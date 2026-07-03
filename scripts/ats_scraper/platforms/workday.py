"""
Workday ATS fetcher

Search API: POST https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{board}/jobs
Body: { "appliedFacets": {}, "limit": 20, "offset": N, "searchText": "" }
Response: { "total": N, "jobPostings": [ { "title", "externalPath", "locationsText",
              "postedOn", "bulletFields": ["Remote"] } ] }

Detail API: GET https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{board}/jobs/{path}
Response: { "jobPostingInfo": { "jobDescription" (HTML), "location", "jobReqId" } }

Requires browser-like User-Agent.
Title-filter before fetching details.
"""

import re
import time
import html as html_module
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
import requests
from ..config import CompanyTarget, JobPosting
from ..filters import title_passes
from .utils import make_session, retry_post, retry_get


SEARCH_URL = "https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{board}/jobs"
DETAIL_URL = "https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{board}{path}"

WORKDAY_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/json",
    "Accept": "application/json",
}

_HTML_TAG = re.compile(r"<[^>]+>")
DETAIL_DELAY = 0.4

_POSTED_DAYS_AGO = re.compile(r"posted\s+(\d+)\s*\+?\s*days?\s+ago", re.IGNORECASE)
_POSTED_TODAY = re.compile(r"posted\s+today", re.IGNORECASE)
_POSTED_YESTERDAY = re.compile(r"posted\s+yesterday", re.IGNORECASE)
_POSTED_30_PLUS = re.compile(r"posted\s+30\s*\+\s*days?\s+ago", re.IGNORECASE)


def strip_html(text: str) -> str:
    decoded = html_module.unescape(text or "")
    return _HTML_TAG.sub(" ", decoded).strip()


# Leading locale segment in a public Workday URL (/en-US/, /de-DE/, ...).
_URL_LOCALE = re.compile(r"^[a-z]{2}-[a-z]{2}$", re.IGNORECASE)


def cxs_detail_url(public_url: str) -> str:
    """Map a public Workday job URL to its CXS JSON detail endpoint.

    Workday is a JS SPA, so Firecrawl scrapes only nav chrome for a public
    `/{locale}/{board}/job/...` URL — no job description. But the same posting's
    description is served verbatim by the (public, unauthenticated) CXS API:

        public:  https://{tenant}.{dc}.myworkdayjobs.com/en-US/{board}/job/{slug}
        cxs:     https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{board}/job/{slug}

    The path after the board (`/job/...`, with or without a location segment) is
    mirrored unchanged — the CXS endpoint accepts whatever `/job/<...>` path the
    public URL carried. `{tenant}` is the first hostname label. Returns "" if the
    URL is not a parseable myworkdayjobs.com posting (no `/job/` segment).
    """
    try:
        parsed = urlparse(public_url)
    except ValueError:
        return ""
    host = (parsed.hostname or "").lower()
    if not host.endswith("myworkdayjobs.com"):
        return ""
    tenant = host.split(".")[0]
    parts = [p for p in parsed.path.split("/") if p]
    # Strip a leading locale segment (en-US, de-DE, ...) if present.
    if parts and _URL_LOCALE.match(parts[0]):
        parts = parts[1:]
    # Remaining: [board, 'job', <location?>, <slug>]. Need the board + a /job/ tail.
    if len(parts) < 2 or "job" not in parts[1:]:
        return ""
    board = parts[0]
    job_idx = parts.index("job", 1)
    tail = "/".join(parts[job_idx:])
    return f"https://{host}/wday/cxs/{tenant}/{board}/{tail}"


def fetch_description_from_url(public_url: str, session: requests.Session | None = None) -> dict:
    """Fetch the job description for a single public Workday URL via the CXS API.

    Used by ats-platform-search to backfill descriptions for Workday results that
    Firecrawl could not render (the board's only `no_description` source). Returns
    {"description": <plain text>, "location": <str>} — both "" on any failure, so
    the caller falls through to its existing no_description gate. Never raises.
    """
    out = {"description": "", "location": ""}
    cxs = cxs_detail_url(public_url)
    if not cxs:
        return out
    own_session = session is None
    if own_session:
        session = make_session(extra_headers=WORKDAY_HEADERS)
    try:
        detail = retry_get(session, cxs)
        info = (detail or {}).get("jobPostingInfo", {}) or {}
        out["description"] = strip_html(info.get("jobDescription", "") or "")
        out["location"] = info.get("location", "") or ""
    except Exception:
        pass
    return out


