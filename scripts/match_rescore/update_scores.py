#!/usr/bin/env python3
"""Apply rescored match_pct values to applications.csv.

Reads one or more JSON files of {app_id: new_score}, validates that every
app_id exists in the CSV, and rewrites applications.csv in place. The original
file is backed up to applications.csv.bak before the rewrite.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = REPO_ROOT / "job_search_log" / "applications.csv"


def load_scores(paths: list[Path]) -> dict[str, int]:
    scores: dict[str, int] = {}
    for path in paths:
        data = json.loads(path.read_text())
        # Accept either {app_id: score} or {app_id: {"score": N, "reason": "..."}}
        for app_id, value in data.items():
            score = value if isinstance(value, int) else value.get("score")
            if score is None:
                continue
            if not isinstance(score, int) or not 0 <= score <= 100:
                raise ValueError(f"{app_id}: invalid score {score!r}")
            if app_id in scores and scores[app_id] != score:
                raise ValueError(f"{app_id}: conflicting scores {scores[app_id]} vs {score}")
            scores[app_id] = score
    return scores


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("score_files", nargs="+", type=Path,
                        help="JSON file(s) mapping app_id -> new score")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print changes without modifying the CSV")
    args = parser.parse_args()

    scores = load_scores(args.score_files)
    rows = list(csv.DictReader(CSV_PATH.open()))
    fieldnames = list(rows[0].keys()) if rows else []

    csv_ids = {row["app_id"] for row in rows}
    unknown = sorted(scores.keys() - csv_ids)
    if unknown:
        print(f"ERROR: {len(unknown)} app_ids not in CSV:", file=sys.stderr)
        for app_id in unknown:
            print(f"  {app_id}", file=sys.stderr)
        sys.exit(1)

    changes = []
    for row in rows:
        app_id = row["app_id"]
        if app_id not in scores:
            continue
        old = row["match_pct"]
        new = str(scores[app_id])
        if old != new:
            changes.append((app_id, old, new))
            row["match_pct"] = new

    print(f"applying {len(changes)} score changes "
          f"({len(scores) - len(changes)} unchanged)")
    for app_id, old, new in changes:
        print(f"  {app_id}: {old or '∅'} -> {new}")

    if args.dry_run:
        print("(dry-run, CSV not modified)")
        return

    backup = CSV_PATH.with_suffix(".csv.bak")
    shutil.copy2(CSV_PATH, backup)
    print(f"backed up: {backup.relative_to(REPO_ROOT)}")

    with CSV_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote: {CSV_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
