"""
Recruitee ATS fetcher

API: GET https://{company}.recruitee.com/api/offers/
Response: { "offers": [ { "id", "slug", "title", "location", "city", "country",
                           "department", "description" (HTML), "requirements" (HTML),
                           "remote" (bool), "hybrid" (bool), "on_site" (bool),
                           "employment_type_code", "careers_url", "created_at",
                           "published_at", ... } ] }

HTML-encoded description + requirements; strip tags for plaintext.
"""

import html as html_module
import re
from ..config import CompanyTarget, JobPosting
from .utils import make_session, retry_get


BASE_URL = "https://{token}.recruitee.com/api/offers/"

_HTML_TAG = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    decoded = html_module.unescape(text or "")
    return _HTML_TAG.sub(" ", decoded).strip()


def _workplace_type(offer: dict) -> str:
    if offer.get("remote"):
        return "remote"
    if offer.get("hybrid"):
        return "hybrid"
    if offer.get("on_site"):
        return "on-site"
    return ""


def fetch_jobs(target: CompanyTarget) -> list[JobPosting]:
    session = make_session()
    url = BASE_URL.format(token=target.board_token)
    data = retry_get(session, url)

    postings = []
    for offer in data.get("offers", []) or []:
        description = strip_html(offer.get("description", "") or "")
        requirements = strip_html(offer.get("requirements", "") or "")
        combined = (description + " " + requirements).strip()

        location = offer.get("location", "") or ""
        if not location:
            city = offer.get("city", "") or ""
            country = offer.get("country", "") or ""
            location = ", ".join(p for p in (city, country) if p)

        department_obj = offer.get("department")
        department = department_obj if isinstance(department_obj, str) else ""

        posted = (offer.get("published_at") or offer.get("created_at") or "")[:10]

        postings.append(JobPosting(
            company=target.name,
            title=offer.get("title", "") or "",
            url=offer.get("careers_url", "") or "",
            location=location,
            department=department,
            description_text=combined,
            ats_platform=target.ats_platform,
            posted_date=posted,
            workplace_type=_workplace_type(offer),
            description_available=True,
        ))

    return postings
