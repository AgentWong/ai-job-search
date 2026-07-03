"""
Rippling ATS fetcher

List API:   GET https://api.rippling.com/platform/api/ats/v1/board/{board_slug}/jobs
Response:   [ { "uuid", "name", "department": {"label", "id"},
                "workLocation": {"label", "id"}, "url" } ]

Detail API: GET https://api.rippling.com/platform/api/ats/v1/board/{board_slug}/jobs/{uuid}
Response:   { "uuid", "name", "description": {"company" (HTML), "role" (HTML)},
              "createdOn" (ISO 8601), "workLocations": [str], "payRangeDetails": [...] }

The list endpoint returns title/location only — no description text and no date.
The per-job detail endpoint carries the full HTML description and `createdOn`.
Like Workday, we title-filter first and fetch the detail only for title-matching
jobs (keeps the per-board fan-out small). All jobs are still returned so the
per-company "Fetched" count and the slug-validator's non-prefiltered semantics
stay intact; non-matching jobs keep description_available=False. A failed/empty
detail fetch falls through to description_available=False (conservative — the
posting reaches the no_description gate instead of being scored on partial data).
"""

import re
import time
import html as html_module
import requests
from ..config import CompanyTarget, JobPosting
from ..filters import title_passes
from .utils import make_session, retry_get


LIST_URL = "https://api.rippling.com/platform/api/ats/v1/board/{token}/jobs"
DETAIL_URL = "https://api.rippling.com/platform/api/ats/v1/board/{token}/jobs/{uuid}"

RIPPLING_HEADERS = {
    "Accept": "application/json",
}

_HTML_TAG = re.compile(r"<[^>]+>")
DETAIL_DELAY = 0.4


def strip_html(text: str) -> str:
    decoded = html_module.unescape(text or "")
    return _HTML_TAG.sub(" ", decoded).strip()


def _fetch_detail(session: requests.Session, token: str, uuid: str) -> dict:
    """Fetch a single job's detail. Returns {"description", "posted_date"};
    both "" on any failure so the caller falls back to the no_description gate."""
    out = {"description": "", "posted_date": ""}
    if not uuid:
        return out
    try:
        detail = retry_get(session, DETAIL_URL.format(token=token, uuid=uuid))
    except Exception:
        return out
    desc = detail.get("description") or {}
    if isinstance(desc, dict):
        parts = [strip_html(desc.get("company", "")), strip_html(desc.get("role", ""))]
        out["description"] = "\n\n".join(p for p in parts if p)
    out["posted_date"] = detail.get("createdOn", "") or ""
    return out


def fetch_jobs(target: CompanyTarget) -> list[JobPosting]:
    session = make_session(extra_headers=RIPPLING_HEADERS)
    url = LIST_URL.format(token=target.board_token)
    data = retry_get(session, url)

    # Rippling returns a bare list
    if isinstance(data, dict):
        items = data.get("data", data.get("jobs", []))
    else:
        items = data

    postings = []
    for job in items:
        title = job.get("name", "") or ""
        work_location = job.get("workLocation") or {}
        location = work_location.get("label", "") if isinstance(work_location, dict) else ""
        department_obj = job.get("department") or {}
        department = department_obj.get("label", "") if isinstance(department_obj, dict) else ""
        posting_url = job.get("url", "") or ""
        uuid = job.get("uuid", "") or ""

        # Construct full URL if relative
        if posting_url and not posting_url.startswith("http"):
            posting_url = f"https://ats.rippling.com{posting_url}"

        # Backfill the description + date from the detail endpoint, but only for
        # title-matching jobs (everything else is rejected at the title stage, so
        # the description would be discarded anyway).
        description_text = ""
        posted_date = ""
        description_available = False
        if title_passes(title):
            detail = _fetch_detail(session, target.board_token, uuid)
            if detail["description"]:
                description_text = detail["description"]
                description_available = True
            posted_date = detail["posted_date"]
            time.sleep(DETAIL_DELAY)

        postings.append(JobPosting(
            company=target.name,
            title=title,
            url=posting_url,
            location=location,
            department=department,
            description_text=description_text,
            ats_platform=target.ats_platform,
            posted_date=posted_date,
            description_available=description_available,
        ))

    return postings
