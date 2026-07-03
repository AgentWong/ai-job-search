"""
Phase 2: fetch a Builtin job detail page and parse it into a JobPosting.

Builtin emits structured JobPosting JSON-LD on every detail page for SEO. We
parse that as the primary source — it's the most stable surface (Builtin would
break its own search-engine indexing by removing it). CSS selectors are used
only as a fallback when the JSON-LD block is missing or unparseable.

JSON-LD fields consumed:
    title                                 -> JobPosting.title
    hiringOrganization.name               -> JobPosting.company
    jobLocation[].address.{addressLocality, addressRegion}
    jobLocationType                       -> "TELECOMMUTE" => Remote
    baseSalary.value.{minValue, maxValue} -> JobPosting.compensation
    datePosted                            -> JobPosting.posted_date
    description (HTML)                    -> JobPosting.description_text (stripped)
    industry                              -> JobPosting.department (fallback)

CSS fallback (used only if JSON-LD missing):
    Description selectors listed in DESCRIPTION_SELECTORS below.
"""

import json
import re
from typing import Optional

from bs4 import BeautifulSoup

from scripts.ats_scraper.config import JobPosting

from .fetcher import RateLimitedSession
from .search import SearchCard

DESCRIPTION_SELECTORS = [
    "[data-testid='job-description']",
    ".job-description",
    ".job-details-description",
    "[class*='JobDescription']",
]


def _text(el) -> str:
    return el.get_text(" ", strip=True) if el else ""


def _strip_html(html_str: str) -> str:
    """Strip tags and decode entities from the HTML description field."""
    if not html_str:
        return ""
    return BeautifulSoup(html_str, "html.parser").get_text("\n", strip=True)


def _walk_for_job_posting(node) -> Optional[dict]:
    """
    Find the first JobPosting object inside an LD+JSON payload.

    Builtin's payload may be a bare object, an object with `@graph`, or a list.
    """
    if isinstance(node, dict):
        if node.get("@type") == "JobPosting":
            return node
        graph = node.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                found = _walk_for_job_posting(item)
                if found:
                    return found
        # Some sites nest under "mainEntity" etc.
        for v in node.values():
            if isinstance(v, (dict, list)):
                found = _walk_for_job_posting(v)
                if found:
                    return found
    elif isinstance(node, list):
        for item in node:
            found = _walk_for_job_posting(item)
            if found:
                return found
    return None


def _extract_ld_json(soup: BeautifulSoup) -> Optional[dict]:
    """Find and return the first JobPosting dict from any LD+JSON script."""
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text() or ""
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        posting = _walk_for_job_posting(data)
        if posting:
            return posting
    return None


def _extract_location_from_ld(posting: dict) -> tuple[str, str]:
    """
    Return (location_str, workplace_type) from a JobPosting JSON-LD dict.

    jobLocationType == "TELECOMMUTE" => "Remote" / "remote"
    Otherwise pipe-join `addressLocality, addressRegion` across jobLocation[].
    """
    location_type = posting.get("jobLocationType")
    if isinstance(location_type, list):
        location_type = location_type[0] if location_type else None
    is_remote = (
        isinstance(location_type, str)
        and location_type.upper() == "TELECOMMUTE"
    )

    job_location = posting.get("jobLocation") or []
    if isinstance(job_location, dict):
        job_location = [job_location]

    parts: list[str] = []
    for loc in job_location:
        if not isinstance(loc, dict):
            continue
        address = loc.get("address") or {}
        if not isinstance(address, dict):
            continue
        locality = (address.get("addressLocality") or "").strip()
        region = (address.get("addressRegion") or "").strip()
        country = (address.get("addressCountry") or "").strip()
        pieces = [p for p in (locality, region) if p]
        if not pieces and country:
            pieces.append(country if isinstance(country, str) else "")
        if pieces:
            parts.append(", ".join(pieces))

    location_str = "|".join(parts) if parts else ""
    if is_remote:
        if location_str:
            location_str = f"Remote ({location_str})"
        else:
            location_str = "Remote"
        return location_str, "remote"

    return location_str, ""


