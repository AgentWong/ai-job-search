#!/usr/bin/env python3
"""Extract Sankey diagram counts from the structured pipeline CSVs.

Reads:
    job_search_log/applications.csv     application metadata
    job_search_log/pipeline_events.csv  pipeline events (one row per stage)

Writes:
    job_search_log/sankey_data.json     stage-bucketed counts per cohort

For each application, we determine its furthest stage reached (the event with
the highest stage index) and the outcome at that stage. Buckets are
`<stage>_<outcome>` — e.g., `email_ghosted`, `interview_1_rejected`,
`applied_no_response`.

Stage order
-----------
    applied (0) → email_response (1) → phone_screen (2)
                → interview_1 (3) → interview_2 (4) → ... interview_N (2+N)
                → offer (very high index)

Stage indexes for interview rounds scale with N, so adding interview_3,
interview_4, etc. requires no code change.

Outcomes
--------
    "" / blank   → advanced (must have a higher-stage event)
    pending      → currently waiting at this stage
    no_response  → applied with no contact (only valid at stage applied)
    rejected, ghosted, withdrew, aborted → terminated at this stage
    accepted, declined → only valid at stage offer

Usage:
    .venv/bin/python scripts/extract_sankey_data.py [--verbose]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

MONTH_RE = re.compile(r"^(\d{4}-\d{2})-\d{2}$")
INTERVIEW_RE = re.compile(r"^interview_(\d+)$")

MONTH_NAMES = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
    5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
    9: "Sept", 10: "Oct", 11: "Nov", 12: "Dec",
}


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


def stage_label(stage: str) -> str:
    """Pretty label for display."""
    if stage == "applied":
        return "Applied"
    if stage == "email_response":
        return "Email Response"
    if stage == "phone_screen":
        return "Phone Screen"
    m = INTERVIEW_RE.match(stage)
    if m:
        n = int(m.group(1))
        return f"{n}{ordinal_suffix(n)} Interview"
    if stage == "offer":
        return "Offer"
    return stage


def ordinal_suffix(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def read_csv_dicts(path: Path) -> list[dict]:
    if not path.exists():
        print(f"Error: {path} not found", file=sys.stderr)
        sys.exit(2)
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def classify_application(events_for_app: list[dict]) -> tuple[str, str]:
    """Given all events for one application, return (furthest_stage, outcome).

    The furthest stage is the event with the highest stage_index. The outcome
    is that event's event_outcome (or "advanced" if blank but it shouldn't be
    blank at the highest stage — that's an inconsistent record).
    """
    if not events_for_app:
        return ("applied", "unclassified")

    sorted_events = sorted(events_for_app, key=lambda e: stage_index(e["event_stage"]))
    highest = sorted_events[-1]
    stage = highest["event_stage"]
    outcome = (highest.get("event_outcome") or "").strip()
    if not outcome:
        # Highest stage with blank outcome → treat as pending
        outcome = "pending"
    return (stage, outcome)


def app_month(date_applied: str) -> str | None:
    m = MONTH_RE.match(date_applied or "")
    return m.group(1) if m else None


def format_month_range(months: list[str]) -> str:
    if not months:
        return ""
    ms = sorted(set(months))
    first_y, first_m = ms[0].split("-")
    last_y, last_m = ms[-1].split("-")
    first_name = MONTH_NAMES[int(first_m)]
    last_name = MONTH_NAMES[int(last_m)]
    if first_y == last_y:
        if first_m == last_m:
            return f"{first_name} {first_y}"
        return f"{first_name}–{last_name} {first_y}"
    return f"{first_name} {first_y}–{last_name} {last_y}"


def build_cohort(title_base: str, months: list[str], app_buckets: dict) -> dict:
    """Build a cohort dict for the JSON output."""
    rng = format_month_range(months)
    title = f"{title_base} ({rng})" if rng else title_base
    total = sum(app_buckets.values())
    return {
        "title": title,
        "total": total,
        "buckets": dict(app_buckets),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apps", default="job_search_log/applications.csv")
    parser.add_argument("--events", default="job_search_log/pipeline_events.csv")
    parser.add_argument("--out", default="job_search_log/sankey_data.json")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    apps = read_csv_dicts(Path(args.apps))
    events = read_csv_dicts(Path(args.events))

    events_by_app: dict[str, list[dict]] = {}
    for ev in events:
        events_by_app.setdefault(ev["app_id"], []).append(ev)

    # Cohorts: all_apps, one_page, two_page
    cohorts: dict[str, dict] = {
        "all_apps": {"buckets": {}, "months": []},
        "one_page": {"buckets": {}, "months": []},
        "two_page": {"buckets": {}, "months": []},
    }

    for app in apps:
        app_id = app["app_id"]
        evs = events_by_app.get(app_id, [])
        stage, outcome = classify_application(evs)
        bucket = f"{stage}_{outcome}"

        month = app_month(app.get("date_applied", ""))
        if month:
            cohorts["all_apps"]["months"].append(month)
        cohorts["all_apps"]["buckets"][bucket] = (
            cohorts["all_apps"]["buckets"].get(bucket, 0) + 1
        )

        rf = (app.get("resume_format") or "").lower()
        if rf == "1-page":
            if month:
                cohorts["one_page"]["months"].append(month)
            cohorts["one_page"]["buckets"][bucket] = (
                cohorts["one_page"]["buckets"].get(bucket, 0) + 1
            )
        elif rf == "2-page":
            if month:
                cohorts["two_page"]["months"].append(month)
            cohorts["two_page"]["buckets"][bucket] = (
                cohorts["two_page"]["buckets"].get(bucket, 0) + 1
            )

        if args.verbose:
            print(f"{app_id}: {bucket}", file=sys.stderr)

    titles = {
        "all_apps": "Job Search Funnel — All Applications",
        "one_page": "Job Search Funnel — 1-Page Resume",
        "two_page": "Job Search Funnel — 2-Page Resume",
    }

    output = {}
    for key, c in cohorts.items():
        output[key] = build_cohort(titles[key], c["months"], c["buckets"])

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(output, f, indent=2)
        f.write("\n")

    print(
        f"Wrote {out_path} — "
        f"all={output['all_apps']['total']} "
        f"one_page={output['one_page']['total']} "
        f"two_page={output['two_page']['total']}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