def normalize_posted_on(raw: str) -> str:
    """Convert Workday's relative posted-on phrases to an ISO date (UTC).

    "Posted 30+ Days Ago" sentinel maps to today-31 days so it always fails
    a `past_month` (30-day) cutoff. Unrecognized strings return "" so the
    central date filter treats them as missing data.
    """
    if not raw:
        return ""
    today = datetime.now(timezone.utc).date()
    if _POSTED_30_PLUS.search(raw):
        return (today - timedelta(days=31)).isoformat()
    m = _POSTED_DAYS_AGO.search(raw)
    if m:
        return (today - timedelta(days=int(m.group(1)))).isoformat()
    if _POSTED_YESTERDAY.search(raw):
        return (today - timedelta(days=1)).isoformat()
    if _POSTED_TODAY.search(raw):
        return today.isoformat()
    return ""


def fetch_jobs(target: CompanyTarget) -> list[JobPosting]:
    session = make_session(extra_headers=WORKDAY_HEADERS)

    tenant = target.workday_tenant
    dc = target.workday_datacenter
    board = target.workday_board_name

    search_url = SEARCH_URL.format(tenant=tenant, dc=dc, board=board)

    candidates = []
    offset = 0

    while True:
        payload = {"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": ""}
        data = retry_post(session, search_url, payload)
        total = data.get("total", 0)
        postings_raw = data.get("jobPostings", [])

        for job in postings_raw:
            title = job.get("title", "") or ""
            if title_passes(title):
                candidates.append(job)

        offset += len(postings_raw)
        if not postings_raw or offset >= total:
            break
        time.sleep(0.3)

    # Fetch details for candidates
    postings = []
    for job in candidates:
        title = job.get("title", "") or ""
        external_path = job.get("externalPath", "") or ""
        locations_text = job.get("locationsText", "") or ""
        posted_on = job.get("postedOn", "") or ""
        bullet_fields = job.get("bulletFields", []) or []
        workplace_type = "remote" if any("remote" in str(b).lower() for b in bullet_fields) else ""

        # Build apply URL — Workday's working public form is
        # /en-US/{board}/details/{slug}, where {slug} is the trailing segment
        # of externalPath (e.g. "/job/Remote-USA/Cloud-Engineer-II_JR100063-1"
        # → "Cloud-Engineer-II_JR100063-1"). The earlier "/job{external_path}"
        # form yields "/job/job/.../Slug" which 404s.
        slug = external_path.rsplit("/", 1)[-1] if external_path else ""
        apply_url = f"https://{tenant}.{dc}.myworkdayjobs.com/en-US/{board}/details/{slug}"

        description_text = ""
        if external_path:
            try:
                detail_url = DETAIL_URL.format(tenant=tenant, dc=dc, board=board, path=external_path)
                detail = retry_get(session, detail_url)
                info = detail.get("jobPostingInfo", {}) or {}
                raw_html = info.get("jobDescription", "") or ""
                description_text = strip_html(raw_html)
                # Prefer more specific location from detail if available. Multi-location
                # postings only put ONE city in `location` (e.g. "Salt Lake City, UT")
                # but list the rest — including ones that ARE the target metro — in
                # `additionalLocations`. Join all of them pipe-separated (the shape
                # location_matches_metro() already splits on) so local-mode matching
                # sees every listed city, not just the first.
                detail_location = info.get("location", "") or ""
                additional_locations = info.get("additionalLocations", []) or []
                all_locations = [loc for loc in [detail_location, *additional_locations] if loc]
                if all_locations:
                    locations_text = "|".join(all_locations)
                time.sleep(DETAIL_DELAY)
            except Exception:
                pass

        postings.append(JobPosting(
            company=target.name,
            title=title,
            url=apply_url,
            location=locations_text,
            department="",
            description_text=description_text,
            ats_platform=target.ats_platform,
            posted_date=normalize_posted_on(posted_on),
            workplace_type=workplace_type,
            description_available=True,
        ))

    return postings
