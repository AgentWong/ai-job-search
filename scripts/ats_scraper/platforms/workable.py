"""
Workable ATS fetcher

Workable's documented API (`workable.com/spi/v3/...`) requires a per-account
Bearer token. This fetcher instead hits the three unauthenticated endpoints
that power Workable's public career-widget; they accept the company's slug
(its Workable subdomain) with no credentials.

Endpoints, tried in order; the first that returns HTTP 200 wins:
  1. GET  https://www.workable.com/api/accounts/{slug}?details=true
  2. GET  https://apply.workable.com/api/v1/widget/accounts/{slug}
  3. POST https://apply.workable.com/api/v3/accounts/{slug}/jobs
         body: {"query":"","location":[],"department":[],"worktype":[],"remote":[]}

The three endpoints return different envelope shapes (job arrays appear
under varying keys), so jobs are located by walking the JSON for arrays of
objects that have a title + shortcode/code/id/url — the same heuristic the
reference JS implementation uses.
"""

import html as html_module
import re
import requests
from ..config import CompanyTarget, JobPosting
from .utils import make_session


ENDPOINTS = [
    {
        "name": "public-account",
        "method": "GET",
        "url": "https://www.workable.com/api/accounts/{slug}?details=true",
        "body": None,
    },
    {
        "name": "widget-account",
        "method": "GET",
        "url": "https://apply.workable.com/api/v1/widget/accounts/{slug}",
        "body": None,
    },
    {
        "name": "v3-account-jobs",
        "method": "POST",
        "url": "https://apply.workable.com/api/v3/accounts/{slug}/jobs",
        "body": {"query": "", "location": [], "department": [], "worktype": [], "remote": []},
    },
]

_HTML_TAG = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    decoded = html_module.unescape(text or "")
    return _HTML_TAG.sub(" ", decoded).strip()


def _looks_like_job(value) -> bool:
    if not isinstance(value, dict):
        return False
    has_title = bool(value.get("title") or value.get("full_title"))
    has_id = bool(
        value.get("shortcode")
        or value.get("code")
        or value.get("id")
        or value.get("url")
        or value.get("application_url")
    )
    return has_title and has_id


def _collect_jobs(value, jobs: list, seen: set) -> list:
    """Recursively find arrays of job-shaped objects anywhere in the response."""
    if value is None:
        return jobs
    if isinstance(value, list):
        if any(_looks_like_job(item) for item in value):
            for item in value:
                if not _looks_like_job(item):
                    continue
                key = (
                    item.get("shortcode")
                    or item.get("code")
                    or item.get("id")
                    or item.get("url")
                )
                if key in seen:
                    continue
                seen.add(key)
                jobs.append(item)
            return jobs
        for item in value:
            _collect_jobs(item, jobs, seen)
        return jobs
    if isinstance(value, dict):
        for nested in value.values():
            _collect_jobs(nested, jobs, seen)
    return jobs


def _readable_location(value) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "; ".join(filter(None, (_readable_location(v) for v in value)))
    if isinstance(value, dict):
        parts = [
            value.get("city"),
            value.get("region"),
            value.get("state"),
            value.get("country"),
            value.get("name"),
        ]
        return ", ".join(p for p in parts if p)
    return ""


def _account_name(data: dict, slug: str) -> str:
    if not isinstance(data, dict):
        return slug
    account = data.get("account") or {}
    company = data.get("company") or {}
    return (
        data.get("name")
        or company.get("name")
        or account.get("name")
        or account.get("company_name")
        or slug
    )


def _normalize(job: dict, company: str, slug: str) -> JobPosting:
    shortcode = job.get("shortcode") or job.get("code") or job.get("id")
    url = (
        job.get("url")
        or job.get("application_url")
        or job.get("apply_url")
        or (f"https://apply.workable.com/j/{shortcode}" if shortcode else f"https://apply.workable.com/{slug}")
    )

    description_parts = [
        job.get("description"),
        job.get("description_html"),
        job.get("full_description"),
        job.get("requirements"),
    ]
    description_text = _strip_html("\n\n".join(p for p in description_parts if p))

    location = _readable_location(
        job.get("location") or job.get("locations") or job.get("city") or job.get("country")
    )

    workplace_type = ""
    if job.get("remote") is True or job.get("telecommuting") is True:
        workplace_type = "remote"

    salary = job.get("salary") or {}
    compensation = ""
    if isinstance(salary, dict):
        min_v = salary.get("salary_from") or salary.get("min")
        max_v = salary.get("salary_to") or salary.get("max")
        currency = salary.get("salary_currency") or salary.get("currency") or "USD"
        if min_v and max_v:
            compensation = f"{currency} {min_v}-{max_v}"
        elif min_v:
            compensation = f"{currency} {min_v}+"

    department = job.get("department") or job.get("department_hierarchy") or ""
    if isinstance(department, list):
        department = department[0] if department else ""
    if isinstance(department, dict):
        department = department.get("name") or ""

    posted_date = (
        job.get("created_at")
        or job.get("published_at")
        or job.get("published")
        or job.get("updated_at")
        or ""
    )

    return JobPosting(
        company=company,
        title=job.get("title") or job.get("full_title") or "",
        url=url,
        location=location,
        department=department or "",
        description_text=description_text,
        ats_platform="workable",
        compensation=compensation,
        posted_date=posted_date,
        workplace_type=workplace_type,
        description_available=bool(description_text),
    )


def _try_endpoint(session: requests.Session, endpoint: dict, slug: str) -> dict | None:
    url = endpoint["url"].format(slug=slug)
    try:
        if endpoint["method"] == "POST":
            resp = session.post(url, json=endpoint["body"], timeout=15)
        else:
            resp = session.get(url, timeout=15)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    try:
        return resp.json()
    except ValueError:
        return None


def fetch_jobs(target: CompanyTarget) -> list[JobPosting]:
    session = make_session(extra_headers={"Content-Type": "application/json"})
    slug = target.board_token

    data = None
    for endpoint in ENDPOINTS:
        data = _try_endpoint(session, endpoint, slug)
        if data is not None:
            break

    if data is None:
        raise RuntimeError(f"All Workable endpoints failed for slug '{slug}'")

    company_name = target.name or _account_name(data, slug)
    raw_jobs = _collect_jobs(data, [], set())
    return [_normalize(job, company_name, slug) for job in raw_jobs]
