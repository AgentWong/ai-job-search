#!/usr/bin/env python3
"""Append a pipeline event to an existing application.

Use this when an application progresses or terminates: an email response
arrives, a phone screen happens, an interview round occurs, the company
rejects, ghosts, the candidate withdraws, an offer is extended, etc.

Usage:
    # Recruiter emailed
    .venv/bin/python scripts/append_event.py <APP_ID> email_response \\
        --date 2026-04-15 [--outcome ghosted|rejected|withdrew|aborted|pending] \\
        [--notes "Recruiter emailed; phone screen scheduled then cancelled"]

    # Phone screen actually happened
    .venv/bin/python scripts/append_event.py <APP_ID> phone_screen \\
        --date 2026-04-20

    # 1st-round interview
    .venv/bin/python scripts/append_event.py <APP_ID> interview_1 \\
        --date 2026-04-26

    # Rejection at 1st round
    .venv/bin/python scripts/append_event.py <APP_ID> interview_1 \\
        --date 2026-04-26 --outcome rejected

    # Outcome-only update on the highest existing stage
    # (overwrite blank/pending → terminal state at that stage)
    .venv/bin/python scripts/append_event.py <APP_ID> --update-outcome rejected

Stage names:
    applied, email_response, phone_screen,
    interview_1, interview_2, interview_3, ... interview_N,
    offer

Outcome enum (blank means advanced to a later stage):
    pending, no_response, rejected, ghosted, withdrew, aborted,
    accepted, declined
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

INTERVIEW_RE = re.compile(r"^interview_(\d+)$")
VALID_STAGES_PREFIXES = ("applied", "email_response", "phone_screen", "offer")
VALID_OUTCOMES = (
    "", "pending", "no_response", "rejected", "ghosted",
    "withdrew", "aborted", "accepted", "declined",
)


def stage_index(stage: str) -> int:
    if stage == "applied":
        return 0
    if stage == "email_response":
        return 1
    if stage == "phone_screen":
        return 2
    m = INTERVIEW_RE.match(stage)
    if m:
        return 2 + int(m.group(1))
    if stage == "offer":
        return 1_000_000
    return -1


def is_valid_stage(stage: str) -> bool:
    return stage in VALID_STAGES_PREFIXES or bool(INTERVIEW_RE.match(stage))


def read_csv(path: Path, header: list[str]) -> list[dict]:
    if not path.exists():
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(2)
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
    p = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("app_id", help="Application identifier")
    p.add_argument("stage", nargs="?", default="",
                   help="Event stage: applied, email_response, phone_screen, "
                        "interview_N, offer")
    p.add_argument("--date", default="",
                   help="Event date YYYY-MM-DD (optional, recommended)")
    p.add_argument("--outcome", default="", choices=VALID_OUTCOMES,
                   help="Outcome at this stage (blank means advanced)")
    p.add_argument("--notes", default="")
    p.add_argument("--update-outcome", default="",
                   help="Update the outcome on the highest existing stage "
                        "for this app instead of appending a new event")
    p.add_argument("--apps-csv", default="job_search_log/applications.csv")
    p.add_argument("--events-csv", default="job_search_log/pipeline_events.csv")
    args = p.parse_args(argv)

    apps = read_csv(Path(args.apps_csv), APPS_HEADER)
    events = read_csv(Path(args.events_csv), EVENTS_HEADER)

    if not any(a["app_id"] == args.app_id for a in apps):
        print(f"Error: app_id {args.app_id} not found in {args.apps_csv}",
              file=sys.stderr)
        return 1

    if args.update_outcome:
        if args.update_outcome not in VALID_OUTCOMES:
            print(f"Invalid outcome: {args.update_outcome}", file=sys.stderr)
            return 2
        # Find the highest existing event for this app
        ev_for_app = [(i, e) for i, e in enumerate(events) if e["app_id"] == args.app_id]
        if not ev_for_app:
            print(f"No events found for app {args.app_id}", file=sys.stderr)
            return 1
        ev_for_app.sort(key=lambda t: stage_index(t[1]["event_stage"]))
        idx, _ = ev_for_app[-1]
        events[idx]["event_outcome"] = args.update_outcome
        if args.notes:
            existing = events[idx].get("event_notes", "")
            events[idx]["event_notes"] = (existing + "; " + args.notes).strip("; ")
        write_csv(Path(args.events_csv), EVENTS_HEADER, events)
        print(f"Updated outcome on highest stage for {args.app_id} → {args.update_outcome}")
        return 0

    if not args.stage:
        print("Error: stage required when not using --update-outcome",
              file=sys.stderr)
        return 2

    if not is_valid_stage(args.stage):
        print(f"Invalid stage: {args.stage}. Valid: applied, email_response, "
              f"phone_screen, interview_N (e.g. interview_1), offer",
              file=sys.stderr)
        return 2

    if args.date and not re.match(r"^\d{4}-\d{2}-\d{2}$", args.date):
        print(f"Error: --date must be YYYY-MM-DD, got {args.date}", file=sys.stderr)
        return 2

    # Reject duplicate (app_id, stage) — user likely wants --update-outcome
    for ev in events:
        if ev["app_id"] == args.app_id and ev["event_stage"] == args.stage:
            print(f"Error: an event for ({args.app_id}, {args.stage}) already "
                  f"exists. Use --update-outcome to change its outcome, or "
                  f"edit the CSV directly.", file=sys.stderr)
            return 1

    # If a new mid-pipeline stage is added (e.g. phone_screen), and a higher
    # stage already exists, that's fine. But if a higher stage exists with a
    # terminal outcome, we should warn. For now, just append.
    events.append({
        "app_id": args.app_id,
        "event_stage": args.stage,
        "event_date": args.date,
        "event_outcome": args.outcome,
        "event_notes": args.notes,
    })

    # Re-sort: by app_id, then stage_index
    events.sort(key=lambda r: (r["app_id"], stage_index(r["event_stage"])))

    write_csv(Path(args.events_csv), EVENTS_HEADER, events)
    print(f"Appended event: {args.app_id} {args.stage} "
          f"date={args.date or '-'} outcome={args.outcome or 'advanced'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
