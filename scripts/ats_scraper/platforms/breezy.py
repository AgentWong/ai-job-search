"""
Breezy HR ATS fetcher

List API:
    GET https://{slug}.breezy.hr/json
    Response: list of positions with shape:
        { "id", "friendly_id", "name", "url", "published_date",
          "type": {"id","name"},
          "location": {"country":{"name","id"}, "state": {...}, "city",
                       "is_remote", "remote_details": {"value","label"}, "name"},
          "department": null | {...}, "salary": "$125k - $130k" | "",
          "company": {"name","friendly_id"} }

Detail page (used to enrich with full description):
    GET https://{slug}.breezy.hr/p/{friendly_id}
    HTML page containing a `<script type="application/ld+json">` block of
    `@type: JobPosting` with `title`, `description` (HTML), `datePosted`,
    `jobLocation`, and optionally `baseSalary`.
"""

import html as html_module
import json
import re
import time
from ..config import CompanyTarget, JobPosting
from .utils import make_session, retry_get


LIST_URL = "https://{slug}.breezy.hr/json"

_HTML_TAG = re.compile(r"<[^>]+>")
_LD_JSON = re.compile(
    r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>',
    re.DOTALL,
)
DETAIL_DELAY = 0.3


def strip_html(text: str) -> str:
    decoded = html_module.unescape(text or "")
    return _HTML_TAG.sub(" ", decoded).strip()


def _format_location(position: dict) -> str:
    loc = position.get("location", {}) or {}
    if loc.get("name"):
        return loc["name"]
    parts = [
        loc.get("city"),
        (loc.get("state") or {}).get("name") if isinstance(loc.get("state"), dict) else None,
        (loc.get("country") or {}).get("name") if isinstance(loc.get("country"), dict) else None,
    ]
    return ", ".join(p for p in parts if p)


def _workplace_type(position: dict) -> str:
    loc = position.get("location", {}) or {}
    if loc.get("is_remote"):
        return "remote"
    return ""


def _extract_jobposting_ld(html: str) -> dict | None:
    for m in _LD_JSON.finditer(html):
        try:
            d = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if d.get("@type") == "JobPosting":
            return d
    return None


def fetch_jobs(target: CompanyTarget) -> list[JobPosting]:
    session = make_session()
    list_url = LIST_URL.format(slug=target.board_token)
    data = retry_get(session, list_url)

    if not isinstance(data, list):
        return []

    postings = []
    for pos in data:
        pos_url = pos.get("url", "") or ""
        title = pos.get("name", "") or ""
        location = _format_location(pos)
        workplace = _workplace_type(pos)
        salary = pos.get("salary", "") or ""
        emp_type = (pos.get("type") or {}).get("name", "") or ""
        dept_obj = pos.get("department")
        department = ""
        if isinstance(dept_obj, dict):
            department = dept_obj.get("name", "") or ""
        elif isinstance(dept_obj, str):
            department = dept_obj
        posted = (pos.get("published_date") or "")[:10]

        description_text = ""
        if pos_url:
            try:
                resp = session.get(pos_url, timeout=20)
                resp.raise_for_status()
                ld = _extract_jobposting_ld(resp.text)
                if ld:
                    description_text = strip_html(ld.get("description", "") or "")
                    if not posted and ld.get("datePosted"):
                        posted = ld["datePosted"][:10]
                time.sleep(DETAIL_DELAY)
            except Exception:
                pass

        # Append employment type to compensation column when both present.
        comp_str = salary
        if emp_type and emp_type.lower() not in salary.lower():
            comp_str = f"{salary} | {emp_type}".strip(" |")

        postings.append(JobPosting(
            company=target.name,
            title=title,
            url=pos_url,
            location=location,
            department=department,
            description_text=description_text,
            ats_platform=target.ats_platform,
            compensation=comp_str,
            posted_date=posted,
            workplace_type=workplace,
            description_available=bool(description_text),
        ))

    return postings
