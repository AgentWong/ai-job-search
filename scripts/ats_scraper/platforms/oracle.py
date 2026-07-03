"""
Oracle Recruiting Cloud (ORC) ATS fetcher

Anonymous JSON API replacing legacy Taleo. Used by JPMorgan, Goldman Sachs,
Marriott, Honeywell, Akamai, Macy's, Navy Federal, Vertiv, Stantec, IHG, etc.

List API:
    GET {base}/hcmRestApi/resources/latest/recruitingCEJobRequisitions
        ?onlyData=true
        &expand=requisitionList.secondaryLocations,requisitionList.workLocation
        &finder=findReqs;siteNumber={site},limit=200,offset=0,workLocationCountryCode=US,sortBy=POSTING_DATES_DESC
    Where {base} is one of:
        https://{POD}.fa.{DC}.oraclecloud.com    (e.g. eeho.fa.us2.oraclecloud.com)
        https://{POD}.fa.oraclecloud.com         (e.g. jpmc.fa.oraclecloud.com)
        https://{POD}.fa.ocs.oraclecloud.com     (newer fa-XXXX-saasfaprod1 PODs)

    Response shape: { "items": [ { "TotalJobsCount", "requisitionList": [
        { "Id", "Title", "PrimaryLocation", "PostedDate",
          "WorkplaceType", "workLocation": {...}, "secondaryLocations": [...] } ] } ] }

Detail API:
    GET {base}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails
        ?expand=all&onlyData=true&finder=ById;Id={reqId},siteNumber={site}
    Response: ExternalDescriptionStr (HTML), ExternalQualificationsStr (HTML),
              ExternalResponsibilitiesStr (HTML), CorporateDescriptionStr (HTML).

ATS_Slug format: the customer-facing site name from the career-page URL.
Examples: "jobsearch", "CX_1", "CX_1001", "nfcu". Extract from
career_url path segment "/sites/{siteName}/...".

Browser User-Agent required — `python-requests/X` triggers 403.
"""

import html as html_module
import re
import time
from urllib.parse import quote
from ..config import CompanyTarget, JobPosting
from ..filters import title_passes
from .utils import make_session, retry_get


ORC_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

_HTML_TAG = re.compile(r"<[^>]+>")
DETAIL_DELAY = 0.5
PAGE_SIZE = 200


def strip_html(text: str) -> str:
    decoded = html_module.unescape(text or "")
    return _HTML_TAG.sub(" ", decoded).strip()


def _parse_host(career_url: str) -> str | None:
    """Return the API base origin (https://...) parsed from the career URL hostname."""
    m = re.match(r"https?://([^/]+)", career_url or "")
    if not m:
        return None
    host = m.group(1).lower()
    # Pattern: {POD}.fa.{DC}.oraclecloud.com
    m1 = re.match(r"^([\w-]+)\.fa\.([a-z]{2}\d+)\.oraclecloud\.com$", host)
    if m1:
        return f"https://{m1.group(1)}.fa.{m1.group(2)}.oraclecloud.com"
    # Pattern: {POD}.fa.oraclecloud.com (no datacenter subdomain)
    m2 = re.match(r"^([\w-]+)\.fa\.oraclecloud\.com$", host)
    if m2:
        return f"https://{m2.group(1)}.fa.oraclecloud.com"
    # Pattern: fa-XXXX-saasfaprod1.fa.ocs.oraclecloud.com
    m3 = re.match(r"^([\w-]+)\.fa\.ocs\.oraclecloud\.com$", host)
    if m3:
        return f"https://{m3.group(1)}.fa.ocs.oraclecloud.com"
    return None


def _format_location(req: dict) -> str:
    primary = req.get("PrimaryLocation", "") or ""
    if primary:
        return primary
    work_loc = req.get("workLocation") or {}
    if isinstance(work_loc, dict):
        parts = [
            work_loc.get("City"),
            work_loc.get("State") or work_loc.get("Region"),
            work_loc.get("CountryCode") or work_loc.get("Country"),
        ]
        return ", ".join(p for p in parts if p)
    return ""


def _normalize_workplace(raw: str) -> str:
    s = (raw or "").lower()
    if "remote" in s:
        return "remote"
    if "hybrid" in s:
        return "hybrid"
    if "onsite" in s or "on-site" in s or "on site" in s:
        return "on-site"
    return ""


def _extract_site_name(target: CompanyTarget) -> str:
    """Prefer ATS_Slug; fall back to career URL /sites/{name}/ segment."""
    if target.board_token:
        return target.board_token
    m = re.search(r"/sites/([^/?#]+)", target.career_url or "")
    return m.group(1) if m else ""


def fetch_jobs(target: CompanyTarget) -> list[JobPosting]:
    base = _parse_host(target.career_url)
    site = _extract_site_name(target)
    if not base or not site:
        return []

    session = make_session(extra_headers=ORC_HEADERS)
    list_endpoint = f"{base}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
    detail_endpoint = f"{base}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails"

    candidates: list[dict] = []
    offset = 0
    while True:
        finder_value = (
            f"findReqs;siteNumber={site},"
            f"limit={PAGE_SIZE},offset={offset},"
            f"workLocationCountryCode=US,"
            f"sortBy=POSTING_DATES_DESC"
        )
        url = (
            f"{list_endpoint}?onlyData=true"
            f"&expand=requisitionList.secondaryLocations,requisitionList.workLocation"
            f"&finder={quote(finder_value, safe=';,=')}"
        )
        data = retry_get(session, url)

        items = data.get("items", []) or []
        if not items:
            break
        # Single wrapper item containing requisitionList + count
        wrapper = items[0]
        reqs = wrapper.get("requisitionList", []) or []
        total = int(wrapper.get("TotalJobsCount", 0) or 0)

        for req in reqs:
            title = req.get("Title", "") or ""
            if title_passes(title):
                candidates.append(req)

        offset += len(reqs)
        if not reqs or offset >= total:
            break
        time.sleep(0.3)

    postings: list[JobPosting] = []
    for req in candidates:
        req_id = str(req.get("Id", "") or "")
        if not req_id:
            continue
        title = req.get("Title", "") or ""
        location = _format_location(req)
        workplace = _normalize_workplace(req.get("WorkplaceType", "") or "")
        posted_date = (req.get("PostedDate") or req.get("PostingStartDate") or "")[:10]

        apply_url = (
            f"{base}/hcmUI/CandidateExperience/en/sites/{site}/job/{req_id}"
        )

        description_text = ""
        try:
            d_finder = f"ById;Id={req_id},siteNumber={site}"
            d_url = (
                f"{detail_endpoint}?onlyData=true&expand=all"
                f"&finder={quote(d_finder, safe=';,=')}"
            )
            detail = retry_get(session, d_url)
            d_items = detail.get("items", []) or []
            if d_items:
                row = d_items[0]
                parts = [
                    row.get("ExternalDescriptionStr", ""),
                    row.get("ExternalResponsibilitiesStr", ""),
                    row.get("ExternalQualificationsStr", ""),
                    row.get("CorporateDescriptionStr", ""),
                ]
                description_text = strip_html(" ".join(p for p in parts if p))
                if not workplace:
                    workplace = _normalize_workplace(row.get("WorkplaceType", "") or "")
            time.sleep(DETAIL_DELAY)
        except Exception:
            pass

        postings.append(JobPosting(
            company=target.name,
            title=title,
            url=apply_url,
            location=location,
            department="",
            description_text=description_text,
            ats_platform=target.ats_platform,
            posted_date=posted_date,
            workplace_type=workplace,
            description_available=bool(description_text),
        ))

    return postings
