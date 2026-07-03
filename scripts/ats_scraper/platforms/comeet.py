"""
Comeet (now Spark Hire Recruit) ATS fetcher

API:
    GET https://www.comeet.co/careers-api/2.0/company/{uid}/positions?token={token}&details=true

The token is **public**, embedded in the customer career-page widget HTML/JS.
It is per-company but is not a credential.

ATS_Slug format: "{uid}|{token}". Both are required.

Response: list of positions with:
    { "uid", "name" (title), "url", "url_active",
      "department", "department_path",
      "location": {"name", "country_code", "is_remote"},
      "details": { "pitch" (HTML), "requirements" (HTML),
                   "responsibilities" (HTML), "description" (HTML) },
      "workplace_type": "Remote" | "On-site" | "Hybrid",
      "time_created", "type" }
"""

import html as html_module
import re
from datetime import datetime, timezone
from ..config import CompanyTarget, JobPosting
from .utils import make_session, retry_get


LIST_URL = (
    "https://www.comeet.co/careers-api/2.0/company/{uid}/positions"
    "?token={token}&details=true"
)

_HTML_TAG = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    decoded = html_module.unescape(text or "")
    return _HTML_TAG.sub(" ", decoded).strip()


def _split_slug(slug: str) -> tuple[str, str]:
    if "|" in slug:
        uid, token = slug.split("|", 1)
        return uid.strip(), token.strip()
    return slug.strip(), ""


def _workplace_type(position: dict) -> str:
    wt = (position.get("workplace_type") or "").lower()
    if "remote" in wt:
        return "remote"
    if "hybrid" in wt:
        return "hybrid"
    if "on-site" in wt or "onsite" in wt or "on site" in wt:
        return "on-site"
    loc = position.get("location") or {}
    if isinstance(loc, dict) and loc.get("is_remote"):
        return "remote"
    return ""


def _location_str(position: dict) -> str:
    loc = position.get("location")
    if isinstance(loc, dict):
        return loc.get("name", "") or ""
    return ""


def _format_posted(raw) -> str:
    if not raw:
        return ""
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(int(raw), tz=timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, OSError):
            return ""
    if isinstance(raw, str):
        return raw[:10]
    return ""


def _extract_description(details) -> str:
    """Extract description text from Comeet details field.

    Comeet's API returns details as a list of {name, value, order} dicts
    (current format) rather than the older single-dict with named keys.
    """
    if isinstance(details, dict):
        # Legacy format: {pitch, description, responsibilities, requirements}
        parts = [
            details.get("pitch", ""),
            details.get("description", ""),
            details.get("responsibilities", ""),
            details.get("requirements", ""),
        ]
        return strip_html(" ".join(p for p in parts if p))
    if isinstance(details, list):
        # Current format: [{name, value, order}, ...]
        parts = [item.get("value", "") for item in details if isinstance(item, dict)]
        return strip_html(" ".join(p for p in parts if p))
    return ""


def fetch_jobs(target: CompanyTarget) -> list[JobPosting]:
    uid, token = _split_slug(target.board_token)
    if not uid or not token:
        return []

    session = make_session()
    url = LIST_URL.format(uid=uid, token=token)
    data = retry_get(session, url)
    if not isinstance(data, list):
        return []

    postings: list[JobPosting] = []
    for pos in data:
        description_text = _extract_description(pos.get("details"))

        dept = pos.get("department")
        department = ""
        if isinstance(dept, dict):
            department = dept.get("name", "") or ""
        elif isinstance(dept, str):
            department = dept
        if not department:
            department = pos.get("department_path", "") or ""

        # url_active_page is the canonical apply URL in the current API response;
        # url_comeet_hosted_page and position_url are fallbacks.
        apply_url = (
            pos.get("url_active_page")
            or pos.get("url_detected_page")
            or pos.get("url_comeet_hosted_page")
            or pos.get("position_url")
            or pos.get("url")
            or ""
        )

        # time_created is null in current API; time_updated is always present.
        posted_raw = pos.get("time_created") or pos.get("time_updated") or pos.get("created")

        postings.append(JobPosting(
            company=target.name,
            title=pos.get("name", "") or "",
            url=apply_url,
            location=_location_str(pos),
            department=department,
            description_text=description_text,
            ats_platform=target.ats_platform,
            compensation=pos.get("employment_type") or pos.get("type", "") or "",
            posted_date=_format_posted(posted_raw),
            workplace_type=_workplace_type(pos),
            description_available=bool(description_text),
        ))

    return postings
