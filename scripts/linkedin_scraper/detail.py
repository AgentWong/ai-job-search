"""
Phase 2: fetch full posting from jobs-guest detail endpoint and parse it.

Endpoint:
    https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}

Returns full posting HTML with description, criteria block (seniority,
employment type, job function, industry), poster info, and applicant count.
"""

from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup

from scripts.ats_scraper.config import JobPosting

from .fetcher import RateLimitedSession
from .search import SearchCard

DESCRIPTION_SELECTORS = [
    ".show-more-less-html__markup",
    ".description__text--rich",
    ".description__text",
    ".jobs-description__content",
]


def _text(el) -> str:
    return el.get_text(" ", strip=True) if el else ""


def _parse_easy_apply(soup: BeautifulSoup) -> bool:
    """
    Detect whether the posting is LinkedIn Easy Apply (onsite) vs external apply.

    The guest-API HTML does not contain the literal text "Easy Apply" — that
    label is only rendered for logged-in users. Instead we infer from the
    primary CTA button's tracking-control-name and structure:

      - External apply (good signal): button has class `sign-up-modal__outlet`
        OR contains an icon with `data-svg-class-name` containing
        `offsite-apply-icon`. Tracking name is `*sign-in-modal*`.

      - Easy Apply (onsite — likely lower-quality / mass applicants): button
        has class `apply-button--default` and tracking name matches
        `public_jobs_apply-link-*onsite` (observed variants:
        `apply-link-onsite`, `apply-link-simple_onsite`).

    Returns False on ambiguous markup (no apply button found) — we'd rather
    let a borderline posting through than wrongly flag it as Easy Apply.
    """
    btn = soup.select_one(".top-card-layout__cta-container button")
    if not btn:
        return False

    classes = btn.get("class") or []
    tracking = btn.get("data-tracking-control-name", "") or ""

    if "sign-up-modal__outlet" in classes:
        return False
    if "sign-in-modal" in tracking or "sign-up-modal" in tracking:
        return False
    if btn.select_one("[data-svg-class-name*='offsite-apply-icon']"):
        return False

    if tracking.startswith("public_jobs_apply-link-") and tracking.endswith("onsite"):
        return True
    if "apply-button--default" in classes:
        return True

    return False


def _parse_criteria(soup: BeautifulSoup) -> dict[str, str]:
    """
    Parse the criteria list at the bottom of the detail page.

    Structure:
        <ul class="description__job-criteria-list">
          <li class="description__job-criteria-item">
            <h3 class="description__job-criteria-subheader">Seniority level</h3>
            <span class="description__job-criteria-text ...">Mid-Senior level</span>
          </li>
          ...
    """
    out: dict[str, str] = {}
    for item in soup.select(".description__job-criteria-item"):
        label_el = item.select_one(".description__job-criteria-subheader")
        value_el = item.select_one(".description__job-criteria-text")
        label = _text(label_el).lower()
        value = _text(value_el)
        if label and value:
            out[label] = value
    return out


def parse_detail_html(html: str, card: SearchCard) -> Optional[JobPosting]:
    """
    Parse a detail-page HTML response into a JobPosting (reusing the
    ats_scraper dataclass so downstream tooling treats LinkedIn results the
    same as any ATS scraper result).

    Returns None if the page returned no parseable content (e.g. job removed,
    404, or empty body).
    """
    if not html.strip():
        return None

    soup = BeautifulSoup(html, "html.parser")

    # Title and company from the detail page (more authoritative than card text)
    title_el = soup.select_one(".topcard__title") or soup.select_one("h2.topcard__title")
    company_el = soup.select_one(".topcard__org-name-link") or soup.select_one(".topcard__flavor")
    location_el = soup.select_one(".topcard__flavor--bullet")

    title = _text(title_el) or card.title
    company = _text(company_el) or card.company
    location = _text(location_el) or card.location

    # Description (try selectors in priority order)
    description = ""
    for sel in DESCRIPTION_SELECTORS:
        el = soup.select_one(sel)
        if el:
            description = el.get_text("\n", strip=True)
            break

    # Criteria block -> seniority, employment type, job function, industries
    criteria = _parse_criteria(soup)

    seniority = criteria.get("seniority level", "")
    employment_type = criteria.get("employment type", "")
    job_function = criteria.get("job function", "")
    industries = criteria.get("industries", "")

    # Synthesize workplace_type from criteria + card location text
    workplace_type = ""
    loc_lower = (location + " " + card.location).lower()
    if "remote" in loc_lower:
        workplace_type = "remote"
    elif "hybrid" in loc_lower:
        workplace_type = "hybrid"
    elif "on-site" in loc_lower or "onsite" in loc_lower:
        workplace_type = "on-site"

    # Compensation: LinkedIn's jobs-guest pages rarely surface salary in a
    # stable selector. If it's in the description text, the scorer's regex
    # picks it up. Pass empty here.
    compensation = ""

    department = job_function or industries

    posting = JobPosting(
        company=company,
        title=title,
        url=card.url,
        location=location,
        department=department,
        description_text=description,
        ats_platform="LinkedIn",
        compensation=compensation,
        posted_date=card.posted_label,
        workplace_type=workplace_type,
        description_available=bool(description),
    )

    # Tag seniority + employment_type onto the posting via a side-channel dict
    # so cli.py can include them in the pending_review.json without touching
    # the shared JobPosting dataclass. We attach as ad-hoc attributes.
    posting.linkedin_seniority = seniority  # type: ignore[attr-defined]
    posting.linkedin_employment_type = employment_type  # type: ignore[attr-defined]
    posting.linkedin_easy_apply = _parse_easy_apply(soup)  # type: ignore[attr-defined]

    return posting


def fetch_detail(
    session: RateLimitedSession, card: SearchCard
) -> Optional[JobPosting]:
    html = session.get_detail(card.detail_api_url)
    return parse_detail_html(html, card)
