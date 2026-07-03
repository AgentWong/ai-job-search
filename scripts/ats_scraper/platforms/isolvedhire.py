"""
iSolvedHire (ApplicantPro) ATS fetcher

Public career sites are served at https://{subdomain}.isolvedhire.com. The Vue
career-site front end (`applicant-pro-components.js`) drives two unauthenticated
JSON endpoints keyed by a numeric *domain id* (the internal site id, distinct
from the subdomain):

  List:   GET https://{subdomain}.isolvedhire.com/core/jobs/{domain_id}?getParams={}
          -> { "success", "data": { "jobs": [ { "id", "title", "jobLocation",
                 "workplaceType", "employmentType", "minSalary", "maxSalary",
                 "payTypeFrame", "startDateRef", "jobUrl", ... } ], "jobCount" } }
          Returns every open posting in one call (no pagination). `getParams`
          is a required query arg the controller JSON-decodes; `{}` is accepted
          and yields the full unfiltered list.

  Detail: GET https://{subdomain}.isolvedhire.com/core/jobs/{domain_id}/{job_id}/job-details
          -> { "success", "data": { "description" (HTML), "advertisingDescription"
                 (plain text), "title", ... } }
          The list response carries no description, so each kept candidate needs
          one detail call (Workday-style two-phase fetch).

board_token (CSV `ATS_Slug`) is the subdomain, optionally `subdomain:domain_id`
to pin the numeric id and skip resolution. When only the subdomain is given the
domain id is parsed from the `/jobs/` page (the front end embeds
`domainId : NNNN` in its bootstrap script).
"""

import html as html_module
import re
import time
from datetime import datetime
from ..config import CompanyTarget, JobPosting
from ..filters import title_passes
from .utils import make_session, retry_get


LIST_URL = "https://{sub}.isolvedhire.com/core/jobs/{domain_id}"
DETAIL_URL = "https://{sub}.isolvedhire.com/core/jobs/{domain_id}/{job_id}/job-details"
JOBS_PAGE_URL = "https://{sub}.isolvedhire.com/jobs/"

# iSolvedHire serves HTML pages with a browser User-Agent; the JSON endpoints are
# happy with anything, but match the rest of the scraper's browser-like header.
ISOLVED_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

_HTML_TAG = re.compile(r"<[^>]+>")
_DOMAIN_ID_RE = re.compile(r"domainId\s*:\s*(\d+)")
DETAIL_DELAY = 0.3


def strip_html(text: str) -> str:
    decoded = html_module.unescape(text or "")
    return _HTML_TAG.sub(" ", decoded).replace("\xa0", " ")


def _normalize_workplace_type(raw: str) -> str:
    value = (raw or "").lower()
    if not value:
        return ""
    if "remote" in value:
        return "remote"
    if "hybrid" in value or "flexib" in value or "work from home" in value:
        return "hybrid"
    if "office" in value or "site" in value or "person" in value:
        return "on-site"
    return ""


def _parse_posted_date(raw: str) -> str:
    """Parse iSolvedHire's startDateRef into ISO (YYYY-MM-DD); "" if unparseable.

    Seen formats: "Apr 27, 2026" (list endpoint), "06-Apr-2026" (detail endpoint).
    """
    raw = (raw or "").strip()
    if not raw:
        return ""
    for fmt in ("%b %d, %Y", "%d-%b-%Y", "%B %d, %Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def _build_compensation(job: dict) -> str:
    min_s = (job.get("minSalary") or "").strip()
    max_s = (job.get("maxSalary") or "").strip()
    frame = (job.get("payTypeFrame") or "").strip()
    if min_s and max_s:
        amount = f"${min_s}-${max_s}"
    elif min_s:
        amount = f"${min_s}+"
    elif max_s:
        amount = f"up to ${max_s}"
    else:
        return ""
    return f"{amount} {frame}".strip()


def _resolve_domain_id(session, subdomain: str) -> str:
    """Parse the numeric domain id from a subdomain's public /jobs/ page."""
    url = JOBS_PAGE_URL.format(sub=subdomain)
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    match = _DOMAIN_ID_RE.search(resp.text)
    if not match:
        raise RuntimeError(f"could not resolve iSolvedHire domain id from {url}")
    return match.group(1)


def fetch_jobs(target: CompanyTarget) -> list[JobPosting]:
    session = make_session(extra_headers=ISOLVED_HEADERS)

    token = target.board_token.strip()
    if ":" in token:
        subdomain, domain_id = (p.strip() for p in token.split(":", 1))
    else:
        subdomain, domain_id = token, ""
    if not domain_id:
        domain_id = _resolve_domain_id(session, subdomain)

    list_url = LIST_URL.format(sub=subdomain, domain_id=domain_id)
    data = retry_get(session, list_url, params={"getParams": "{}"})
    jobs = ((data or {}).get("data") or {}).get("jobs") or []

    postings = []
    for job in jobs:
        title = job.get("title", "") or ""
        if not title_passes(title):
            continue

        job_id = job.get("id")
        description_text = ""
        if job_id is not None:
            try:
                detail_url = DETAIL_URL.format(
                    sub=subdomain, domain_id=domain_id, job_id=job_id
                )
                detail = retry_get(session, detail_url)
                info = (detail or {}).get("data") or {}
                description_text = strip_html(info.get("description", "") or "")
                if not description_text:
                    description_text = (info.get("advertisingDescription", "") or "").strip()
                time.sleep(DETAIL_DELAY)
            except Exception:
                pass

        postings.append(JobPosting(
            company=target.name,
            title=title,
            url=job.get("jobUrl", "") or "",
            location=job.get("jobLocation", "") or "",
            department=job.get("orgTitle", "") or "",
            description_text=description_text,
            ats_platform=target.ats_platform,
            compensation=_build_compensation(job),
            posted_date=_parse_posted_date(job.get("startDateRef", "")),
            workplace_type=_normalize_workplace_type(job.get("workplaceType", "")),
            description_available=True,
        ))

    return postings
