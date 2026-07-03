"""
Greenhouse ATS fetcher

API: GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true
Response: { "jobs": [ { "id", "title", "location": {"name"}, "departments": [{"name"}],
                         "content" (HTML), "metadata", ... } ] }

HTML is entity-encoded; decode with html module.
"""

import html as html_module
import re
import requests
from ..config import CompanyTarget, JobPosting
from .utils import make_session, retry_get


BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"

_HTML_TAG = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    decoded = html_module.unescape(text or "")
    return _HTML_TAG.sub(" ", decoded).strip()


def fetch_jobs(target: CompanyTarget) -> list[JobPosting]:
    session = make_session()
    url = BASE_URL.format(token=target.board_token)
    data = retry_get(session, url)

    postings = []
    for job in data.get("jobs", []):
        location_obj = job.get("location", {}) or {}
        location = location_obj.get("name", "") or ""

        departments = job.get("departments", []) or []
        department = departments[0].get("name", "") if departments else ""

        raw_html = job.get("content", "") or ""
        description_text = strip_html(raw_html)

        apply_url = job.get("absolute_url", "") or ""

        postings.append(JobPosting(
            company=target.name,
            title=job.get("title", ""),
            url=apply_url,
            location=location,
            department=department,
            description_text=description_text,
            ats_platform=target.ats_platform,
            posted_date=job.get("updated_at", "") or "",
            description_available=True,
        ))

    return postings
