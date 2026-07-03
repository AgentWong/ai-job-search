"""
Applied jobs cooldown and ghost job detection.

Reads job_search_log/applications.csv (and pipeline_events.csv for ghost
detection) to build:

  - cooldown set: (company_normalized, role_normalized) pairs from rows where
    date_applied is within the past 60 days
    -> used to skip positions where the same role was recently applied to

  - ghost set: (company_normalized, role_normalized) pairs from rows older
    than the cooldown window where the only pipeline event is the initial
    "applied" with outcome "no_response"
    -> used to skip suspected ghost jobs (posted repeatedly, never responds)

Cooldown is same-role at same-company only. Different role functions at the
same company (e.g. DevOps vs SRE vs MLOps) are NOT collapsed and remain
eligible. Rules mirror shared/applied_jobs_filter.md.
"""

import csv
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

COOLDOWN_DAYS = 60

# Strip seniority modifiers and common decorators so role matching is
# title-shape-stable. The seniority regex stage already drops senior titles
# from candidate listings; this normalization lets a logged "Sr DevOps
# Engineer" application still match a current "DevOps Engineer" listing for
# cooldown purposes (same role function, just different seniority label).
_SENIORITY_TOKEN = re.compile(
    r"\b(senior|sr\.?|lead|principal|staff|junior|jr\.?|"
    r"associate|intermediate|i{1,3}|iv|vi*)\b",
    re.IGNORECASE,
)
_CORP_SUFFIX = re.compile(
    r"\b(inc|llc|corp|corporation|ltd|limited|co|company|labs?|gmbh|plc)\b",
    re.IGNORECASE,
)
# Generic descriptor words that frequently appear in a company's "full" name
# from one source (e.g. the ATS API returns "Akamai Technologies") but are
# dropped when the same company is logged casually ("Akamai"). Stripping them
# lets the short and long forms collapse to one key so the cooldown filter and
# the queue-writer dedup catch the re-application. Like the corporate suffixes
# above, this favors catching a re-application over the rare distinct-company
# collision (documented stance in normalize_company).
_DESCRIPTOR_WORD = re.compile(
    r"\b(technologies|technology|software|solutions|systems|group|holdings|"
    r"industries|international|worldwide|global|enterprises|enterprise|"
    r"digital|networks|media)\b",
    re.IGNORECASE,
)
_NON_ALPHANUM = re.compile(r"[^a-z0-9 ]")
_WHITESPACE = re.compile(r"\s+")
_SRE_FULL = re.compile(r"\bsite reliability engineer\b", re.IGNORECASE)
# Strip parenthetical decorators ("(Remote)", "(US)", "(Hybrid)", "(100% Remote)").
# Bracketed location/modality tags are post-fix noise that don't change the role.
_PAREN_BLOCK = re.compile(r"\s*\([^)]*\)\s*")
# Strip trailing dash-separated location/modality tags ("- Remote", "- US",
# "- Atlanta, GA", "- 100% Remote", "- WFH"). Closed allowlist so we don't
# accidentally eat real role qualifiers like "Cloud Engineer - Development".
_TRAILING_DASH_LOCALE = re.compile(
    r"\s*[-–—]\s*("
    r"remote|hybrid|onsite|on[- ]?site|wfh|"
    r"us|usa|united states|"
    r"\d+%\s*remote|"  # "100% Remote"
    r"[a-z][a-z .]+,\s*[a-z]{2}"  # "Atlanta, GA"
    r")\s*$",
    re.IGNORECASE,
)
# Strip a leading "Remote " prefix that some boards prepend.
_LEADING_REMOTE = re.compile(r"^\s*remote\s+", re.IGNORECASE)


def normalize_company(name: str) -> str:
    """Lowercase, strip parenthetical qualifiers, strip corporate suffixes and generic descriptor words, normalize punctuation/whitespace.

    Generic descriptor words ("Technologies", "Software", "Solutions",
    "Systems", ...) are stripped so a company logged under its short name
    ("Akamai") collapses to the same key as the ATS API's fuller name
    ("Akamai Technologies"). Without this the cooldown filter and queue dedup
    silently miss re-applications whenever the two sources disagree on the
    descriptor.

    Parenthetical content is stripped first so "Attune (Method Insurance)"
    and "Method Insurance (Attune)" both collapse to their primary token and
    can match the canonical entry in applications.csv.

    Internal whitespace is then removed entirely so compound-word spelling
    variants collapse to one key: "Blue Cross Blue Shield" == "BlueCross
    BlueShield", "Net App" == "NetApp", "Smart Recruiters" == "SmartRecruiters".
    This is a comparison key only (never displayed); cooldown/dedup favors
    catching a re-application over the rare distinct-company collision.
    """
    if not name:
        return ""
    n = name.lower()
    n = _PAREN_BLOCK.sub(" ", n)
    n = _CORP_SUFFIX.sub("", n)
    n = _DESCRIPTOR_WORD.sub("", n)
    n = _NON_ALPHANUM.sub(" ", n)
    n = _WHITESPACE.sub(" ", n).strip()
    n = n.replace(" ", "")
    return n


