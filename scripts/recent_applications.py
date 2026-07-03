"""
List recent applications for cooldown filtering.

Reads job_search_log/applications.csv and prints rows where date_applied is
within the past N days (default: 60). LLM workflows consume the output and
apply fuzzy matching against candidate positions.

Output formats:
  default (table)  Pipe-separated: "Company | Role | YYYY-MM-DD"
  --json           JSON array of {company, role, date_applied, app_id}
"""

import argparse
import csv
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

DEFAULT_APPS_CSV = Path("job_search_log/applications.csv")
DEFAULT_DAYS = 60


def collect_recent(apps_csv: Path, days: int, today: date) -> list[dict]:
    if not apps_csv.exists():
        return []
    cutoff = today - timedelta(days=days)
    rows: list[dict] = []
    with open(apps_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            company = (row.get("company") or "").strip()
            role = (row.get("role") or "").strip()
            date_applied = (row.get("date_applied") or "").strip()
            if not company or not role or not date_applied:
                continue
            try:
                applied = datetime.strptime(date_applied, "%Y-%m-%d").date()
            except ValueError:
                continue
            if applied >= cutoff:
                rows.append({
                    "company": company,
                    "role": role,
                    "date_applied": date_applied,
                    "app_id": (row.get("app_id") or "").strip(),
                })
    rows.sort(key=lambda r: r["date_applied"], reverse=True)
    return rows


def main() -> int:
    p = argparse.ArgumentParser(
        description="List applications from job_search_log/applications.csv "
                    "within the past N days (default 60).",
    )
    p.add_argument("--apps-csv", default=str(DEFAULT_APPS_CSV))
    p.add_argument(
        "--days", type=int, default=DEFAULT_DAYS,
        help="Lookback window in days (default: 60)",
    )
    p.add_argument("--json", action="store_true", help="JSON output instead of pipe-separated table")
    args = p.parse_args()

    rows = collect_recent(Path(args.apps_csv), args.days, date.today())

    if args.json:
        json.dump(rows, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if not rows:
        print(f"# No applications in the past {args.days} days")
        return 0

    print(f"# Applications in the past {args.days} days ({len(rows)} total)")
    print("# Company | Role | Date Applied")
    for r in rows:
        print(f"{r['company']} | {r['role']} | {r['date_applied']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
