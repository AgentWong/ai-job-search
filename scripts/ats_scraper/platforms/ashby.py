"""
Ashby ATS fetcher

API: GET https://api.ashbyhq.com/posting-api/job-board/{board_token}?includeCompensation=true
Response: { "jobs": [ { "id", "title", "location", "team", "isListed", "applyUrl",
                         "descriptionPlain", "compensation", "employmentType",
                         "isRemote", ... } ] }
"""

import time
import requests
from ..config import CompanyTarget, JobPosting
from .utils import make_session, retry_get


BASE_URL = "https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true"


def fetch_jobs(target: CompanyTarget) -> list[JobPosting]:
    session = make_session()
    url = BASE_URL.format(token=target.board_token)
    data = retry_get(session, url)

    postings = []
    for job in data.get("jobs", []):
        if not job.get("isListed", True):
            continue

        comp = job.get("compensation", {}) or {}
        comp_str = ""
        if comp:
            min_val = comp.get("minValue")
            max_val = comp.get("maxValue")
            currency = comp.get("currency", "USD")
            interval = comp.get("interval", "")
            if min_val and max_val:
                comp_str = f"{currency} {min_val}-{max_val}/{interval}"
            elif min_val:
                comp_str = f"{currency} {min_val}+/{interval}"

        workplace_type = "remote" if job.get("isRemote") else ""
        location = job.get("location", "") or ""

        # Strip /application suffix — it leads to the apply form, not the job posting
        raw_url = job.get("applyUrl", "") or ""
        if raw_url.endswith("/application"):
            raw_url = raw_url[: -len("/application")]

        postings.append(JobPosting(
            company=target.name,
            title=job.get("title", ""),
            url=raw_url,
            location=location,
            department=job.get("team", "") or "",
            description_text=job.get("descriptionPlain", "") or "",
            ats_platform=target.ats_platform,
            compensation=comp_str,
            posted_date=job.get("publishedAt", "") or "",
            workplace_type=workplace_type,
            description_available=True,
        ))

    return postings
