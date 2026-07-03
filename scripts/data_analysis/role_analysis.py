"""Role effectiveness: ATS volume, browser volume, and applications-actually-submitted."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path

from .loaders import filter_by_date, parse_iso_date, read_csv, safe_int


def _normalize_role(s: str) -> str:
    """Loose normalization for fuzzy role matching across sources."""
    return " ".join((s or "").lower().split())


def _bucket_role(title: str, configured_roles: list[str]) -> str | None:
    """Map a free-text role string from applications.csv to a configured role."""
    norm = _normalize_role(title)
    if not norm:
        return None
    # Direct substring match (longest first to prefer "Site Reliability Engineer" over "Reliability Engineer")
    for role in sorted(configured_roles, key=len, reverse=True):
        if _normalize_role(role) in norm:
            return role
    # Common aliases
    aliases = {
        "sre": "Site Reliability Engineer",
        "site reliability": "Site Reliability Engineer",
        "devops": "DevOps Engineer",
        "platform engineer": "Platform Engineer",
        "cloud engineer": "Cloud Engineer",
        "infrastructure engineer": "Infrastructure Engineer",
        "systems engineer": "Systems Engineer",
        "mlops": "MLOps Engineer",
    }
    for alias, mapped in aliases.items():
        if alias in norm and mapped in configured_roles:
            return mapped
    return None


def analyze(
    *,
    today: date,
    window_days: int,
    tracking_dir: Path,
    applications_csv: Path,
    inclusions: dict,
) -> dict:
    cutoff = today.fromordinal(today.toordinal() - window_days)

    primary_roles = [r["name"] for r in inclusions.get("target_roles", {}).get("primary", [])]
    secondary_roles = [r["name"] for r in inclusions.get("target_roles", {}).get("secondary", [])]
    # local_only roles only run in local mode, but they're still configured —
    # include them so historical tracking rows attribute correctly instead of
    # landing in untracked_role_strings_in_csvs.
    local_only_roles = [r["name"] for r in inclusions.get("target_roles", {}).get("local_only", [])]
    all_configured = primary_roles + secondary_roles + local_only_roles
    role_tier = {r: "primary" for r in primary_roles}
    role_tier.update({r: "secondary" for r in secondary_roles})
    role_tier.update({r: "local_only" for r in local_only_roles})

    # ATS role effectiveness (firecrawl-based ATS platform search)
    ats_rows = filter_by_date(read_csv(tracking_dir / "ats_role_effectiveness.csv"), "date", cutoff)
    # Browser role effectiveness (hiringcafe; plus historical linkedin/builtin rows)
    browser_rows = filter_by_date(read_csv(tracking_dir / "browser_role_effectiveness.csv"), "date", cutoff)

    by_role: dict[str, dict] = {
        r: {
            "tier": role_tier[r],
            "ats_found": 0,
            "ats_qualified": 0,
            "ats_runs": 0,
            "browser_found": 0,
            "browser_qualified": 0,
            "browser_runs": 0,
            "applications": 0,
            "applications_with_response": 0,
        }
        for r in all_configured
    }
    untracked_in_config: list[str] = []  # roles seen in CSVs but not in config.yml

    for r in ats_rows:
        role = r.get("role", "").strip()
        if not role:
            continue
        if role not in by_role:
            untracked_in_config.append(role)
            continue
        by_role[role]["ats_found"] += safe_int(r.get("found"))
        by_role[role]["ats_qualified"] += safe_int(r.get("qualified"))
        by_role[role]["ats_runs"] += 1

    for r in browser_rows:
        role = r.get("role", "").strip()
        if not role:
            continue
        if role not in by_role:
            untracked_in_config.append(role)
            continue
        by_role[role]["browser_found"] += safe_int(r.get("found"))
        by_role[role]["browser_qualified"] += safe_int(r.get("qualified"))
        by_role[role]["browser_runs"] += 1

    # Applications you actually submitted, joined to configured roles
    apps = read_csv(applications_csv)
    apps_in_window = []
    for a in apps:
        d = parse_iso_date(a.get("date_applied", ""))
        if d is None or d >= cutoff:
            apps_in_window.append(a)
    unattributed_apps = 0
    for a in apps_in_window:
        bucket = _bucket_role(a.get("role", ""), all_configured)
        if bucket is None:
            unattributed_apps += 1
            continue
        by_role[bucket]["applications"] += 1

    # Build classification + summary
    role_summaries = []
    for role, m in by_role.items():
        total_found = m["ats_found"] + m["browser_found"]
        total_qualified = m["ats_qualified"] + m["browser_qualified"]
        total_runs = m["ats_runs"] + m["browser_runs"]
        qual_rate = (total_qualified / total_found * 100.0) if total_found else 0.0

        classification = _classify_role(
            tier=m["tier"],
            total_found=total_found,
            total_qualified=total_qualified,
            applications=m["applications"],
            total_runs=total_runs,
            window_days=window_days,
            qual_rate_pct=qual_rate,
        )

        # Cost-aware flag: high-volume noise burns Firecrawl credits and browser-workflow time
        # even when it produces a few qualified hits. The LLM can weight this against the
        # bare classification.
        high_volume_low_yield = (
            total_found >= 500 and qual_rate < 1.0 and m["applications"] < 3
        )

        role_summaries.append({
            "role": role,
            "tier": m["tier"],
            "ats_found": m["ats_found"],
            "ats_qualified": m["ats_qualified"],
            "browser_found": m["browser_found"],
            "browser_qualified": m["browser_qualified"],
            "total_found": total_found,
            "total_qualified": total_qualified,
            "qual_rate_pct": round(qual_rate, 2),
            "applications": m["applications"],
            "total_runs": total_runs,
            "classification": classification,
            "high_volume_low_yield": high_volume_low_yield,
        })

    role_summaries.sort(key=lambda r: (r["tier"], -r["total_found"], r["role"]))

    return {
        "window_days": window_days,
        "cutoff_date": cutoff.isoformat(),
        "total_applications_in_window": len(apps_in_window),
        "applications_unattributed_to_role": unattributed_apps,
        "untracked_role_strings_in_csvs": sorted(set(untracked_in_config)),
        "roles": role_summaries,
    }


def _classify_role(
    *,
    tier: str,
    total_found: int,
    total_qualified: int,
    applications: int,
    total_runs: int,
    window_days: int,
    qual_rate_pct: float,
) -> str:
    """
    Classification heuristic:
      keep_primary           — already primary, still earning its slot
      promote_to_primary     — secondary that's pulling its weight
      keep_secondary         — secondary doing fine where it is
      demote_to_secondary    — primary that's underperforming
      removal_candidate      — high volume, zero LLM-qualified AND zero applications
                               (the "Systems Engineer" case)
      keep_local_only        — a local_only-tier role: intentionally high-noise
                               and searched only in local mode, so it's never
                               auto-promoted or flagged for removal
      no_data                — too few runs to judge
    """
    if total_runs < 3:
        return "no_data"

    # local_only roles are deliberately high-noise generalist titles, gated to
    # local mode — don't subject them to the promotion/removal heuristics below.
    if tier == "local_only":
        return "keep_local_only"

    high_volume = total_found >= 25  # 25+ found in window suggests the search is producing inventory
    no_qualified = total_qualified == 0
    no_apps = applications == 0
    earning = total_qualified >= 1 or applications >= 1

    if high_volume and no_qualified and no_apps:
        return "removal_candidate"

    if tier == "primary":
        if earning:
            return "keep_primary"
        return "demote_to_secondary"

    # tier == "secondary"
    if earning and total_found >= 10:
        return "promote_to_primary"
    return "keep_secondary"
