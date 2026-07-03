"""
Phase 1: search builtin.com jobs and parse listing cards.

Search URL pattern (path segments filter senior + tiny startups at URL level):
    REMOTE mode:
        https://builtin.com/jobs/remote/entry-level/junior/mid-level/51-200/201-500/501-1000/1000
          ?search="<ROLE>"&daysSinceUpdated=<DAYS>&country=USA&allLocations=true&page=<N>
          &handler=SearchResults
    LOCAL mode (target metro = config.yml location.city/state):
        https://builtin.com/jobs/remote/hybrid/office/entry-level/junior/mid-level/51-200/.../1000
          ?search="<ROLE>"&daysSinceUpdated=<DAYS>&country=USA
          &city=<CITY>&state=<STATE>&allLocations=true&page=<N>&handler=SearchResults

LOCATION HANDLING — the load-bearing fix. Built In does NOT filter by a
"<city>-<state>" path slug (e.g. /jobs/austin-tx/...): that path returns
nationwide results, which is why local-mode runs used to surface on-site jobs
in Michigan, Arizona, etc. The metro is constrained by the `city`/`state`
QUERY PARAMS instead (verified live). The path carries only work-arrangement
segments: remote-mode uses `/remote`; local-mode uses `/remote/hybrid/office`
(or `/hybrid/office` when location.accept_remote_in_local_mode is false).
`allLocations=true` lets all-location (remote-US) roles surface alongside the
metro matches; it is dropped in strict-local mode.

The `handler=SearchResults` parameter is critical. Without it, builtin.com
returns the JS-rendered page scaffolding (Alpine.js bindings, filter widgets,
no actual job listings). With it, the same URL returns the HTML partial that
the page's `fetch()` call retrieves and injects into `#jobs-list`. That partial
contains the real job-card markup.

The card markup uses `data-id="job-card"` containers; the job-detail link sits
on `a[data-id="job-card-title"]` (which is also the title text). Company name
is on `a[data-id="company-title"]`. The work-arrangement and location sit in
icon-labelled rows (`i.fa-house-building` -> "Remote"/"Hybrid"/"On-site",
`i.fa-location-dot` -> "Austin, TX, USA"); we extract and pipe-join them into
SearchCard.location so the shared location filter can act as a deterministic
Phase 1 backstop to the server-side geo filter. Phase 2 still re-checks against
the authoritative detail-page JSON-LD.
"""

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from .fetcher import RateLimitedSession
from scripts.ats_scraper.location import LocationConfig

BASE_URL = "https://builtin.com"

# Path segments filter senior titles (entry-level/junior/mid-level) and tiny
# startups (51-200 through 1000+) at the URL level. Never bypass — doing so
# floods Phase 1 with senior/staff/principal roles the regex would just reject.
_SENIORITY_SIZE_SEGMENTS = "/entry-level/junior/mid-level/51-200/201-500/501-1000/1000"

# The path carries only WORK-ARRANGEMENT segments. The metro is set by the
# city/state query params in build_search_url, NOT by a path slug — a
# "<city>-<state>" path segment does not filter on Built In (it returns
# nationwide results).
def _search_path(loc_cfg: LocationConfig) -> str:
    if loc_cfg.remote:
        # Remote-only: the /remote segment + allLocations=true constrains to
        # remote-US roles.
        return "/jobs/remote" + _SENIORITY_SIZE_SEGMENTS
    # Local mode: accept hybrid + on-site ("office") always; include remote too
    # unless the config opts out. The configured metro is applied via the
    # city/state query params (see build_search_url), not the path.
    arrangements = ["hybrid", "office"]
    if loc_cfg.accept_remote_in_local_mode:
        arrangements.insert(0, "remote")
    return "/jobs/" + "/".join(arrangements) + _SENIORITY_SIZE_SEGMENTS

# config.yml time_filter -> daysSinceUpdated value
DAYS_MAP = {
    "past_day": 1,
    "past_2_days": 2,
    "past_week": 7,
    "past_month": 30,
}

