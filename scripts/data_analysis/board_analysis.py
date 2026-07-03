"""ATS board / platform effectiveness over the analysis window."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path

from .loaders import filter_by_date, read_csv, safe_int

# Rejection reasons that signal "this company / platform isn't producing
# remote-eligible US infra roles" — the user can act on them by removing
# companies from company_targets_ats.csv or tightening exclusions.yml.
# Informational reasons (too_old, no_target_role, seniority_keyword, etc.)
# are expected high-volume noise and are not surfaced as actionable.
ACTIONABLE_REJECTION_REASONS = {
    "no_remote_signal",
    "non_us_geography",
    "hybrid_or_onsite",
    "state_restriction",   # config-driven (candidate's state); was "idaho_restriction"
    "idaho_restriction",   # legacy label kept so historical CSV rows still classify
    "wrong_metro",         # local-mode: posting outside the configured city/state
    "remote_not_local",    # local-mode (strict): remote role dropped when only local wanted
    "excluded_company",  # if non-zero, exclusions list has companies still being scraped
}


def analyze(
    *,
    today: date,
    window_days: int,
    tracking_dir: Path,
    inclusions: dict,
) -> dict:
    cutoff = today.fromordinal(today.toordinal() - window_days)

    board_tier: dict[str, str] = {}
    board_name: dict[str, str] = {}
    # Map any tracked board key (with or without wildcard, with or without subdomain)
    # to a single canonical config domain. Tracking CSVs sometimes store the bare
    # apex ("applytojob.com") instead of the wildcard form ("*.applytojob.com").
    canonical_for: dict[str, str] = {}
    for tier in ("primary", "watch", "secondary"):
        for entry in inclusions.get("job_boards", {}).get(tier, []):
            domain = entry.get("domain", "").strip()
            if not domain:
                continue
            board_tier[domain] = tier
            board_name[domain] = entry.get("name", domain)
            canonical_for[domain] = domain
            if domain.startswith("*."):
                apex = domain[2:]
                canonical_for[apex] = domain
                canonical_for[f"www.{apex}"] = domain

    board_rows = filter_by_date(read_csv(tracking_dir / "ats_board_effectiveness.csv"), "date", cutoff)

    agg: dict[str, dict] = defaultdict(lambda: {"runs": 0, "found": 0, "qualified": 0, "queries": 0})
    for r in board_rows:
        board = r.get("board", "").strip()
        if not board:
            continue
        canonical = canonical_for.get(board, board)
        agg[canonical]["runs"] += 1
        agg[canonical]["found"] += safe_int(r.get("found"))
        agg[canonical]["qualified"] += safe_int(r.get("qualified"))
        agg[canonical]["queries"] += safe_int(r.get("queries"))

    board_summaries = []
    seen = set()
    for board, m in agg.items():
        seen.add(board)
        rate = (m["qualified"] / m["found"] * 100.0) if m["found"] else 0.0
        tier = board_tier.get(board)
        board_summaries.append({
            "board": board,
            "name": board_name.get(board, board),
            "current_tier": tier or "untracked_in_config",
            "runs": m["runs"],
            "found": m["found"],
            "qualified": m["qualified"],
            "queries": m["queries"],
            "qual_rate_pct": round(rate, 2),
            "recommendation": _classify_board(tier, m["runs"], m["found"], m["qualified"]),
        })

    # Boards configured but never appeared in tracking window — flag separately
    silent_boards = [
        {"board": d, "name": board_name[d], "current_tier": board_tier[d]}
        for d in board_tier if d not in seen
    ]

    board_summaries.sort(key=lambda r: (r["current_tier"], -r["found"], r["board"]))

    # ATS API platform effectiveness (separate scraper, not Firecrawl)
    api_platform_rows = filter_by_date(read_csv(tracking_dir / "ats_api_platform_effectiveness.csv"), "date", cutoff)
    api_agg: dict[str, dict] = defaultdict(lambda: {"runs": 0, "fetched": 0, "qualified": 0, "companies": 0})
    for r in api_platform_rows:
        plat = r.get("platform", "").strip()
        if not plat:
            continue
        api_agg[plat]["runs"] += 1
        api_agg[plat]["fetched"] += safe_int(r.get("fetched"))
        api_agg[plat]["qualified"] += safe_int(r.get("qualified"))
        api_agg[plat]["companies"] += safe_int(r.get("companies"))

    # Per-(platform, reason) rejection rollup from the normalized rejection CSV.
    # If the file is missing (not yet generated) we fall back to parsing the
    # `rejection_breakdown` column on the per-company effectiveness CSV.
    rejection_by_platform, rejection_by_company = _load_rejection_breakdown(tracking_dir, cutoff)

    api_platform_summaries = []
    for plat, m in api_agg.items():
        plat_rej = rejection_by_platform.get(plat, {})
        actionable_total = sum(c for r, c in plat_rej.items() if r in ACTIONABLE_REJECTION_REASONS)
        api_platform_summaries.append({
            "platform": plat,
            "runs": m["runs"],
            "fetched": m["fetched"],
            "qualified": m["qualified"],
            "company_run_pairs": m["companies"],
            "qual_rate_pct": round((m["qualified"] / m["fetched"] * 100.0) if m["fetched"] else 0.0, 2),
            "rejection_breakdown": dict(sorted(plat_rej.items(), key=lambda x: -x[1])),
            "actionable_rejections": actionable_total,
            "actionable_rejection_pct": round((actionable_total / m["fetched"] * 100.0) if m["fetched"] else 0.0, 2),
        })
    api_platform_summaries.sort(key=lambda r: -r["fetched"])

    # Per-company actionable-rejection leaderboard. Only surfaces companies
    # whose rejections are dominated by remote/geo/hybrid signals — these
    # are the candidates for removal from company_targets_ats.csv.
    company_actionable = _build_company_actionable_summary(rejection_by_company)

    return {
        "window_days": window_days,
        "cutoff_date": cutoff.isoformat(),
        "firecrawl_boards": board_summaries,
        "silent_boards_in_config": silent_boards,
        "ats_api_platforms": api_platform_summaries,
        "ats_api_company_actionable_rejections": company_actionable,
    }


def _load_rejection_breakdown(tracking_dir: Path, cutoff: date):
    """Return (per_platform, per_company) rejection-reason aggregates.

    Prefers the normalized ats_api_company_rejections.csv; falls back to
    parsing the inline `rejection_breakdown` column on the company effectiveness
    CSV for older runs that pre-date the normalized tracker.
    """
    per_platform: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    per_company: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))

    rej_path = tracking_dir / "ats_api_company_rejections.csv"
    if rej_path.exists():
        for r in filter_by_date(read_csv(rej_path), "date", cutoff):
            plat = (r.get("platform") or "").strip() or "Unknown"
            company = (r.get("company") or "").strip()
            reason = (r.get("reason") or "").strip()
            count = safe_int(r.get("count"))
            if not reason or count <= 0:
                continue
            per_platform[plat][reason] += count
            if company:
                per_company[(company, plat)][reason] += count
        return per_platform, per_company

    # Fallback: parse the inline column on the company CSV.
    for r in filter_by_date(read_csv(tracking_dir / "ats_api_company_effectiveness.csv"), "date", cutoff):
        plat = (r.get("platform") or "").strip() or "Unknown"
        company = (r.get("company") or "").strip()
        breakdown = (r.get("rejection_breakdown") or "").strip()
        if not breakdown:
            continue
        for chunk in breakdown.split(";"):
            if ":" not in chunk:
                continue
            reason, _, n = chunk.rpartition(":")
            count = safe_int(n)
            if count <= 0:
                continue
            per_platform[plat][reason] += count
            if company:
                per_company[(company, plat)][reason] += count

    return per_platform, per_company


def _build_company_actionable_summary(
    rejection_by_company: dict[tuple[str, str], dict[str, int]],
) -> list[dict]:
    """Companies whose rejections are dominated by actionable reasons.

    Sorted by actionable-reason count desc. Only includes companies where
    actionable rejections are >= 5 (filter out incidental noise).
    """
    rows = []
    for (company, plat), reasons in rejection_by_company.items():
        actionable = {r: c for r, c in reasons.items() if r in ACTIONABLE_REJECTION_REASONS}
        actionable_total = sum(actionable.values())
        if actionable_total < 5:
            continue
        all_total = sum(reasons.values())
        rows.append({
            "company": company,
            "platform": plat,
            "actionable_rejections": actionable_total,
            "all_rejections": all_total,
            "actionable_share_pct": round((actionable_total / all_total * 100.0) if all_total else 0.0, 1),
            "reasons": dict(sorted(actionable.items(), key=lambda x: -x[1])),
        })
    rows.sort(key=lambda r: -r["actionable_rejections"])
    return rows


def _classify_board(tier: str | None, runs: int, found: int, qualified: int) -> str:
    if tier is None:
        return "untracked_in_config"
    if runs < 3:
        return "no_data"

    qual_rate = (qualified / found * 100.0) if found else 0.0

    # Rules cribbed from config.yml inline thresholds (1.5% qual rate, 30 runs, etc.)
    if tier == "secondary":
        if qualified >= 1 and qual_rate >= 1.5 and runs >= 10:
            return "promote_to_primary"
        if found >= (10 * runs) and runs >= 10:
            return "promote_to_watch"
        return "keep_secondary"

    if tier == "watch":
        if qualified >= 1 and qual_rate >= 1.5 and runs >= 30:
            return "promote_to_primary"
        if qualified == 0 and runs >= 30 and (found / runs) < 10:
            return "demote_to_secondary"
        return "keep_watch"

    # primary
    if qualified == 0 and runs >= 30:
        return "demote_to_watch"
    return "keep_primary"
