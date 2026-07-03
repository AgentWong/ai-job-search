"""
SmartRecruiters ATS fetcher

List API: GET https://api.smartrecruiters.com/v1/companies/{board_token}/postings
          ?limit=100&offset={n}
Response: { "totalFound": N, "content": [ { "id", "name" (title), "location": {...},
             "department": {"label"}, "releasedDate" } ] }

Detail API: GET https://api.smartrecruiters.com/v1/companies/{board_token}/postings/{id}
Response: { "jobAd": { "sections": { "jobDescription": { "text" } } },
             "workplace": { "workplaceType" } }

Optimization: title-filter before fetching details.
"""

import time
import requests
from ..config import CompanyTarget, JobPosting
from ..filters import title_passes
from .utils import make_session, retry_get


LIST_URL = "https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=100&offset={offset}"
DETAIL_URL = "https://api.smartrecruiters.com/v1/companies/{token}/postings/{job_id}"
DETAIL_DELAY = 0.3


def _location_str(loc: dict) -> str:
    if not loc:
        return ""
    parts = []
    if loc.get("city"):
        parts.append(loc["city"])
    if loc.get("region"):
        parts.append(loc["region"])
    if loc.get("country"):
        parts.append(loc.get("countryCode", loc["country"]))
    remote = loc.get("remote")
    if remote:
        parts.insert(0, "Remote")
    return ", ".join(parts)


def fetch_jobs(target: CompanyTarget) -> list[JobPosting]:
    session = make_session()
    postings = []
    offset = 0

    # Collect candidates from list (title-filter only)
    candidates = []
    while True:
        url = LIST_URL.format(token=target.board_token, offset=offset)
        data = retry_get(session, url)
        content = data.get("content", [])
        total = data.get("totalFound", 0)

        for job in content:
            title = job.get("name", "") or ""
            if title_passes(title):
                candidates.append(job)

        offset += len(content)
        if not content or offset >= total:
            break
        time.sleep(0.2)

    # Fetch details for candidates only
    for job in candidates:
        job_id = job.get("id", "")
        title = job.get("name", "") or ""
        location = _location_str(job.get("location", {}) or {})
        dept = (job.get("department", {}) or {}).get("label", "") or ""
        posted = job.get("releasedDate", "") or ""

        # Build apply URL
        apply_url = f"https://jobs.smartrecruiters.com/{target.board_token}/{job_id}"

        description_text = ""
        workplace_type = ""

        try:
            detail_url = DETAIL_URL.format(token=target.board_token, job_id=job_id)
            detail = retry_get(session, detail_url)
            job_ad = detail.get("jobAd", {}) or {}
            sections = job_ad.get("sections", {}) or {}
            job_desc = sections.get("jobDescription", {}) or {}
            description_text = job_desc.get("text", "") or ""

            workplace = detail.get("workplace", {}) or {}
            workplace_type = workplace.get("workplaceType", "") or ""
            time.sleep(DETAIL_DELAY)
        except Exception:
            pass

        postings.append(JobPosting(
            company=target.name,
            title=title,
            url=apply_url,
            location=location,
            department=dept,
            description_text=description_text,
            ats_platform=target.ats_platform,
            posted_date=posted,
            workplace_type=workplace_type,
            description_available=True,
        ))

    return postings