# Extracts the numeric job ID from a Builtin job-detail href.
# Builtin job URLs look like: /job/<slug>/<numeric-id>
_JOB_ID_RE = re.compile(r"/job/[^/]+/(\d+)\b")


@dataclass
class SearchCard:
    """A single search-result card before any filtering or detail fetch."""
    job_id: str
    title: str
    company: str
    location: str
    posted_label: str       # e.g. "2 days ago" — may be empty if card omits it
    url: str                # canonical /job/<slug>/<id> URL


def build_search_url(
    role: str,
    *,
    time_filter: str,
    loc_cfg: Optional[LocationConfig] = None,
    page: int = 1,
) -> str:
    """
    Build a Builtin search URL.

    The role is wrapped in literal quotes for exact phrase matching — the same
    convention the browser workflow uses to keep noise down.

    Location is driven by config.yml `location`:
      remote -> /jobs/remote path + allLocations=true (no city/state).
      local  -> /jobs/remote/hybrid/office (or /hybrid/office if remote isn't
                accepted) + city=<City>&state=<State> query params, plus
                allLocations=true when remote-in-local is accepted. The
                city/state params — NOT a path slug — are what actually
                constrain Built In to the target metro.
    """
    days = DAYS_MAP.get(time_filter)
    if days is None:
        raise ValueError(
            f"Unknown time_filter '{time_filter}'. Expected one of {list(DAYS_MAP)}"
        )

    if loc_cfg is None:
        loc_cfg = LocationConfig()  # default = remote-US

    quoted_role = f'"{role}"'
    params = [
        f"search={quote_plus(quoted_role)}",
        f"daysSinceUpdated={days}",
        "country=USA",
    ]
    if loc_cfg.remote:
        params.append("allLocations=true")
    else:
        # Local mode: the metro is constrained by city/state query params
        # (verified: Built In honors these; a path slug does not).
        if not (loc_cfg.city and loc_cfg.state):
            raise ValueError(
                "Built In local-mode search needs location.city + location.state "
                "in config.yml."
            )
        params.append(f"city={quote_plus(loc_cfg.city)}")
        params.append(f"state={quote_plus(loc_cfg.state)}")
        # Keep allLocations=true so all-location (remote-US) roles surface
        # alongside the metro matches; drop it for strict-local search.
        if loc_cfg.accept_remote_in_local_mode:
            params.append("allLocations=true")
    params += [
        f"page={page}",
        # Razor Pages handler — returns the job-card HTML partial that the
        # page's JS would otherwise fetch and inject into #jobs-list. Without
        # this param the response is the JS scaffolding with zero job content.
        "handler=SearchResults",
    ]
    return f"{BASE_URL}{_search_path(loc_cfg)}?{'&'.join(params)}"


def _text(el) -> str:
    return el.get_text(" ", strip=True) if el else ""


def _attr_after_icon(card_el, icon_class: str) -> str:
    """Return the text of the value element that follows a labelled card icon.

    Built In marks each card attribute with a Font Awesome icon; the value sits
    in the element immediately after the icon's wrapper:
        <div>...<i class="fa-regular fa-location-dot ..."></i></div>
        <div><span>Austin, TX, USA</span></div>   <- the value
    Matching on the icon class is the most stable anchor (the surrounding
    layout/util classes churn). Returns "" if the icon or value is absent.
    """
    icon = card_el.select_one(f"i.{icon_class}")
    if icon is None or icon.parent is None:
        return ""
    return _text(icon.parent.find_next_sibling())


def _extract_job_id(href: str) -> Optional[str]:
    if not href:
        return None
    m = _JOB_ID_RE.search(href)
    return m.group(1) if m else None


def _absolute_url(href: str) -> str:
    if not href:
        return ""
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return f"{BASE_URL}{href}"
    return f"{BASE_URL}/{href}"


