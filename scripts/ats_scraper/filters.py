import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional
from .config import JobPosting
from .location import LocationConfig, location_verdict

# Stage 1: Title matching patterns
# _TARGET_ROLES is built at runtime from config/config.yml via
# set_target_roles(). The fallback regex below is only used if nothing has
# been set — e.g. a direct import in tests — and mirrors the role list in
# config.yml at time of writing.
_TARGET_ROLES = re.compile(
    r"devops|platform engineer|site reliability|sre|cloud engineer|"
    r"infrastructure engineer|systems engineer|cloud administrator|"
    r"cloud operations|release engineer",
    re.IGNORECASE,
)


def build_target_roles_pattern(role_names: list[str]) -> re.Pattern:
    """Compile a case-insensitive regex matching any of the given role names.

    SRE gets special handling: if the expanded form "Site Reliability Engineer"
    is present, the "SRE" abbreviation is also accepted so titles like
    "SRE II" still match.
    """
    alternatives: list[str] = []
    seen: set[str] = set()
    for raw in role_names:
        name = (raw or "").strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        alternatives.append(re.escape(name))
        if key == "site reliability engineer" and "sre" not in seen:
            seen.add("sre")
            alternatives.append(r"\bSRE\b")
    if not alternatives:
        raise ValueError("build_target_roles_pattern: no role names provided")
    return re.compile("|".join(alternatives), re.IGNORECASE)


def set_target_roles(pattern: re.Pattern) -> None:
    """Install the target-roles regex used by apply_filters and title_passes."""
    global _TARGET_ROLES
    _TARGET_ROLES = pattern

_SENIORITY_REJECT = re.compile(
    r"\bsenior\b|\bsr\.?\b|\blead\b|\bprincipal\b|\bstaff\b|\bmanager\b|"
    r"\bdirector\b|\barchitect\b|\bhead of\b|\bIII\b|\bIV\b|\bV\b",
    re.IGNORECASE,
)

_WRONG_ROLE_REJECT = re.compile(
    r"\bbackend\b|\bfullstack\b|\bfull.stack\b|\bsoftware engineer\b",
    re.IGNORECASE,
)

# Stage 2 location/remote filtering now lives in scripts/ats_scraper/location.py
# (shared with the Built In / LinkedIn scrapers) and is mode-aware via
# config.yml `location`. See location_verdict().


POSTED_WITHIN_DAYS = {
    "past_day": 1,
    "past_2_days": 2,
    "past_week": 7,
    "past_month": 30,
}


def _parse_posted_date(raw: str) -> Optional[datetime]:
    """Parse posted_date from various platform formats into a timezone-aware datetime."""
    if not raw:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
    ):
        try:
            return datetime.strptime(raw, fmt).astimezone(timezone.utc)
        except ValueError:
            continue
    for fmt in ("%Y-%m-%d",):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


@dataclass
class FilterStats:
    stage: str
    input_count: int = 0
    output_count: int = 0
    rejections: dict = field(default_factory=dict)
    # Per-company: { company_name: { reason: count } }
    per_company: dict = field(default_factory=dict)

    def reject(self, reason: str, company: str = ""):
        self.rejections[reason] = self.rejections.get(reason, 0) + 1
        if company:
            co = self.per_company.setdefault(company, {})
            co[reason] = co.get(reason, 0) + 1


@dataclass
class CompanyFilterSummary:
    """Rolled-up view of how a company's jobs moved through all filter stages."""
    fetched: int = 0
    qualified: int = 0
    # { reason: count } across all stages
    rejections: dict = field(default_factory=dict)


@dataclass
class FilterResult:
    qualified: list
    no_description: list
    stats: list  # list[FilterStats]
    per_company: dict  # { company_name: CompanyFilterSummary }