def _extract_salary_from_ld(posting: dict) -> str:
    """
    Format `$<min>K-$<max>K` from baseSalary.value. Empty if absent or partial.

    Plain hyphen (no en/em dash) for consistency with the rest of the codebase.
    """
    base = posting.get("baseSalary")
    if not isinstance(base, dict):
        return ""
    value = base.get("value")
    if not isinstance(value, dict):
        return ""
    min_v = value.get("minValue")
    max_v = value.get("maxValue")
    if min_v is None or max_v is None:
        return ""
    try:
        min_n = float(min_v)
        max_n = float(max_v)
    except (TypeError, ValueError):
        return ""
    if min_n <= 0 or max_n <= 0:
        return ""
    return f"${round(min_n/1000)}K-${round(max_n/1000)}K"


def _extract_industry_from_ld(posting: dict) -> str:
    """Best-effort industry/department string for JobPosting.department."""
    industry = posting.get("industry")
    if isinstance(industry, list):
        industry = ", ".join(i for i in industry if isinstance(i, str))
    if isinstance(industry, str):
        return industry
    return ""


def _company_name_from_ld(posting: dict) -> str:
    org = posting.get("hiringOrganization")
    if isinstance(org, dict):
        name = org.get("name") or org.get("legalName") or ""
        if isinstance(name, str):
            return name.strip()
    if isinstance(org, str):
        return org.strip()
    return ""


def _parse_from_ld(html: str, card: SearchCard) -> Optional[JobPosting]:
    soup = BeautifulSoup(html, "html.parser")
    posting = _extract_ld_json(soup)
    if not posting:
        return None

    title = (posting.get("title") or card.title or "").strip()
    company = _company_name_from_ld(posting) or card.company
    location_str, workplace_type = _extract_location_from_ld(posting)
    if not location_str:
        location_str = card.location
    description = _strip_html(posting.get("description") or "")
    compensation = _extract_salary_from_ld(posting)
    department = _extract_industry_from_ld(posting)
    posted_date = (posting.get("datePosted") or card.posted_label or "").strip()

    return JobPosting(
        company=company,
        title=title,
        url=card.url,
        location=location_str,
        department=department,
        description_text=description,
        ats_platform="Built In",
        compensation=compensation,
        posted_date=posted_date,
        workplace_type=workplace_type,
        description_available=bool(description),
    )


def _parse_from_selectors(html: str, card: SearchCard) -> Optional[JobPosting]:
    """CSS fallback for when LD+JSON is missing or unparseable."""
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.select_one("h1") or soup.select_one("[class*='JobTitle']")
    title = _text(title_el) or card.title

    company_el = (
        soup.select_one("[class*='CompanyName']")
        or soup.select_one("[data-testid*='company']")
    )
    company = _text(company_el) or card.company

    description = ""
    for sel in DESCRIPTION_SELECTORS:
        el = soup.select_one(sel)
        if el:
            description = el.get_text("\n", strip=True)
            break

    # Heuristic workplace_type from card / description
    workplace_type = ""
    blob = (card.location + " " + description[:500]).lower()
    if "remote" in blob:
        workplace_type = "remote"
    elif "hybrid" in blob:
        workplace_type = "hybrid"
    elif "on-site" in blob or "onsite" in blob:
        workplace_type = "on-site"

    return JobPosting(
        company=company,
        title=title,
        url=card.url,
        location=card.location,
        department="",
        description_text=description,
        ats_platform="Built In",
        compensation="",
        posted_date=card.posted_label,
        workplace_type=workplace_type,
        description_available=bool(description),
    )


def parse_detail_html(html: str, card: SearchCard) -> Optional[JobPosting]:
    """
    Parse a Builtin detail-page HTML response into a JobPosting.

    Tries JSON-LD first (preferred — Builtin emits structured JobPosting for
    SEO). Falls back to CSS selectors if the LD+JSON block is missing.

    Returns None if the page is empty (404 / removed job / blocked).
    """
    if not html.strip():
        return None

    via_ld = _parse_from_ld(html, card)
    if via_ld is not None:
        return via_ld
    return _parse_from_selectors(html, card)


def fetch_detail(
    session: RateLimitedSession, card: SearchCard
) -> Optional[JobPosting]:
    html = session.get_detail(card.url)
    return parse_detail_html(html, card)
