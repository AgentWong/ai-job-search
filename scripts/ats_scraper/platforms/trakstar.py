"""
Trakstar Hire (formerly Recruiterbox) ATS fetcher

Public documented API — no auth, no token bootstrap.

List API:
    GET https://jsapi.recruiterbox.com/v1/openings?client_name={slug}&limit=300
    Response: { "objects": [ { "id", "title", "description" (HTML), "requirements" (HTML),
                                "url" (str), "hosted_url", "location": {...},
                                "department": {"name"}, "team": {"name"},
                                "position_type": "Full-time" | ...,
                                "allows_remote": bool,
                                "city", "state", "country", "remote_status",
                                "created_at" } ], "meta": {"total_count", "next"} }

Subdomain `{slug}.recruiterbox.com` is being migrated to `{slug}.hire.trakstar.com`,
but the `jsapi` API endpoint is unchanged.

`allows_remote` boolean → workplace_type "remote" trivially.
"""

import html as html_module
import re
import time
from ..config import CompanyTarget, JobPosting
from .utils import make_session, retry_get


LIST_URL = "https://jsapi.recruiterbox.com/v1/openings?client_name={slug}&limit=300&offset={offset}"

_HTML_TAG = re.compile(r"<[^>]+>")
PAGE_DELAY = 0.3


def strip_html(text: str) -> str:
    decoded = html_module.unescape(text or "")
    return _HTML_TAG.sub(" ", decoded).strip()


def _format_location(opening: dict) -> str:
    loc = opening.get("location")
    if isinstance(loc, dict):
        parts = [loc.get("city"), loc.get("state"), loc.get("country")]
        joined = ", ".join(p for p in parts if p)
        if joined:
            return joined
    parts = [
        opening.get("city"),
        opening.get("state"),
        opening.get("country"),
    ]
    return ", ".join(p for p in parts if p)


def _workplace_type(opening: dict) -> str:
    if opening.get("allows_remote") is True:
        return "remote"
    rs = (opening.get("remote_status") or "").lower()
    if "remote" in rs:
        return "remote"
    if "hybrid" in rs:
        return "hybrid"
    return ""


def _department(opening: dict) -> str:
    dept = opening.get("department")
    if isinstance(dept, dict):
        name = dept.get("name") or ""
        if name:
            return name
    team = opening.get("team")
    if isinstance(team, dict):
        return team.get("name", "") or ""
    return ""


def fetch_jobs(target: CompanyTarget) -> list[JobPosting]:
    session = make_session()
    postings: list[JobPosting] = []
    offset = 0

    while True:
        url = LIST_URL.format(slug=target.board_token, offset=offset)
        data = retry_get(session, url)
        objects = data.get("objects", []) or []
        if not objects:
            break

        for op in objects:
            description = strip_html(op.get("description", "") or "")
            requirements = strip_html(op.get("requirements", "") or "")
            combined = (description + " " + requirements).strip()

            apply_url = (
                op.get("hosted_url")
                or op.get("url")
                or op.get("apply_url")
                or ""
            )
            if apply_url and not apply_url.startswith("http"):
                apply_url = f"https://{target.board_token}.recruiterbox.com{apply_url}"

            posted = (op.get("created_at") or "")[:10]

            postings.append(JobPosting(
                company=target.name,
                title=op.get("title", "") or "",
                url=apply_url,
                location=_format_location(op),
                department=_department(op),
                description_text=combined,
                ats_platform=target.ats_platform,
                compensation=op.get("position_type", "") or "",
                posted_date=posted,
                workplace_type=_workplace_type(op),
                description_available=True,
            ))

        meta = data.get("meta") or {}
        total = int(meta.get("total_count") or 0)
        offset += len(objects)
        if total and offset >= total:
            break
        if len(objects) < 300:
            break
        time.sleep(PAGE_DELAY)

    return postings
