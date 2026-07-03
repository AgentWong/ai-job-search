"""
One-off migration: add `rejection_breakdown` column to
ats_api_company_effectiveness.csv.

Existing rows have no breakdown data — the column is left blank. Future runs
will populate it. Safe to re-run; detects already-migrated header.

Usage:
    .venv/bin/python -m scripts.effectiveness_tracker.migrate_ats_company_breakdown
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = REPO_ROOT / "results" / "tracking" / "data" / "ats_api_company_effectiveness.csv"
NEW_COLUMN = "rejection_breakdown"


def main() -> int:
    if not CSV_PATH.exists():
        print(f"Nothing to migrate: {CSV_PATH} does not exist")
        return 0

    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        print("Empty CSV; nothing to do")
        return 0

    header = rows[0]
    if NEW_COLUMN in header:
        print(f"Already migrated: '{NEW_COLUMN}' present in header")
        return 0

    header.append(NEW_COLUMN)
    for row in rows[1:]:
        row.append("")

    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    print(f"Migrated {len(rows) - 1} rows; added '{NEW_COLUMN}' column")
    return 0


if __name__ == "__main__":
    sys.exit(main())
