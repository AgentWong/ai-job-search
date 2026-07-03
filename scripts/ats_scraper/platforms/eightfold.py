"""
Eightfold ATS fetcher

Anonymous-but-undocumented JSON API. Customers include American Express,
Starbucks, Citi, HSBC, AstraZeneca, Qualcomm, Bayer.

List API:
    GET https://{subdomain}.eightfold.ai/api/apply/v2/jobs
        ?domain={domain}&hl=en&start={n}&num={page_size}&pid=&domainName=true&sort_by=relevance
    Response: { "count": N,
                 "positions": [ { "id", "name", "location", "locations",
                                   "department", "business_unit", "type",
                                   "canonicalPositionUrl", "t_create" (epoch s),
                                   "work_location_option" ("remote"|"onsite"|"hybrid"),
                                   "job_description": null /* populated by detail API */ } ] }

Detail API:
    GET https://{subdomain}.eightfold.ai/api/apply/v2/jobs/{id}?domain={domain}
    Response: same fields plus a populated `job_description` (HTML),
              `apply_redirect_url`, `custom_JD`.

ATS_Slug format: "{subdomain}" or "{subdomain}|{domain}".
If only subdomain is given, domain defaults to "{subdomain}.com".

Some tenants reject anonymous calls with `403 "Not authorized for PCSX"` —
those have moved to the gated PCSX search and are not scrapable here.
List-side title filtering keeps detail calls bounded.
"""

import html as html_module
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote

import requests

from ..config import CompanyTarget, JobPosting
from ..filters import title_passes
from .utils import make_session, retry_get


class GatedTenantError(Exception):
    """Raised when an Eightfold tenant has moved to gated PCSX search."""


LIST_URL = (
    "https://{sub}.eightfold.ai/api/apply/v2/jobs"
    "?domain={domain}&hl=en&start={start}&num={num}&pid=&domainName=true"
    "&sort_by=relevance&query={query}"
)
DETAIL_URL = "https://{sub}.eightfold.ai/api/apply/v2/jobs/{job_id}?domain={domain}"
# Anonymous Eightfold caps page size at 10 regardless of `num`.
PAGE_SIZE = 10
# Each enterprise tenant may post thousands of jobs; bound the per-keyword
# scan so a single tenant doesn't dominate the run.
MAX_PAGES_PER_QUERY = 8

# Keyword queries against the relevance-ranked search. Title regex applies
# next, so over-fetching unrelated roles is fine — under-fetching by missing
# a keyword is what we're avoiding.
SEARCH_QUERIES = (
    "DevOps",
    "Site Reliability",
    "Platform Engineer",
    "Cloud Engineer",
    "Infrastructure Engineer",
    "Systems Engineer",
)

EIGHTFOLD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

_HTML_TAG = re.compile(r"<[^>]+>")
PAGE_DELAY = 0.3
DETAIL_DELAY = 0.4


def strip_html(text: str) -> str:
    decoded = html_module.unescape(text or "")
    return _HTML_TAG.sub(" ", decoded).strip()


def _split_slug(slug: str) -> tuple[str, str]:
    """Return (subdomain, domain). Defaults domain to '{sub}.com' when omitted."""
    if "|" in slug:
        sub, domain = slug.split("|", 1)
        return sub.strip(), domain.strip()
    sub = slug.strip()
    return sub, f"{sub}.com" if sub else ""


def _location_str(pos: dict) -> str:
    loc = pos.get("location") or pos.get("location_name") or ""
    if isinstance(loc, str) and loc:
        return loc
    locations = pos.get("locations")
    if isinstance(locations, list) and locations:
        first = locations[0]
        if isinstance(first, dict):
            parts = [first.get("city"), first.get("state"), first.get("country")]
            return ", ".join(p for p in parts if p)
        if isinstance(first, str):
            return first
    return ""


def _workplace_type(pos: dict) -> str:
    wlo = (pos.get("work_location_option") or "").lower()
    if "remote" in wlo:
        return "remote"
    if "hybrid" in wlo:
        return "hybrid"
    if "onsite" in wlo or "on-site" in wlo or "on site" in wlo:
        return "on-site"
    if pos.get("is_remote") is True:
        return "remote"
    loc = (_location_str(pos) or "").lower()
    if "remote" in loc:
        return "remote"
    return ""


