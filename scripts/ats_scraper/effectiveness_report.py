"""
Analyze ats_api_company_effectiveness.csv and print a structured report
for the ats-api-search workflow. Replaces ad-hoc Python in the orchestrator.

Usage:
    .venv/bin/python -m scripts.ats_scraper.effectiveness_report
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPANY_CSV = REPO_ROOT / "results" / "tracking" / "data" / "ats_api_company_effectiveness.csv"

# All known ATS platforms — used to detect malformed rows from older CSV data
# (e.g. "Command|Link" written without quoting produced "Command" / "Link" columns).
_KNOWN_PLATFORMS = {
    "Ashby", "Greenhouse", "Lever", "Pinpoint", "Recruitee",
    "Rippling", "SmartRecruiters", "Workday", "Unknown",
}

# Platforms where 0 fetched is expected (title-filtered at fetch time)
_PREFILTERED_PLATFORMS = {"Workday", "SmartRecruiters"}

# Minimum runs before recommending removal
_REMOVAL_THRESHOLD = 30


def _load_company_data(csv_path: Path) -> dict[str, list[dict]]:
    companies: dict[str, list[dict]] = defaultdict(list)
    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            # Skip malformed rows where the platform column isn't a known platform.
            # This happens when a company name containing "|" was written unquoted
            # in older CSV versions, causing the parser to mis-split the columns.
            if row.get("platform", "") not in _KNOWN_PLATFORMS:
                continue
            companies[row["company"]].append(row)
    return companies


def _safe_int(val: str) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def main() -> int:
    if not COMPANY_CSV.exists():
        print(json.dumps({"error": f"CSV not found: {COMPANY_CSV}"}))
        return 1

    companies = _load_company_data(COMPANY_CSV)

    max_runs = max(len(v) for v in companies.values()) if companies else 0
    run_counts = sorted(set(len(v) for v in companies.values()))

    # Companies with 0 qualified across 3+ runs and fetched > 0
    never_qualified: list[tuple[str, int, int, str]] = []
    # Companies with 0 fetched on non-prefiltered platforms across 2+ runs
    zero_fetched: list[tuple[str, int, str]] = []
    # Companies that have hit the removal threshold (30+ runs, 0 qualified, 0 fetched)
    removal_candidates: list[tuple[str, int, str]] = []

    for company, runs in companies.items():
        n = len(runs)
        platform = runs[0].get("platform", "unknown")
        total_qualified = sum(_safe_int(r["qualified"]) for r in runs)
        total_fetched = sum(_safe_int(r["fetched"]) for r in runs)

        if n >= 3 and total_qualified == 0 and total_fetched > 0:
            never_qualified.append((company, n, total_fetched, platform))

        if n >= 2 and total_fetched == 0 and platform not in _PREFILTERED_PLATFORMS:
            zero_fetched.append((company, n, platform))

        if n >= _REMOVAL_THRESHOLD and total_qualified == 0 and total_fetched == 0:
            removal_candidates.append((company, n, platform))

    never_qualified.sort(key=lambda x: (-x[1], -x[2]))
    zero_fetched.sort(key=lambda x: -x[1])
    removal_candidates.sort(key=lambda x: -x[1])

    result = {
        "max_runs": max_runs,
        "run_count_distribution": run_counts,
        "never_qualified_3plus_runs": [
            {"company": c, "runs": n, "total_fetched": f, "platform": p}
            for c, n, f, p in never_qualified
        ],
        "zero_fetched_non_prefiltered": [
            {"company": c, "runs": n, "platform": p}
            for c, n, p in zero_fetched
        ],
        "removal_candidates_30plus_runs": [
            {"company": c, "runs": n, "platform": p}
            for c, n, p in removal_candidates
        ],
        "notes": (
            f"Max runs is {max_runs}. "
            f"Removal threshold is {_REMOVAL_THRESHOLD} runs. "
            + ("No companies at removal threshold yet." if not removal_candidates
               else f"{len(removal_candidates)} companies at removal threshold.")
        ),
    }

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