def _parse_card_element(card_el) -> Optional[SearchCard]:
    """Parse one card-shaped element into a SearchCard. Returns None on miss."""
    # The title anchor IS the job-detail link. data-id is the most stable
    # attribute; fall back to any anchor pointing at /job/<slug>/<id>.
    anchor = (
        card_el.select_one("a[data-id='job-card-title']")
        or card_el.select_one("a[href*='/job/']")
    )
    if not anchor:
        return None
    href = anchor.get("href", "")
    job_id = _extract_job_id(href)
    if not job_id:
        return None

    title = _text(anchor)
    company_el = card_el.select_one("a[data-id='company-title']")
    company = _text(company_el)

    # Work-arrangement + location sit in icon-labelled rows. Pipe-join them
    # ("Hybrid | Austin, TX, USA", "Remote | USA") to feed the shared location
    # filter — a deterministic Phase 1 backstop to the server-side geo filter.
    # Phase 2 re-checks against the authoritative detail-page JSON-LD. Missing
    # icons -> "" -> filter_card skips the location check (defers to Phase 2),
    # so parser drift degrades gracefully rather than dropping every card.
    arrangement = _attr_after_icon(card_el, "fa-house-building")
    loc_text = _attr_after_icon(card_el, "fa-location-dot")
    location = " | ".join(p for p in (arrangement, loc_text) if p)

    # posted_label is left blank: the fa-clock icon nests INSIDE its value span
    # (unlike location/arrangement, whose icons sit in a separate wrapper), so
    # _attr_after_icon doesn't apply, and posted_label isn't used for filtering.
    return SearchCard(
        job_id=job_id,
        title=title,
        company=company,
        location=location,
        posted_label="",
        url=_absolute_url(href),
    )


def parse_search_html(html: str) -> list[SearchCard]:
    """
    Parse a single page of Builtin search results into SearchCard records.

    Tries the documented card selector first; if no cards are found that way,
    falls back to scanning all `<a href="/job/...">` anchors and synthesizing
    minimal cards from them. Defensive against Builtin's class-name churn.
    """
    if not html.strip():
        return []
    soup = BeautifulSoup(html, "html.parser")

    cards: list[SearchCard] = []
    seen_ids: set[str] = set()

    # Primary: explicit card containers
    for card_el in soup.select("[data-id='job-card']"):
        card = _parse_card_element(card_el)
        if card and card.job_id not in seen_ids:
            seen_ids.add(card.job_id)
            cards.append(card)

    # Fallback: anchor scan (in case the card wrapper class changed)
    if not cards:
        for anchor in soup.select("a[href*='/job/']"):
            href = anchor.get("href", "")
            job_id = _extract_job_id(href)
            if not job_id or job_id in seen_ids:
                continue
            seen_ids.add(job_id)
            # Walk up to find a plausible card parent for company/location text
            parent = anchor.find_parent(attrs={"data-id": True}) or anchor.parent
            card = _parse_card_element(parent) if parent else None
            if card is None:
                # Synthesize a minimal card from the anchor alone
                card = SearchCard(
                    job_id=job_id,
                    title=_text(anchor),
                    company="",
                    location="",
                    posted_label="",
                    url=_absolute_url(href),
                )
            cards.append(card)

    return cards


def search_role(
    session: RateLimitedSession,
    role: str,
    *,
    time_filter: str,
    loc_cfg: Optional[LocationConfig] = None,
    max_pages: int = 3,
    verbose: bool = False,
) -> list[SearchCard]:
    """
    Search one role across up to `max_pages` pages.

    De-duplicates by job_id in case Builtin repeats listings across pages.
    Stops early when a page returns zero cards (last page reached).
    """
    seen_ids: set[str] = set()
    all_cards: list[SearchCard] = []

    for page_num in range(1, max_pages + 1):
        url = build_search_url(role, time_filter=time_filter, loc_cfg=loc_cfg, page=page_num)
        if verbose:
            print(f"    page {page_num}/{max_pages}")
        print(f"    [DEBUG] URL: {url}")
        html = session.get_search(url)
        page_cards = parse_search_html(html)

        new_cards = [c for c in page_cards if c.job_id not in seen_ids]
        for c in new_cards:
            seen_ids.add(c.job_id)
        all_cards.extend(new_cards)

        if verbose:
            print(f"      -> {len(page_cards)} cards ({len(new_cards)} new)")

        if not page_cards:
            break

    return all_cards