def _format_posted(raw) -> str:
    if not raw:
        return ""
    if isinstance(raw, (int, float)):
        ts = int(raw)
        if ts > 10_000_000_000:
            ts = ts // 1000
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, OSError):
            return ""
    if isinstance(raw, str):
        return raw[:10]
    return ""


def _department(pos: dict) -> str:
    for k in ("department", "business_unit", "team"):
        v = pos.get(k)
        if isinstance(v, str) and v:
            return v
        if isinstance(v, dict):
            n = v.get("name") or v.get("label")
            if n:
                return n
    return ""


def _probe_tenant(session: requests.Session, sub: str, domain: str) -> None:
    """Single non-retried call to detect gated PCSX tenants (permanent 403)."""
    probe_url = LIST_URL.format(
        sub=sub, domain=domain, start=0, num=PAGE_SIZE, query="",
    )
    resp = session.get(probe_url, timeout=30)
    if resp.status_code == 403:
        try:
            body = resp.json()
        except ValueError:
            body = {}
        msg = body.get("message", "") if isinstance(body, dict) else ""
        if "PCSX" in msg or "Not authorized" in msg:
            raise GatedTenantError(f"{sub}.eightfold.ai is gated (PCSX): {msg}")


def fetch_jobs(target: CompanyTarget) -> list[JobPosting]:
    sub, domain = _split_slug(target.board_token)
    if not sub or not domain:
        return []

    session = make_session(extra_headers=EIGHTFOLD_HEADERS)
    session.headers.update({"Referer": f"https://{sub}.eightfold.ai/careers/"})

    try:
        _probe_tenant(session, sub, domain)
    except GatedTenantError:
        return []
    except requests.RequestException:
        pass

    seen_ids: set = set()
    candidates: list[dict] = []
    for query in SEARCH_QUERIES:
        encoded_q = quote(query, safe="")
        start = 0
        for _ in range(MAX_PAGES_PER_QUERY):
            url = LIST_URL.format(
                sub=sub, domain=domain, start=start, num=PAGE_SIZE, query=encoded_q,
            )
            data = retry_get(session, url)
            positions = data.get("positions", []) if isinstance(data, dict) else []
            total = int(data.get("count", 0) or 0) if isinstance(data, dict) else 0
            if not positions:
                break

            for pos in positions:
                pid = pos.get("id")
                if pid in seen_ids:
                    continue
                seen_ids.add(pid)
                title = pos.get("name", "") or ""
                if title_passes(title):
                    candidates.append(pos)

            start += len(positions)
            if total and start >= total:
                break
            time.sleep(PAGE_DELAY)

    postings: list[JobPosting] = []
    for pos in candidates:
        job_id = pos.get("id")
        title = pos.get("name", "") or ""

        # Detail fetch — list responses carry no description.
        description_text = ""
        workplace = _workplace_type(pos)
        if job_id:
            try:
                d_url = DETAIL_URL.format(sub=sub, job_id=job_id, domain=domain)
                detail = retry_get(session, d_url)
                if isinstance(detail, dict):
                    description_text = strip_html(detail.get("job_description", "") or "")
                    if not workplace:
                        workplace = _workplace_type(detail)
                time.sleep(DETAIL_DELAY)
            except Exception:
                pass

        apply_url = (
            pos.get("canonicalPositionUrl")
            or pos.get("apply_url")
            or pos.get("url")
            or (f"https://{sub}.eightfold.ai/careers/job/{job_id}" if job_id else "")
        )

        postings.append(JobPosting(
            company=target.name,
            title=title,
            url=apply_url,
            location=_location_str(pos),
            department=_department(pos),
            description_text=description_text,
            ats_platform=target.ats_platform,
            compensation=pos.get("type", "") or "",
            posted_date=_format_posted(
                pos.get("t_create") or pos.get("created_at") or pos.get("posting_start_date")
            ),
            workplace_type=workplace,
            description_available=bool(description_text),
        ))

    return postings