def normalize_role(title: str) -> str:
    """Strip seniority modifiers, location/modality decorators, normalize punctuation.

    Strips parenthetical decorators (e.g., "Cloud Engineer (Remote)") and
    trailing dash-separated location/modality tags (e.g., "Cloud Engineer -
    Remote", "DevOps Engineer - Atlanta, GA") so the same logical role at the
    same company collapses to the same key for cooldown matching.
    Collapses SRE <-> Site Reliability Engineer.
    """
    if not title:
        return ""
    n = title.lower()
    # Decorator stripping must run BEFORE _NON_ALPHANUM eats the
    # parens/dashes the patterns depend on.
    n = _PAREN_BLOCK.sub(" ", n)
    n = _TRAILING_DASH_LOCALE.sub("", n)
    n = _LEADING_REMOTE.sub("", n)
    n = _SRE_FULL.sub("sre", n)
    n = _NON_ALPHANUM.sub(" ", n)
    n = _SENIORITY_TOKEN.sub(" ", n)
    n = _WHITESPACE.sub(" ", n).strip()
    return n


@dataclass
class CooldownData:
    """Parsed cooldown and ghost job sets."""
    cooldown: set = field(default_factory=set)
    ghost: set = field(default_factory=set)
    cooldown_entries: list = field(default_factory=list)
    ghost_entries: list = field(default_factory=list)


def _load_applications(apps_csv: Path) -> list[dict]:
    if not apps_csv.exists():
        return []
    with open(apps_csv, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _load_responded_app_ids(events_csv: Path) -> set[str]:
    """Return app_ids that have any post-applied event or any non-no_response outcome.

    An app is considered "responded to" if it has any pipeline event other
    than the initial applied stage, OR if its applied event has any outcome
    other than 'no_response' (e.g. rejected, ghosted, withdrew). Only apps
    with the bare 'applied + no_response' record are eligible to be flagged
    as ghost jobs.
    """
    if not events_csv.exists():
        return set()
    responded: set[str] = set()
    with open(events_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            app_id = (row.get("app_id") or "").strip()
            if not app_id:
                continue
            stage = (row.get("event_stage") or "").lower()
            outcome = (row.get("event_outcome") or "").lower()
            if stage != "applied":
                responded.add(app_id)
                continue
            if outcome and outcome != "no_response":
                responded.add(app_id)
    return responded


def get_company_recent_applications(
    company_raw: str, log_dir: Path, today: date
) -> list[dict]:
    """Return all applications at a given company within the past 60 days.

    No role normalization — returns raw role strings and dates so the LLM
    can do fuzzy same-role matching.
    """
    apps_csv = log_dir / "applications.csv"
    rows = _load_applications(apps_csv)
    if not rows:
        return []

    cutoff = today - timedelta(days=COOLDOWN_DAYS)
    company_norm = normalize_company(company_raw)
    recent = []
    for row in rows:
        c = normalize_company((row.get("company") or "").strip())
        if c != company_norm:
            continue
        date_raw = (row.get("date_applied") or "").strip()
        try:
            applied = datetime.strptime(date_raw, "%Y-%m-%d").date()
        except ValueError:
            continue
        if applied >= cutoff:
            recent.append({
                "role": (row.get("role") or "").strip(),
                "date_applied": date_raw,
            })
    return recent


def load_cooldown_data(log_dir: Path, today: date) -> CooldownData:
    """Build CooldownData from applications.csv + pipeline_events.csv.

    Args:
        log_dir: Path to job_search_log/ directory
        today: Reference date (anchor for the 60-day window)
    """
    data = CooldownData()
    apps_csv = log_dir / "applications.csv"
    events_csv = log_dir / "pipeline_events.csv"

    rows = _load_applications(apps_csv)
    if not rows:
        return data

    cutoff = today - timedelta(days=COOLDOWN_DAYS)
    responded_ids = _load_responded_app_ids(events_csv)

    for row in rows:
        company_raw = (row.get("company") or "").strip()
        role_raw = (row.get("role") or "").strip()
        date_applied_raw = (row.get("date_applied") or "").strip()
        if not company_raw or not role_raw:
            continue

        company_norm = normalize_company(company_raw)
        role_norm = normalize_role(role_raw)
        if not company_norm or not role_norm:
            continue

        try:
            applied = datetime.strptime(date_applied_raw, "%Y-%m-%d").date()
        except ValueError:
            # Missing/malformed date - skip; can't classify recent vs old
            continue

        key = (company_norm, role_norm)

        if applied >= cutoff:
            data.cooldown.add(key)
            data.cooldown_entries.append(
                f"{company_raw} / {role_raw} ({date_applied_raw})"
            )
        else:
            app_id = (row.get("app_id") or "").strip()
            if app_id and app_id not in responded_ids:
                data.ghost.add(key)
                data.ghost_entries.append(
                    f"{company_raw} / {role_raw} ({date_applied_raw}) - no response"
                )

    return data
