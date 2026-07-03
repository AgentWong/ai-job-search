"""
Dayforce HCM ATS fetcher

CSRF API:
    GET https://jobs.dayforcehcm.com/api/auth/csrf
    Response: { "csrfToken": "..." }
    Side effect: sets cookie `__Host-next-auth.csrf-token`.

Search API:
    POST https://jobs.dayforcehcm.com/api/geo/{namespace}/jobposting/search
    Required header: `X-CSRF-Token: {token}` (must match the cookie value
    before the URL-encoded `|`; obtained from the GET above).
    Body: { "clientNamespace", "jobBoardCode", "cultureCode": "en-US",
            "distanceUnit": 0, "paginationStart": N }
    Response: { "count", "offset", "maxCount",
                "jobPostings": [ { "jobPostingId", "jobTitle",
                                    "jobDescription" (HTML, inline — no
                                      separate detail fetch needed),
                                    "hasVirtualLocation",
                                    "postingStartTimestampUTC",
                                    "postingLocations": [{...}], ... } ] }

Slug format: "{clientNamespace}:{jobBoardCode}" — both parsed from the
career URL (e.g. paradigm:CANDIDATEPORTAL from
https://jobs.dayforcehcm.com/en-US/paradigm/CANDIDATEPORTAL).

`hasVirtualLocation` is reliable on most tenants but not all; we additionally
scan the description and the postingLocations list for remote keywords.

Cloudflare-fronted but does not enforce JS challenges — a browser-like
User-Agent and a single session (cookie jar) is sufficient.
"""

import html as html_module
import re
from datetime import datetime
from ..config import CompanyTarget, JobPosting
from .utils import make_session, retry_get, retry_post


CSRF_URL = "https://jobs.dayforcehcm.com/api/auth/csrf"
SEARCH_URL = "https://jobs.dayforcehcm.com/api/geo/{namespace}/jobposting/search"
JOB_URL_TEMPLATE = (
    "https://jobs.dayforcehcm.com/en-US/{namespace}/{board}/jobs/{job_id}"
)

DAYFORCE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

_HTML_TAG = re.compile(r"<[^>]+>")
_REMOTE_DESC = re.compile(r"\b(remote|work\s+from\s+home|wfh|virtual)\b", re.IGNORECASE)


def strip_html(text: str) -> str:
    decoded = html_module.unescape(text or "")
    return _HTML_TAG.sub(" ", decoded).strip()


def _split_slug(slug: str) -> tuple[str, str]:
    """Return (clientNamespace, jobBoardCode). Defaults board to CANDIDATEPORTAL."""
    if ":" in slug:
        ns, board = slug.split(":", 1)
        return ns.strip(), (board.strip() or "CANDIDATEPORTAL")
    return slug.strip(), "CANDIDATEPORTAL"


def _format_posted(raw: str) -> str:
    if not raw:
        return ""
    try:
        # Strip timezone for fromisoformat compatibility on older Pythons,
        # then take the date portion.
        cleaned = raw.replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned).date().isoformat()
    except ValueError:
        return raw[:10]


def _location_str(locations: list) -> str:
    if not locations:
        return ""
    parts = []
    for loc in locations:
        addr = loc.get("formattedAddress") if isinstance(loc, dict) else None
        if addr:
            parts.append(addr)
    return "; ".join(parts)


def _workplace_type(job: dict, description_text: str) -> str:
    if job.get("hasVirtualLocation") is True:
        return "remote"
    locs = job.get("postingLocations") or []
    for loc in locs:
        if not isinstance(loc, dict):
            continue
        addr = (loc.get("formattedAddress") or "").lower()
        if "remote" in addr or "virtual" in addr:
            return "remote"
    # Last-resort heuristic: description-text scan. Keep narrow — many
    # non-remote postings mention "remote" in pass-through copy (e.g.
    # "remote monitoring tools"), so we look for stronger phrases.
    if description_text:
        head = description_text[:1500].lower()
        if re.search(r"\b(100%\s+remote|fully\s+remote|remote-?first|work\s+from\s+home|wfh)\b", head):
            return "remote"
    return ""


def _csrf_token(session) -> str:
    data = retry_get(session, CSRF_URL)
    if isinstance(data, dict):
        return data.get("csrfToken", "") or ""
    return ""


def fetch_jobs(target: CompanyTarget) -> list[JobPosting]:
    namespace, board = _split_slug(target.board_token)
    if not namespace:
        return []

    session = make_session(extra_headers=DAYFORCE_HEADERS)
    session.headers.update({
        "Origin": "https://jobs.dayforcehcm.com",
        "Referer": f"https://jobs.dayforcehcm.com/en-US/{namespace}/{board}",
    })

    token = _csrf_token(session)
    if not token:
        return []
    session.headers.update({"X-CSRF-Token": token, "Content-Type": "application/json"})

    search_url = SEARCH_URL.format(namespace=namespace)
    pagination_start = 0
    seen_ids: set = set()
    postings: list[JobPosting] = []

    while True:
        payload = {
            "clientNamespace": namespace,
            "jobBoardCode": board,
            "cultureCode": "en-US",
            "distanceUnit": 0,
            "paginationStart": pagination_start,
        }
        data = retry_post(session, search_url, payload)
        if not isinstance(data, dict):
            break
        batch = data.get("jobPostings") or []
        max_count = int(data.get("maxCount") or 0)
        offset = int(data.get("offset") or pagination_start)
        count = int(data.get("count") or len(batch))

        for job in batch:
            job_id = job.get("jobPostingId")
            if job_id is None or job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            title = job.get("jobTitle", "") or ""
            description_text = strip_html(job.get("jobDescription", "") or "")
            postings.append(JobPosting(
                company=target.name,
                title=title,
                url=JOB_URL_TEMPLATE.format(namespace=namespace, board=board, job_id=job_id),
                location=_location_str(job.get("postingLocations") or []),
                department="",
                description_text=description_text,
                ats_platform=target.ats_platform,
                posted_date=_format_posted(job.get("postingStartTimestampUTC", "") or ""),
                workplace_type=_workplace_type(job, description_text),
                description_available=True,
            ))

        next_start = offset + count
        if not batch or count == 0 or next_start >= max_count:
            break
        pagination_start = next_start

    return postings
