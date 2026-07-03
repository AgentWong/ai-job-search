"""Backfill authoritative location for Workable results Firecrawl can't see.

Workable (apply.workable.com) renders its location block client-side from a JSON
API: the static markdown Firecrawl scrapes contains the job body and a bare
"Remote" label, but NOT the country. A posting open only to South Africa / Kenya
therefore reaches the filter looking like a clean US-eligible "Remote" role, so
neither the regex pre-filter (no country token in title/URL/snippet) nor the LLM
reviewer (scores from that same markdown) can drop it — it qualifies on every run.

Workable serves the structured location verbatim from a public JSON endpoint:

    https://apply.workable.com/api/v2/accounts/{account}/jobs/{shortcode}
    -> {"location": {"country": "...", "countryCode": "ZA"},
        "locations": [{"countryCode": "ZA"}, {"countryCode": "KE"}], ...}

Both `{account}` and `{shortcode}` are reconstructable from the result URL
(apply.workable.com/{account}/j/{shortcode}/) — no new search, no Firecrawl
credits. This module fetches that JSON and injects the authoritative country
into the result so the downstream non-US gate can act on it.

Conservative by design: any fetch/parse failure leaves the result unchanged so
it falls through to the existing gates exactly as before — enrichment only ever
*adds* a drop signal, never removes one.
"""

from __future__ import annotations

import re

import requests

# Workable's JSON country/countryCode is ISO; we treat US as the only eligible
# country in remote mode (residence-state eligibility is handled downstream).
_US_CODES = {"US", "USA"}
_US_COUNTRY_NAMES = {"united states", "united states of america", "usa", "us"}

_URL_RE = re.compile(
    r"apply\.workable\.com/(?P<account>[^/]+)/j/(?P<shortcode>[^/?#]+)",
    re.IGNORECASE,
)

_API = "https://apply.workable.com/api/v2/accounts/{account}/jobs/{shortcode}"

_HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
}


def _is_workable(url: str) -> bool:
    return "apply.workable.com" in (url or "").lower()


def make_workable_session() -> requests.Session:
    """One session reused across a query's Workable fetches (keep-alive)."""
    s = requests.Session()
    s.headers.update(_HEADERS)
    return s


def _location_is_us(loc: dict) -> bool:
    code = (loc.get("countryCode") or "").strip().upper()
    if code:
        return code in _US_CODES
    country = (loc.get("country") or "").strip().lower()
    return country in _US_COUNTRY_NAMES


def _label(locations: list[dict]) -> str:
    """Human-readable country list for the snippet (e.g. 'South Africa, Kenya')."""
    seen, out = set(), []
    for loc in locations:
        name = (loc.get("country") or loc.get("countryCode") or "").strip()
        if name and name.lower() not in seen:
            seen.add(name.lower())
            out.append(name)
    return ", ".join(out)


def enrich_workable_result(item: dict, session: requests.Session | None = None) -> str | None:
    """Resolve a Workable result's authoritative location via the public JSON API.

    Mutates `item['description']` to surface the resolved country (so the
    existing snippet-based gates see it), and returns:
      - "non_us_workable" if NO listed location is US-eligible (caller should drop),
      - None otherwise (enriched-and-kept, OR not a Workable URL, OR fetch failed —
        in every None case the caller's downstream gates run unchanged).

    Never raises: any network/parse error returns None (conservative — fall
    through to the existing filter behavior rather than dropping on a bad fetch).
    """
    url = item.get("url", "") or ""
    if not _is_workable(url):
        return None

    m = _URL_RE.search(url)
    if not m:
        return None

    api = _API.format(account=m.group("account"), shortcode=m.group("shortcode"))
    try:
        sess = session or requests
        resp = sess.get(api, headers=_HEADERS, timeout=10)
        if resp.status_code != 200:
            return None
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None

    # Collect every advertised location (primary + locations[]).
    locations: list[dict] = []
    primary = data.get("location")
    if isinstance(primary, dict):
        locations.append(primary)
    for loc in data.get("locations") or []:
        if isinstance(loc, dict) and not loc.get("hidden"):
            locations.append(loc)

    if not locations:
        return None  # nothing authoritative to act on

    label = _label(locations)
    if label:
        # Surface the resolved country so the report/debug trail shows WHY,
        # and so any downstream snippet check also sees it.
        item["description"] = f"{label}. {item.get('description', '') or ''}".strip()

    # Authoritative drop: not one advertised location is US-eligible.
    if not any(_location_is_us(loc) for loc in locations):
        return "non_us_workable"

    return None
