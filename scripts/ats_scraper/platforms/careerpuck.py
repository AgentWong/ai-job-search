"""
Careerpuck ATS fetcher

API:
    GET https://api.careerpuck.com/v1/public/job-boards/{company}
    Required headers: origin: https://app.careerpuck.com
                      referer: https://app.careerpuck.com/

Caveat: Careerpuck is often a front-end overlay on Greenhouse/Lever; each job
carries an `atsSourcePlatform` field. Caller should deduplicate against
underlying ATS scrapes — handled via the application_queue dedup check.

Response: { "jobBoard": {...},
             "jobs": [ { "id", "title", "description" (HTML), "location",
                         "atsSourcePlatform", "atsSourceUrl",
                         "department", "team", "employmentType",
                         "remote": bool, "workplaceType",
                         "publishedAt", "applicationUrl" } ] }
"""

import html as html_module
import re
from ..config import CompanyTarget, JobPosting
from .utils import make_session, retry_get


LIST_URL = "https://api.careerpuck.com/v1/public/job-boards/{slug}"

CAREERPUCK_HEADERS = {
    "Origin": "https://app.careerpuck.com",
    "Referer": "https://app.careerpuck.com/",
    "Accept": "application/json",
}

_HTML_TAG = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    decoded = html_module.unescape(text or "")
    return _HTML_TAG.sub(" ", decoded).strip()


def _workplace_type(job: dict) -> str:
    if job.get("remote") is True:
        return "remote"
    wt = (job.get("workplaceType") or job.get("workplace_type") or "").lower()
    if "remote" in wt:
        return "remote"
    if "hybrid" in wt:
        return "hybrid"
    if "onsite" in wt or "on-site" in wt:
        return "on-site"
    loc = (job.get("location") or "").lower()
    if "remote" in loc:
        return "remote"
    if "hybrid" in loc:
        return "hybrid"
    return ""


def _location_str(job: dict) -> str:
    loc = job.get("location")
    if isinstance(loc, str):
        return loc
    if isinstance(loc, dict):
        parts = [loc.get("city"), loc.get("state"), loc.get("country")]
        return ", ".join(p for p in parts if p)
    return ""


def _department(job: dict) -> str:
    for k in ("department", "team", "category"):
        v = job.get(k)
        if isinstance(v, dict):
            n = v.get("name") or v.get("label")
            if n:
                return n
        elif isinstance(v, str) and v:
            return v
    return ""


def fetch_jobs(target: CompanyTarget) -> list[JobPosting]:
    session = make_session(extra_headers=CAREERPUCK_HEADERS)
    url = LIST_URL.format(slug=target.board_token)
    data = retry_get(session, url)

    jobs = []
    if isinstance(data, dict):
        jobs = (
            data.get("jobs")
            or data.get("results")
            or data.get("data")
            or []
        )
    elif isinstance(data, list):
        jobs = data

    postings: list[JobPosting] = []
    for job in jobs:
        desc = strip_html(job.get("description", "") or "")
        # Prefer ATS source URL when present (links to the underlying job),
        # falling back to Careerpuck's own application URL.
        apply_url = (
            job.get("atsSourceUrl")
            or job.get("applicationUrl")
            or job.get("apply_url")
            or job.get("url")
            or ""
        )
        posted = (
            job.get("publishedAt")
            or job.get("published_at")
            or job.get("createdAt")
            or ""
        )[:10]

        postings.append(JobPosting(
            company=target.name,
            title=job.get("title", "") or "",
            url=apply_url,
            location=_location_str(job),
            department=_department(job),
            description_text=desc,
            ats_platform=target.ats_platform,
            compensation=job.get("employmentType", "") or "",
            posted_date=posted,
            workplace_type=_workplace_type(job),
            description_available=bool(desc),
        ))

    return postings
