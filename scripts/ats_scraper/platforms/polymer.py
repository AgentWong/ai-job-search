"""
Polymer ATS fetcher

Public documented API.

List API:
    GET https://api.polymer.co/v1/hire/organizations/{slug}/jobs
    Headers: Origin/Referer https://www.polymerhq.io
    Response: { "items": [ { "id", "title", "description" (HTML),
                              "display_location", "location_type",
                              "remote_restriction_country_list": ["US","CA"],
                              "department" | "team", "employment_type",
                              "salary_min", "salary_max", "salary_currency",
                              "apply_url" | "url", "created_at" } ],
                 "meta": { "total", "is_last", "page", "next_page",
                           "count", "organization_name" } }

Empty: items=[]. Missing org: HTTP 422 "no careers_page found".
"""

import html as html_module
import re
import time
from ..config import CompanyTarget, JobPosting
from .utils import make_session, retry_get


LIST_URL = "https://api.polymer.co/v1/hire/organizations/{slug}/jobs"

POLYMER_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Origin": "https://www.polymerhq.io",
    "Referer": "https://www.polymerhq.io/",
}

_HTML_TAG = re.compile(r"<[^>]+>")
PAGE_DELAY = 0.2


def strip_html(text: str) -> str:
    decoded = html_module.unescape(text or "")
    return _HTML_TAG.sub(" ", decoded).strip()


def _workplace_type(job: dict) -> str:
    lt = (job.get("location_type") or "").lower()
    disp = (job.get("display_location") or "").lower()
    if "remote" in lt or "remote" in disp:
        return "remote"
    if "hybrid" in lt or "hybrid" in disp:
        return "hybrid"
    if lt in ("onsite", "on-site", "on site"):
        return "on-site"
    return ""


def _location_str(job: dict) -> str:
    if job.get("display_location"):
        return job["display_location"]
    countries = job.get("remote_restriction_country_list") or []
    if isinstance(countries, list) and countries:
        return f"Remote ({', '.join(countries)})"
    parts = [job.get("city"), job.get("state"), job.get("country")]
    return ", ".join(p for p in parts if p)


def _compensation(job: dict) -> str:
    smin = job.get("salary_min")
    smax = job.get("salary_max")
    cur = job.get("salary_currency") or ""
    if smin and smax:
        return f"{cur}{smin}-{smax}".strip()
    if smin:
        return f"{cur}{smin}+".strip()
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
    session = make_session(extra_headers=POLYMER_HEADERS)
    url: str | None = LIST_URL.format(slug=target.board_token)

    postings: list[JobPosting] = []
    while url:
        try:
            data = retry_get(session, url)
        except RuntimeError:
            # 422 "no careers_page found" comes through as a retried failure;
            # treat unknown orgs as empty rather than raising.
            return postings

        items = []
        meta = {}
        if isinstance(data, dict):
            items = data.get("items") or data.get("jobs") or data.get("results") or []
            meta = data.get("meta") or {}
        elif isinstance(data, list):
            items = data

        for job in items:
            desc = strip_html(job.get("description", "") or "")
            apply_url = (
                job.get("apply_url")
                or job.get("url")
                or job.get("hosted_url")
                or job.get("public_url")
                or ""
            )
            posted = (
                job.get("created_at")
                or job.get("published_at")
                or job.get("posted_at")
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
                compensation=_compensation(job),
                posted_date=posted,
                workplace_type=_workplace_type(job),
                description_available=bool(desc),
            ))

        if meta.get("is_last") or not meta.get("next_page"):
            break
        # `next_page` is a 1-based page number; build the next URL.
        url = (
            f"{LIST_URL.format(slug=target.board_token)}"
            f"?page={meta['next_page']}"
        )
        time.sleep(PAGE_DELAY)

    return postings
