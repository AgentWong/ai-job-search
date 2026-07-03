"""
Gem ATS fetcher

Public documented API. The response shape is Greenhouse-derived: a bare list
of job objects with `title`, `content` (HTML), `absolute_url`, `location`,
`departments`, `offices`, etc.

List API:
    GET https://api.gem.com/job_board/v0/{vanity}/job_posts/
    Response: [
      { "id", "title", "content" (HTML), "content_plain",
        "absolute_url",
        "location": {"name"}, "location_type",
        "departments": [{"id","name",...}], "offices": [{"id","name","location"}],
        "employment_type", "requisition_id", "internal_job_id",
        "created_at", "updated_at", "first_published_at" }, ...
    ]
"""

import html as html_module
import re
from ..config import CompanyTarget, JobPosting
from .utils import make_session, retry_get


LIST_URL = "https://api.gem.com/job_board/v0/{slug}/job_posts/"

_HTML_TAG = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    decoded = html_module.unescape(text or "")
    return _HTML_TAG.sub(" ", decoded).strip()


def _location_str(post: dict) -> str:
    loc = post.get("location")
    if isinstance(loc, dict):
        name = loc.get("name") or ""
        if name:
            return name
    elif isinstance(loc, str):
        return loc
    offices = post.get("offices") or []
    if offices and isinstance(offices, list):
        first = offices[0]
        if isinstance(first, dict):
            office_loc = first.get("location")
            if isinstance(office_loc, dict) and office_loc.get("name"):
                return office_loc["name"]
            return first.get("name", "") or ""
    return ""


def _workplace_type(post: dict) -> str:
    lt = (post.get("location_type") or "").lower()
    if "remote" in lt:
        return "remote"
    if "hybrid" in lt:
        return "hybrid"
    if lt in ("onsite", "on-site", "on site"):
        return "on-site"
    name = (_location_str(post) or "").lower()
    if "remote" in name:
        return "remote"
    if "hybrid" in name:
        return "hybrid"
    return ""


def _department(post: dict) -> str:
    depts = post.get("departments") or []
    if isinstance(depts, list) and depts:
        first = depts[0]
        if isinstance(first, dict):
            return first.get("name", "") or ""
    return ""


def fetch_jobs(target: CompanyTarget) -> list[JobPosting]:
    session = make_session()
    url = LIST_URL.format(slug=target.board_token)
    data = retry_get(session, url)

    # Gem returns a bare list (Greenhouse-style); be lenient if a wrapper appears.
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("results") or data.get("job_posts") or data.get("data") or []
    else:
        return []

    postings: list[JobPosting] = []
    for post in items:
        desc = strip_html(post.get("content", "") or post.get("content_plain", "") or "")
        apply_url = post.get("absolute_url") or post.get("apply_url") or ""
        posted = (
            post.get("first_published_at")
            or post.get("created_at")
            or post.get("updated_at")
            or ""
        )[:10]

        postings.append(JobPosting(
            company=target.name,
            title=post.get("title", "") or "",
            url=apply_url,
            location=_location_str(post),
            department=_department(post),
            description_text=desc,
            ats_platform=target.ats_platform,
            compensation=post.get("employment_type", "") or "",
            posted_date=posted,
            workplace_type=_workplace_type(post),
            description_available=bool(desc),
        ))

    return postings
