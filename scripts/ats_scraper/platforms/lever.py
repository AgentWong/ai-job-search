"""
Lever ATS fetcher

API: GET https://api.lever.co/v0/postings/{board_token}?mode=json&skip={n}&limit=25
Pagination: fetch until response is empty list.
Response item: { "id", "text" (title), "categories": {"location", "department", "team"},
                  "descriptionPlain", "additionalPlain", "workplaceType",
                  "createdAt" (epoch ms), "hostedUrl" }
"""

import time
import requests
from ..config import CompanyTarget, JobPosting
from .utils import make_session, retry_get


BASE_URL = "https://api.lever.co/v0/postings/{token}?mode=json&skip={skip}&limit=25"
DETAIL_DELAY = 0.2


def fetch_jobs(target: CompanyTarget) -> list[JobPosting]:
    session = make_session()
    postings = []
    skip = 0

    while True:
        url = BASE_URL.format(token=target.board_token, skip=skip)
        data = retry_get(session, url)

        if not data:
            break

        for job in data:
            cats = job.get("categories", {}) or {}
            location = cats.get("location", "") or ""
            department = cats.get("department", "") or cats.get("team", "") or ""

            desc = (job.get("descriptionPlain", "") or "") + " " + (job.get("additionalPlain", "") or "")
            desc = desc.strip()

            workplace_type = job.get("workplaceType", "") or ""

            created_ms = job.get("createdAt")
            posted_date = ""
            if created_ms:
                import datetime
                posted_date = datetime.datetime.fromtimestamp(
                    created_ms / 1000, tz=datetime.timezone.utc
                ).strftime("%Y-%m-%d")

            postings.append(JobPosting(
                company=target.name,
                title=job.get("text", ""),
                url=job.get("hostedUrl", "") or "",
                location=location,
                department=department,
                description_text=desc,
                ats_platform=target.ats_platform,
                posted_date=posted_date,
                workplace_type=workplace_type,
                description_available=True,
            ))

        if len(data) < 25:
            break
        skip += len(data)
        time.sleep(DETAIL_DELAY)

    return postings