def apply_filters(
    postings: list[JobPosting],
    excluded_companies: list[str],
    posted_within: str | None = None,
    cooldown_data=None,  # CooldownData | None — imported lazily to avoid circular imports
    loc_cfg: LocationConfig | None = None,
) -> FilterResult:
    # Default config = remote-US search from Oregon (legacy behavior) so callers
    # that don't pass loc_cfg are unaffected.
    if loc_cfg is None:
        loc_cfg = LocationConfig()
    stats = []
    all_postings = postings  # preserve original list for per-company rollup

    # Stage 0 — Posted-date filtering (optional)
    if posted_within and posted_within in POSTED_WITHIN_DAYS:
        cutoff = datetime.now(timezone.utc) - timedelta(days=POSTED_WITHIN_DAYS[posted_within])
        s0 = FilterStats(stage="posted_date", input_count=len(postings))
        after_s0 = []
        for p in postings:
            parsed = _parse_posted_date(p.posted_date)
            if parsed is None:
                # No date available — keep the posting (don't penalize missing data)
                after_s0.append(p)
                continue
            if parsed >= cutoff:
                after_s0.append(p)
            else:
                s0.reject("too_old", p.company)
        s0.output_count = len(after_s0)
        stats.append(s0)
        postings = after_s0

    # Stage 1 — Title matching
    s1 = FilterStats(stage="title_matching", input_count=len(postings))
    after_s1 = []
    for p in postings:
        if not _TARGET_ROLES.search(p.title):
            s1.reject("no_target_role", p.company)
            continue
        if _SENIORITY_REJECT.search(p.title):
            s1.reject("seniority_keyword", p.company)
            continue
        if _WRONG_ROLE_REJECT.search(p.title):
            s1.reject("wrong_role_type", p.company)
            continue
        after_s1.append(p)
    s1.output_count = len(after_s1)
    stats.append(s1)

    # Stage 2 — Location/remote filtering (mode-aware; see location.py)
    s2 = FilterStats(stage="location_remote", input_count=len(after_s1))
    after_s2 = []
    for p in after_s1:
        desc = p.description_text if p.description_available else ""
        keep, reason = location_verdict(p.location, p.workplace_type, desc, loc_cfg)
        if not keep:
            s2.reject(reason, p.company)
            continue
        after_s2.append(p)
    s2.output_count = len(after_s2)
    stats.append(s2)

    # Stage 3 — Company exclusion (without description split — that happens at the end)
    s3 = FilterStats(stage="company_exclusion", input_count=len(after_s2))
    after_s3 = []
    for p in after_s2:
        if p.company.lower() in excluded_companies:
            s3.reject("excluded_company", p.company)
            continue
        after_s3.append(p)
    s3.output_count = len(after_s3)
    stats.append(s3)

    # Stage 4 — Cooldown and ghost job detection (optional)
    if cooldown_data is not None:
        from .cooldown import normalize_company, normalize_role
        s4 = FilterStats(stage="cooldown_ghost", input_count=len(after_s3))
        after_s4 = []
        for p in after_s3:
            key = (normalize_company(p.company), normalize_role(p.title))
            if key in cooldown_data.cooldown:
                s4.reject("recently_applied_cooldown", p.company)
                continue
            if key in cooldown_data.ghost:
                s4.reject("suspected_ghost_job", p.company)
                continue
            after_s4.append(p)
        s4.output_count = len(after_s4)
        stats.append(s4)
        after_s4_final = after_s4
    else:
        after_s4_final = after_s3

    # Stage 5 — Description-based disqualifiers
    # (scoring also catches these, but we want them visible in the filter funnel
    #  as hard rejections so the per-company breakdown is accurate)
    from .scorer import score_posting, score_posting_no_description
    s5 = FilterStats(stage="description_disqualifiers", input_count=len(after_s4_final))
    after_s5_with_desc = []
    after_s5_no_desc = []
    for p in after_s4_final:
        if not p.description_available:
            # No description — can't check description disqualifiers, pass through
            after_s5_no_desc.append(p)
            continue
        result = score_posting(p)
        if result.description_disqualified:
            s5.reject(result.disqualify_reason, p.company)
            continue
        after_s5_with_desc.append(p)
    s5.output_count = len(after_s5_with_desc) + len(after_s5_no_desc)
    stats.append(s5)

    qualified = after_s5_with_desc
    no_description = after_s5_no_desc

    # Roll up per-company summary across all stages
    company_summary: dict[str, CompanyFilterSummary] = {}
    for p in all_postings:
        s = company_summary.setdefault(p.company, CompanyFilterSummary())
        s.fetched += 1
    for p in qualified + no_description:
        company_summary[p.company].qualified += 1
    for stage in stats:
        for company, reasons in stage.per_company.items():
            s = company_summary.setdefault(company, CompanyFilterSummary())
            for reason, count in reasons.items():
                s.rejections[reason] = s.rejections.get(reason, 0) + count

    return FilterResult(
        qualified=qualified,
        no_description=no_description,
        stats=stats,
        per_company=company_summary,
    )


def title_passes(title: str) -> bool:
    """Quick title check used by SmartRecruiters/Workday before fetching details."""
    if not _TARGET_ROLES.search(title):
        return False
    if _SENIORITY_REJECT.search(title):
        return False
    if _WRONG_ROLE_REJECT.search(title):
        return False
    return True
