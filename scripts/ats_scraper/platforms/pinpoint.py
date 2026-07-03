"""
Pinpoint ATS fetcher

API: GET https://{board_token}.pinpointhq.com/postings.json
Response: { "data": [ { "id", "title", "url", "workplace_type", "employment_type",
                         "description" (HTML), "key_responsibilities" (HTML),
                         "skills_knowledge_expertise" (HTML),
                         "job": { "department": { "name" } },
                         "location": { "city", "name" }, ... } ] }

No posted_at date field available in the public API.
"""

import html as html_module
import re
from ..config import CompanyTarget, JobPosting
from .utils import make_session, retry_get


BASE_URL = "https://{token}.pinpointhq.com/postings.json"

_HTML_TAG = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    decoded = html_module.unescape(text or "")
    return _HTML_TAG.sub(" ", decoded).strip()


def fetch_jobs(target: CompanyTarget) -> list[JobPosting]:
    session = make_session()
    url = BASE_URL.format(token=target.board_token)
    data = retry_get(session, url)

    postings = []
    for posting in data.get("data", []) or []:
        description = strip_html(posting.get("description", "") or "")
        responsibilities = strip_html(posting.get("key_responsibilities", "") or "")
        skills = strip_html(posting.get("skills_knowledge_expertise", "") or "")
        combined = " ".join(p for p in (description, responsibilities, skills) if p)

        location_obj = posting.get("location") or {}
        location = location_obj.get("name") or location_obj.get("city") or ""

        job_obj = posting.get("job") or {}
        dept_obj = job_obj.get("department") or {}
        department = dept_obj.get("name") or ""

        workplace_raw = posting.get("workplace_type") or ""
        if workplace_raw == "remote":
            workplace_type = "remote"
        elif workplace_raw == "hybrid":
            workplace_type = "hybrid"
        elif workplace_raw == "onsite":
            workplace_type = "on-site"
        else:
            workplace_type = ""

        postings.append(JobPosting(
            company=target.name,
            title=posting.get("title", "") or "",
            url=posting.get("url", "") or "",
            location=location,
            department=department,
            description_text=combined,
            ats_platform=target.ats_platform,
            posted_date="",
            workplace_type=workplace_type,
            description_available=True,
        ))

    return postings
