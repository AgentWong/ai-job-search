"""
Phase 1: search LinkedIn jobs-guest API and parse listing cards.

Endpoint:
    https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search

Returns ~10 cards per page. Pagination via `start=0,10,20,...`.

Each card carries:
  - data-entity-urn="urn:li:jobPosting:{jobId}"
  - .base-search-card__title
  - .base-search-card__subtitle (company)
  - .job-search-card__location
  - .job-search-card__listdate (or --new for fresh listings)
"""

from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from .fetcher import RateLimitedSession
from scripts.ats_scraper.location import LocationConfig

SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
US_GEO_ID = "103644278"
# The jobs-guest endpoint pages by 10 (it returns ~10 cards per request and
# `start` advances by 10). A larger value here both (a) makes the
# `len(page_cards) < PAGE_SIZE` last-page check fire after page 1 — capping every
# role at a single page regardless of --max-pages — and (b) skips cards by
# over-advancing `start`. Verified live: 10 cards/page.
PAGE_SIZE = 10

# LinkedIn f_WT (workplace type) codes: 1 = on-site, 2 = remote, 3 = hybrid.

# config.yml time_filter -> LinkedIn f_TPR value
TPR_MAP = {
    "past_day": "r86400",
    "past_2_days": "r172800",
    "past_week": "r604800",
    "past_month": "r2592000",
}

# Canonical job URL (used as the stable URL in the queue, not the API endpoint)
JOB_VIEW_URL = "https://www.linkedin.com/jobs/view/{job_id}"


@dataclass
class SearchCard:
    """A single search-result card before any filtering or detail fetch."""
    job_id: str
    title: str
    company: str
    location: str
    posted_label: str       # "1 day ago", "2 weeks ago", etc.
    url: str                # canonical jobs/view/{id} URL

    @property
    def detail_api_url(self) -> str:
        return f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{self.job_id}"


def build_search_url(
    role: str,
    *,
    time_filter: str,
    loc_cfg: Optional[LocationConfig] = None,
    job_type: str = "F",         # F = Full-time
    experience_levels: Optional[str] = None,  # comma-separated, e.g. "2,3,4"
    sort_by: str = "DD",
    start: int = 0,
) -> str:
    """
    Build a jobs-guest search URL.

    The role is wrapped in literal quotes for exact phrase matching — unquoted
    searches return 7-62x more irrelevant results (measured on LinkedIn).

    Location is driven by config.yml `location` (via loc_cfg):
      remote -> US-wide geoId + f_WT=2 (Remote)
      local  -> the configured metro geoId + f_WT for on-site/hybrid
                (plus remote when accept_remote_in_local_mode).
    """
    tpr = TPR_MAP.get(time_filter)
    if tpr is None:
        raise ValueError(
            f"Unknown time_filter '{time_filter}'. Expected one of {list(TPR_MAP)}"
        )

    if loc_cfg is None:
        loc_cfg = LocationConfig()  # default = remote-US

    distance_param: Optional[str] = None
    if loc_cfg.remote:
        geo_param = f"geoId={US_GEO_ID}"
        f_wt = "2"   # Remote only
    else:
        if not (loc_cfg.city and loc_cfg.state):
            raise ValueError(
                "LinkedIn local-mode search needs location.city and location.state "
                "in config.yml (location.remote: false)."
            )
        # Verified empirically: the jobs-guest endpoint resolves a free-text
        # `location` param to the metro (location=Austin, Texas -> Austin/Cedar
        # Park cards). Guessing numeric geoIds is unreliable (e.g. 90000063 =>
        # Wisconsin, 103743442 => Houston), so free text is the default. An
        # explicit geo_codes.linkedin_geo_id overrides it for exact targeting.
        override_geo = (loc_cfg.geo_codes.get("linkedin_geo_id") or "").strip()
        if override_geo:
            geo_param = f"geoId={override_geo}"
        else:
            geo_param = f"location={quote_plus(f'{loc_cfg.city}, {loc_cfg.state}')}"
        # f_WT: 1=on-site, 2=remote, 3=hybrid. Include remote when accepted.
        f_wt = "1,2,3" if loc_cfg.accept_remote_in_local_mode else "1,3"
        # LinkedIn radius param is `distance` (miles). Verified live: distance=25
        # is reflected as "25 mi" in the filter UI. Only meaningful in local mode.
        if loc_cfg.distance_miles:
            distance_param = f"distance={int(loc_cfg.distance_miles)}"

    quoted_role = f'"{role}"'
    params = [
        f"keywords={quote_plus(quoted_role)}",
        geo_param,
        f"f_TPR={tpr}",
        f"f_WT={f_wt}",
        f"f_JT={job_type}",
        f"sortBy={sort_by}",
        f"start={start}",
    ]
    if distance_param:
        params.append(distance_param)
    if experience_levels:
        params.append(f"f_E={experience_levels}")

    return f"{SEARCH_URL}?{'&'.join(params)}"


def _text(el) -> str:
    return el.get_text(" ", strip=True) if el else ""


def parse_search_html(html: str) -> list[SearchCard]:
    """Parse a single page of search results into SearchCard records."""
    if not html.strip():
        return []
    soup = BeautifulSoup(html, "html.parser")
    cards: list[SearchCard] = []

    for el in soup.find_all(attrs={"data-entity-urn": True}):
        urn = el.get("data-entity-urn", "")
        if not urn.startswith("urn:li:jobPosting:"):
            continue
        job_id = urn.rsplit(":", 1)[-1]
        if not job_id.isdigit():
            continue

        title_el = el.select_one(".base-search-card__title")
        company_el = el.select_one(".base-search-card__subtitle")
        location_el = el.select_one(".job-search-card__location")
        posted_el = (
            el.select_one(".job-search-card__listdate--new")
            or el.select_one(".job-search-card__listdate")
        )

        cards.append(SearchCard(
            job_id=job_id,
            title=_text(title_el),
            company=_text(company_el),
            location=_text(location_el),
            posted_label=_text(posted_el),
            url=JOB_VIEW_URL.format(job_id=job_id),
        ))

    return cards


def search_role(
    session: RateLimitedSession,
    role: str,
    *,
    time_filter: str,
    loc_cfg: Optional[LocationConfig] = None,
    max_pages: int = 3,
    experience_levels: Optional[str] = None,
    verbose: bool = False,
) -> list[SearchCard]:
    """
    Search one role across up to `max_pages` pages.

    De-duplicates by job_id in case LinkedIn returns repeats across pages.
    Stops early when a page returns fewer than PAGE_SIZE cards (last page).
    """
    seen_ids: set[str] = set()
    all_cards: list[SearchCard] = []

    for page in range(max_pages):
        start = page * PAGE_SIZE
        url = build_search_url(
            role,
            time_filter=time_filter,
            loc_cfg=loc_cfg,
            experience_levels=experience_levels,
            start=start,
        )
        if verbose:
            print(f"    page {page + 1}/{max_pages}: start={start}")
        print(f"    [DEBUG] URL: {url}")
        html = session.get_search(url)
        page_cards = parse_search_html(html)

        new_cards = [c for c in page_cards if c.job_id not in seen_ids]
        for c in new_cards:
            seen_ids.add(c.job_id)
        all_cards.extend(new_cards)

        if verbose:
            print(f"      -> {len(page_cards)} cards ({len(new_cards)} new)")

        if len(page_cards) < PAGE_SIZE:
            # Last page reached
            break

    return all_cards
