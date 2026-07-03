"""
Single-request probes for each ATS platform.

Each probe returns a ProbeResult with:
- ok: True if the slug resolves to a valid board (200 + parseable shape)
- jobs_total: total job count visible at the board (None if unknown)
- status_code: HTTP status from the probe
- detail: short human-readable reason (e.g. "404 Not Found", "ok: 137 jobs",
          "403 PCSX gated", "auth required")
- probe_url: the URL that was hit, for the report

These probes intentionally use small page sizes / no detail fetches so a
sweep across 60+ companies completes in well under a minute. The shapes mirror
`scripts/ats_scraper/platforms/*` but trimmed to a single HEAD-like call.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import requests


DEFAULT_TIMEOUT = 15
BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class ProbeResult:
    ok: bool
    jobs_total: Optional[int]
    status_code: Optional[int]
    detail: str
    probe_url: str


def _session(extra_headers: Optional[dict] = None) -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": BROWSER_UA, "Accept": "application/json"})
    if extra_headers:
        s.headers.update(extra_headers)
    return s


def _safe_json(resp: requests.Response):
    try:
        return resp.json()
    except ValueError:
        return None


def probe_greenhouse(slug: str) -> ProbeResult:
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=false"
    try:
        resp = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        return ProbeResult(False, None, None, f"network error: {exc}", url)
    if resp.status_code == 404:
        return ProbeResult(False, None, 404, "404 Not Found (board does not exist)", url)
    if resp.status_code != 200:
        return ProbeResult(False, None, resp.status_code, f"HTTP {resp.status_code}", url)
    data = _safe_json(resp)
    if not isinstance(data, dict) or "jobs" not in data:
        return ProbeResult(False, None, 200, "200 but no 'jobs' key in response", url)
    total = len(data.get("jobs") or [])
    return ProbeResult(True, total, 200, f"ok: {total} jobs", url)


def probe_ashby(slug: str) -> ProbeResult:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=false"
    try:
        resp = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        return ProbeResult(False, None, None, f"network error: {exc}", url)
    if resp.status_code == 404:
        return ProbeResult(False, None, 404, "404 Not Found", url)
    if resp.status_code != 200:
        return ProbeResult(False, None, resp.status_code, f"HTTP {resp.status_code}", url)
    data = _safe_json(resp)
    if not isinstance(data, dict) or "jobs" not in data:
        return ProbeResult(False, None, 200, "200 but no 'jobs' key", url)
    total = len(data.get("jobs") or [])
    return ProbeResult(True, total, 200, f"ok: {total} jobs", url)


def probe_lever(slug: str) -> ProbeResult:
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json&limit=1"
    try:
        resp = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        return ProbeResult(False, None, None, f"network error: {exc}", url)
    if resp.status_code == 404:
        return ProbeResult(False, None, 404, "404 Not Found", url)
    if resp.status_code != 200:
        return ProbeResult(False, None, resp.status_code, f"HTTP {resp.status_code}", url)
    data = _safe_json(resp)
    if not isinstance(data, list):
        return ProbeResult(False, None, 200, "200 but response is not a list", url)
    # Lever's mode=json returns up to `limit` postings; total is not exposed.
    return ProbeResult(True, len(data), 200, f"ok: {len(data)}+ jobs visible", url)


def probe_smartrecruiters(slug: str) -> ProbeResult:
    """SmartRecruiters API returns 200/totalFound:0 for arbitrary slugs (the
    endpoint doesn't 404 on bad tenants), so when totalFound is 0 we follow up
    with the careers.smartrecruiters.com HTML page — invalid slugs 302 to the
    generic landing at jobs.smartrecruiters.com."""
    url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=1&offset=0"
    try:
        resp = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        return ProbeResult(False, None, None, f"network error: {exc}", url)
    if resp.status_code == 404:
        return ProbeResult(False, None, 404, "404 Not Found", url)
    if resp.status_code != 200:
        return ProbeResult(False, None, resp.status_code, f"HTTP {resp.status_code}", url)
    data = _safe_json(resp)
    if not isinstance(data, dict):
        return ProbeResult(False, None, 200, "200 but response is not an object", url)
    total = data.get("totalFound")
    if not isinstance(total, int):
        return ProbeResult(False, None, 200, "200 but no totalFound key", url)
    if total > 0:
        return ProbeResult(True, total, 200, f"ok: {total} jobs", url)
    # totalFound == 0: verify slug validity via the careers HTML host
    html_url = f"https://careers.smartrecruiters.com/{slug}"
    try:
        h = requests.get(html_url, headers={"User-Agent": BROWSER_UA},
                         timeout=DEFAULT_TIMEOUT, allow_redirects=False)
    except requests.RequestException:
        return ProbeResult(True, 0, 200, "ok: 0 jobs (ambiguous — HTML probe failed)", url)
    if h.status_code in (301, 302):
        loc = (h.headers.get("location") or "").lower()
        if "jobs.smartrecruiters.com" in loc and slug.lower() not in loc:
            return ProbeResult(False, 0, 200, "API returns 0; careers page redirects to landing (slug invalid)", html_url)
    if h.status_code == 200:
        return ProbeResult(True, 0, 200, "ok: 0 jobs (board exists, currently empty)", url)
    return ProbeResult(True, 0, 200, f"ok: 0 jobs (HTML probe status {h.status_code})", url)


def probe_rippling(slug: str) -> ProbeResult:
    url = f"https://api.rippling.com/platform/api/ats/v1/board/{slug}/jobs"
    try:
        resp = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        return ProbeResult(False, None, None, f"network error: {exc}", url)
    if resp.status_code == 404:
        return ProbeResult(False, None, 404, "404 Not Found", url)
    if resp.status_code != 200:
        return ProbeResult(False, None, resp.status_code, f"HTTP {resp.status_code}", url)
    data = _safe_json(resp)
    items = data if isinstance(data, list) else (data.get("data") if isinstance(data, dict) else None)
    if items is None:
        return ProbeResult(False, None, 200, "200 but no jobs array", url)
    return ProbeResult(True, len(items), 200, f"ok: {len(items)} jobs", url)


def probe_workday(slug: str, career_url: str = "") -> ProbeResult:
    """
    Workday slug format: '{tenant}.{dc}' (e.g., 'crowdstrike.wd5').
    The board name comes from the career URL trailing path segment.
    """
    token = slug.split(":", 1)[0]
    if "." in token:
        tenant, dc = token.split(".", 1)
    else:
        tenant = token
        m = re.search(r"\.?(wd\d+)\.myworkdayjobs\.com", career_url or "")
        dc = m.group(1) if m else "wd1"

    board = ""
    if career_url:
        board = career_url.rstrip("/").split("/")[-1]

    if not board:
        return ProbeResult(False, None, None, "could not parse board name from career_url", "")

    url = f"https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{board}/jobs"
    headers = {
        "User-Agent": BROWSER_UA,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        return ProbeResult(False, None, None, f"network error: {exc}", url)
    if resp.status_code == 404:
        return ProbeResult(False, None, 404, "404 Not Found (tenant/board mismatch)", url)
    if resp.status_code != 200:
        return ProbeResult(False, None, resp.status_code, f"HTTP {resp.status_code}", url)
    data = _safe_json(resp)
    if not isinstance(data, dict) or "jobPostings" not in data:
        return ProbeResult(False, None, 200, "200 but missing jobPostings key", url)
    total = data.get("total")
    if not isinstance(total, int):
        total = len(data.get("jobPostings") or [])
    return ProbeResult(True, total, 200, f"ok: {total} jobs", url)


def probe_eightfold(slug: str) -> ProbeResult:
    """
    Eightfold slug format: '{subdomain}' or '{subdomain}|{domain}'.
    """
    if "|" in slug:
        sub, domain = slug.split("|", 1)
        sub, domain = sub.strip(), domain.strip()
    else:
        sub = slug.strip()
        domain = f"{sub}.com" if sub else ""
    if not sub or not domain:
        return ProbeResult(False, None, None, "missing subdomain or domain", "")
    url = (
        f"https://{sub}.eightfold.ai/api/apply/v2/jobs"
        f"?domain={domain}&hl=en&start=0&num=5&pid=&domainName=true"
    )
    try:
        resp = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        return ProbeResult(False, None, None, f"network error: {exc}", url)
    if resp.status_code == 403:
        data = _safe_json(resp) or {}
        msg = data.get("message", "") if isinstance(data, dict) else ""
        if "PCSX" in msg or "Not authorized" in msg:
            return ProbeResult(False, None, 403, f"403 PCSX-gated tenant ({msg})", url)
        return ProbeResult(False, None, 403, "403 Forbidden", url)
    if resp.status_code != 200:
        return ProbeResult(False, None, resp.status_code, f"HTTP {resp.status_code}", url)
    data = _safe_json(resp)
    if not isinstance(data, dict):
        return ProbeResult(False, None, 200, "200 but response is not an object", url)
    total = data.get("count")
    if not isinstance(total, int):
        return ProbeResult(False, None, 200, "200 but no count key", url)
    return ProbeResult(True, total, 200, f"ok: {total} jobs", url)


def probe_dayforce(slug: str) -> ProbeResult:
    """
    Dayforce slug format: '{clientNamespace}:{jobBoardCode}'.
    Requires CSRF token, so we do a two-call probe.
    """
    if ":" in slug:
        namespace, board = slug.split(":", 1)
    else:
        namespace, board = slug, "CANDIDATEPORTAL"

    headers = {
        "User-Agent": BROWSER_UA,
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://jobs.dayforcehcm.com",
        "Referer": f"https://jobs.dayforcehcm.com/en-US/{namespace}/{board}",
    }
    sess = requests.Session()
    sess.headers.update(headers)
    csrf_url = "https://jobs.dayforcehcm.com/api/auth/csrf"
    try:
        r = sess.get(csrf_url, timeout=DEFAULT_TIMEOUT)
        if r.status_code != 200:
            return ProbeResult(False, None, r.status_code, f"csrf HTTP {r.status_code}", csrf_url)
        token = (_safe_json(r) or {}).get("csrfToken")
        if not token:
            return ProbeResult(False, None, 200, "csrf returned no token", csrf_url)
        sess.headers.update({"X-CSRF-Token": token, "Content-Type": "application/json"})
        search_url = f"https://jobs.dayforcehcm.com/api/geo/{namespace}/jobposting/search"
        payload = {
            "clientNamespace": namespace,
            "jobBoardCode": board,
            "cultureCode": "en-US",
            "distanceUnit": 0,
            "paginationStart": 0,
        }
        r2 = sess.post(search_url, json=payload, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        return ProbeResult(False, None, None, f"network error: {exc}", csrf_url)

    if r2.status_code == 404:
        return ProbeResult(False, None, 404, "404 Not Found", search_url)
    if r2.status_code != 200:
        return ProbeResult(False, None, r2.status_code, f"search HTTP {r2.status_code}", search_url)
    data = _safe_json(r2)
    if not isinstance(data, dict):
        return ProbeResult(False, None, 200, "200 but search response not an object", search_url)
    total = data.get("maxCount")
    if not isinstance(total, int):
        return ProbeResult(False, None, 200, "200 but no maxCount key", search_url)
    return ProbeResult(True, total, 200, f"ok: {total} jobs", search_url)


def probe_icims(slug: str) -> ProbeResult:
    """iCIMS hosts at careers-{slug}.icims.com. Search endpoint returns HTML."""
    url = f"https://careers-{slug}.icims.com/jobs/search?ss=1"
    try:
        resp = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        return ProbeResult(False, None, None, f"network error: {exc}", url)
    if resp.status_code == 404:
        return ProbeResult(False, None, 404, "404 Not Found", url)
    if resp.status_code != 200:
        return ProbeResult(False, None, resp.status_code, f"HTTP {resp.status_code}", url)
    # Heuristic: look for "no jobs" text or a job count tag
    body = resp.text or ""
    if "iCIMS" not in body and "icims" not in body:
        return ProbeResult(False, None, 200, "200 but no iCIMS markers", url)
    return ProbeResult(True, None, 200, "ok: iCIMS board exists", url)


def probe_bamboohr(slug: str) -> ProbeResult:
    """BambooHR hosts at {slug}.bamboohr.com/careers."""
    url = f"https://{slug}.bamboohr.com/careers"
    try:
        resp = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=DEFAULT_TIMEOUT, allow_redirects=False)
    except requests.RequestException as exc:
        return ProbeResult(False, None, None, f"network error: {exc}", url)
    if resp.status_code in (404, 301, 302):
        return ProbeResult(False, None, resp.status_code, f"HTTP {resp.status_code} (no such tenant)", url)
    if resp.status_code != 200:
        return ProbeResult(False, None, resp.status_code, f"HTTP {resp.status_code}", url)
    return ProbeResult(True, None, 200, "ok: BambooHR tenant exists", url)


def probe_recruitee(slug: str) -> ProbeResult:
    url = f"https://{slug}.recruitee.com/api/offers/"
    try:
        resp = requests.get(url, headers={"User-Agent": BROWSER_UA, "Accept": "application/json"}, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        return ProbeResult(False, None, None, f"network error: {exc}", url)
    if resp.status_code != 200:
        return ProbeResult(False, None, resp.status_code, f"HTTP {resp.status_code}", url)
    data = _safe_json(resp)
    if not isinstance(data, dict) or "offers" not in data:
        return ProbeResult(False, None, 200, "200 but no offers array", url)
    total = len(data.get("offers") or [])
    return ProbeResult(True, total, 200, f"ok: {total} jobs", url)


def probe_workable(slug: str) -> ProbeResult:
    url = f"https://apply.workable.com/api/v1/widget/accounts/{slug}"
    try:
        resp = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        return ProbeResult(False, None, None, f"network error: {exc}", url)
    if resp.status_code == 404:
        return ProbeResult(False, None, 404, "404 Not Found", url)
    if resp.status_code != 200:
        return ProbeResult(False, None, resp.status_code, f"HTTP {resp.status_code}", url)
    data = _safe_json(resp)
    if not isinstance(data, dict):
        return ProbeResult(False, None, 200, "200 but unexpected shape", url)
    jobs = data.get("jobs") if isinstance(data.get("jobs"), list) else None
    total = len(jobs) if jobs is not None else None
    return ProbeResult(True, total, 200, f"ok: {total if total is not None else '?'} jobs", url)


def probe_jobvite(slug: str) -> ProbeResult:
    """Jobvite redirects unknown tenants to a generic ?invalid=1 page; only count
    HTML responses that actually contain the slug as the company anchor."""
    url = f"https://jobs.jobvite.com/{slug}/jobs"
    try:
        resp = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=DEFAULT_TIMEOUT,
                            allow_redirects=False)
    except requests.RequestException as exc:
        return ProbeResult(False, None, None, f"network error: {exc}", url)
    if resp.status_code in (301, 302):
        loc = resp.headers.get("location", "")
        if "invalid" in loc.lower():
            return ProbeResult(False, None, resp.status_code, "redirect to invalid landing page", url)
        return ProbeResult(False, None, resp.status_code, f"unexpected redirect: {loc}", url)
    if resp.status_code != 200:
        return ProbeResult(False, None, resp.status_code, f"HTTP {resp.status_code}", url)
    body = (resp.text or "").lower()
    if slug.lower() not in body or "jobvite" not in body:
        return ProbeResult(False, None, 200, "200 but no tenant markers", url)
    return ProbeResult(True, None, 200, "ok: Jobvite HTML page exists", url)


# Platform name -> probe function. Names match the ATS_Platform column.
PROBES = {
    "greenhouse": probe_greenhouse,
    "ashby": probe_ashby,
    "lever": probe_lever,
    "smartrecruiters": probe_smartrecruiters,
    "rippling": probe_rippling,
    "workday": probe_workday,
    "eightfold": probe_eightfold,
    "dayforce": probe_dayforce,
}

# Discovery-only probes: platforms we can detect but don't scrape. Used by
# `--discover` to answer "where did this company actually end up?".
DISCOVERY_PROBES = {
    **PROBES,
    "icims": probe_icims,
    "bamboohr": probe_bamboohr,
    "recruitee": probe_recruitee,
    "workable": probe_workable,
    "jobvite": probe_jobvite,
}


def probe(platform: str, slug: str, career_url: str = "") -> ProbeResult:
    key = (platform or "").strip().lower()
    fn = PROBES.get(key)
    if fn is None:
        return ProbeResult(False, None, None, f"no probe for platform '{platform}'", "")
    if key == "workday":
        return fn(slug, career_url)
    return fn(slug)


def discover(slug: str, career_url: str = "") -> dict[str, ProbeResult]:
    """Probe `slug` against every known platform. Returns {platform: result}."""
    results: dict[str, ProbeResult] = {}
    for plat, fn in DISCOVERY_PROBES.items():
        try:
            if plat == "workday":
                results[plat] = fn(slug, career_url)
            else:
                results[plat] = fn(slug)
        except Exception as exc:  # pragma: no cover
            results[plat] = ProbeResult(False, None, None, f"probe raised: {exc}", "")
    return results
