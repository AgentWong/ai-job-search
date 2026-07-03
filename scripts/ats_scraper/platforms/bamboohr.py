"""
BambooHR ATS fetcher

List API:
    GET https://{slug}.bamboohr.com/careers/list
    Headers: Accept: application/json, X-Requested-With: XMLHttpRequest
    Response: { "meta": {"totalCount": N},
                "result": [ { "id", "jobOpeningName", "departmentLabel",
                              "employmentStatusLabel",
                              "location": {"city","state"},
                              "atsLocation": {"country","state","province","city"},
                              "isRemote", "locationType" } ] }

Detail page:
    GET https://{slug}.bamboohr.com/careers/{id}/detail
    HTML page with an embedded JSON object that begins with `{"jobOpeningShareUrl"...}`
    Containing description (HTML), location, compensation, datePosted, etc.

Inactive accounts redirect (302) to https://www.bamboohr.com — caller should
treat such targets as having no jobs rather than erroring.
"""

import html as html_module
import json
import re
import time
from ..config import CompanyTarget, JobPosting
from .utils import make_session, retry_get


LIST_URL = "https://{slug}.bamboohr.com/careers/list"
DETAIL_URL = "https://{slug}.bamboohr.com/careers/{job_id}/detail"

BAMBOO_HEADERS = {
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest",
}

_HTML_TAG = re.compile(r"<[^>]+>")
_EMBEDDED_JSON_START = re.compile(r'\{"jobOpeningShareUrl"')
DETAIL_DELAY = 0.3


def strip_html(text: str) -> str:
    decoded = html_module.unescape(text or "")
    return _HTML_TAG.sub(" ", decoded).strip()


def _format_location(list_row: dict) -> str:
    loc = list_row.get("location", {}) or {}
    ats = list_row.get("atsLocation", {}) or {}
    parts = [
        ats.get("city") or loc.get("city"),
        ats.get("state") or ats.get("province") or loc.get("state"),
        ats.get("country"),
    ]
    return ", ".join(p for p in parts if p)


def _is_remote(list_row: dict) -> str:
    if list_row.get("isRemote") is True:
        return "remote"
    # locationType "2" appears to mean remote in observed payloads; "0" onsite.
    if str(list_row.get("locationType", "")) == "2":
        return "remote"
    return ""


def _extract_embedded_payload(html: str) -> dict | None:
    m = _EMBEDDED_JSON_START.search(html)
    if not m:
        return None
    start = m.start()
    depth = 0
    in_str = False
    esc = False
    for i, c in enumerate(html[start:], start=start):
        if esc:
            esc = False
            continue
        if c == "\\":
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if not in_str:
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(html[start : i + 1])
                    except json.JSONDecodeError:
                        return None
    return None


def fetch_jobs(target: CompanyTarget) -> list[JobPosting]:
    session = make_session(extra_headers=BAMBOO_HEADERS)
    list_url = LIST_URL.format(slug=target.board_token)

    # Inactive accounts 302 to www.bamboohr.com which serves HTML; treat as empty.
    try:
        data = retry_get(session, list_url)
    except RuntimeError:
        return []
    if not isinstance(data, dict) or "result" not in data:
        return []

    postings = []
    for row in data.get("result", []) or []:
        job_id = str(row.get("id", "") or "")
        if not job_id:
            continue
        title = row.get("jobOpeningName", "") or ""
        department = row.get("departmentLabel", "") or ""
        location = _format_location(row)
        workplace = _is_remote(row)
        apply_url = f"https://{target.board_token}.bamboohr.com/careers/{job_id}"

        description_text = ""
        compensation = ""
        posted_date = ""
        try:
            detail_html_resp = session.get(
                DETAIL_URL.format(slug=target.board_token, job_id=job_id),
                timeout=20,
            )
            detail_html_resp.raise_for_status()
            payload = _extract_embedded_payload(detail_html_resp.text)
            if payload:
                description_text = strip_html(payload.get("description", "") or "")
                comp = payload.get("compensation")
                if isinstance(comp, str):
                    compensation = comp
                elif isinstance(comp, dict):
                    parts = [str(v) for v in comp.values() if v]
                    compensation = " ".join(parts)
                posted_date = (payload.get("datePosted") or "")[:10]
                if not workplace and payload.get("isRemote"):
                    workplace = "remote"
            time.sleep(DETAIL_DELAY)
        except Exception:
            pass

        postings.append(JobPosting(
            company=target.name,
            title=title,
            url=apply_url,
            location=location,
            department=department,
            description_text=description_text,
            ats_platform=target.ats_platform,
            compensation=compensation,
            posted_date=posted_date,
            workplace_type=workplace,
            description_available=bool(description_text),
        ))

    return postings
