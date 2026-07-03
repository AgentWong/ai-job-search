#!/usr/bin/env python3
"""Append a new application row + initial 'applied' event to the CSVs.

Used by the process-clippings workflow to register a freshly clipped job
posting.

Usage:
    .venv/bin/python scripts/append_application.py \\
        --company "Acme Corp" \\
        --role "DevOps Engineer" \\
        --date-applied 2026-04-28 \\
        --source "jobs.lever.co" \\
        --original-source "ats-platform" \\
        --match 85 \\
        --resume-format 2-page \\
        --used-cover-letter true \\
        [--application-notes "..."]

After append, run:
    .venv/bin/python scripts/regenerate_dashboard.py
    .venv/bin/python scripts/extract_sankey_data.py
    .venv/bin/python scripts/sankey_d3.py
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

APPS_HEADER = [
    "app_id", "company", "role", "date_applied", "source", "original_source",
    "match_pct", "resume_format", "used_cover_letter", "application_notes",
]

EVENTS_HEADER = [
    "app_id", "event_stage", "event_date", "event_outcome", "event_notes",
]


def slugify(text: str) -> str:
    text = (text or "").lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "unknown"


def read_csv(path: Path, header: list[str]) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, header: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in header})


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--company", required=True)
    p.add_argument("--role", required=True)
    p.add_argument("--date-applied", required=True,
                   help="YYYY-MM-DD")
    p.add_argument("--source", default="")
    p.add_argument("--original-source", default="")
    p.add_argument("--match", default="",
                   help="Integer 0-100, or empty for N/A")
    p.add_argument("--resume-format", choices=["1-page", "2-page", ""], default="")
    p.add_argument("--used-cover-letter", choices=["true", "false"], default="false")
    p.add_argument("--application-notes", default="")
    p.add_argument("--apps-csv", default="job_search_log/applications.csv")
    p.add_argument("--events-csv", default="job_search_log/pipeline_events.csv")
    p.add_argument("--allow-duplicate", action="store_true",
                   help="Allow multiple apps with the same company+date "
                        "(suffix the app_id with -2, -3, ...)")
    args = p.parse_args(argv)

    if not re.match(r"^\d{4}-\d{2}-\d{2}$", args.date_applied):
        print(f"Error: --date-applied must be YYYY-MM-DD, got {args.date_applied}",
              file=sys.stderr)
        return 2

    if args.match:
        try:
            int(args.match)
        except ValueError:
            print(f"Error: --match must be an integer, got {args.match}",
                  file=sys.stderr)
            return 2

    apps_path = Path(args.apps_csv)
    events_path = Path(args.events_csv)

    apps = read_csv(apps_path, APPS_HEADER)
    events = read_csv(events_path, EVENTS_HEADER)

    base_app_id = f"{slugify(args.company)}__{args.date_applied}"
    app_id = base_app_id
    existing_ids = {a["app_id"] for a in apps}
    if app_id in existing_ids:
        if not args.allow_duplicate:
            print(f"Error: app_id {app_id} already exists. Use "
                  f"--allow-duplicate to add a second row for the same "
                  f"company+date.", file=sys.stderr)
            return 1
        suffix = 2
        while f"{base_app_id}-{suffix}" in existing_ids:
            suffix += 1
        app_id = f"{base_app_id}-{suffix}"

    apps.append({
        "app_id": app_id,
        "company": args.company,
        "role": args.role,
        "date_applied": args.date_applied,
        "source": args.source,
        "original_source": args.original_source,
        "match_pct": args.match,
        "resume_format": args.resume_format,
        "used_cover_letter": args.used_cover_letter,
        "application_notes": args.application_notes,
    })

    events.append({
        "app_id": app_id,
        "event_stage": "applied",
        "event_date": args.date_applied,
        "event_outcome": "no_response",
        "event_notes": "",
    })

    apps.sort(key=lambda r: (r.get("date_applied", ""), r.get("company", "").lower()))

    write_csv(apps_path, APPS_HEADER, apps)
    write_csv(events_path, EVENTS_HEADER, events)

    print(f"Appended {app_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
