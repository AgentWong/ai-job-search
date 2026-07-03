"""
Data Analysis CLI

Aggregates effectiveness tracking CSVs + applications log into a compact
JSON report the LLM can read and reason about.

Usage:
    .venv/bin/python -m scripts.data_analysis.cli [OPTIONS]

Options:
    --days N             Analysis window for roles/boards/applications (default: 30)
    --output PATH        JSON output path (default: results/tracking/data_analysis_<date>.json)
    --pretty             Pretty-print JSON output
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from . import applications_analysis, board_analysis, role_analysis
from .loaders import load_config

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKING_DATA_DIR = REPO_ROOT / "results" / "tracking" / "data"
APPLICATIONS_CSV = REPO_ROOT / "job_search_log" / "applications.csv"
PIPELINE_EVENTS_CSV = REPO_ROOT / "job_search_log" / "pipeline_events.csv"
CONFIG_YML = REPO_ROOT / "config" / "config.yml"
DEFAULT_OUT_DIR = REPO_ROOT / "results" / "tracking"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="scripts.data_analysis.cli",
        description="Aggregate tracking CSVs + applications log into a JSON analysis report.",
    )
    p.add_argument("--days", type=int, default=30,
                   help="Analysis window for roles/boards/applications (default: 30)")
    p.add_argument("--output", default="",
                   help="JSON output path (default: results/tracking/data_analysis_<date>.json)")
    p.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    today = date.today()

    inclusions = load_config(CONFIG_YML)

    report = {
        "generated_at": today.isoformat(),
        "windows": {"role_board_days": args.days},
        "roles": role_analysis.analyze(
            today=today,
            window_days=args.days,
            tracking_dir=TRACKING_DATA_DIR,
            applications_csv=APPLICATIONS_CSV,
            inclusions=inclusions,
        ),
        "boards": board_analysis.analyze(
            today=today,
            window_days=args.days,
            tracking_dir=TRACKING_DATA_DIR,
            inclusions=inclusions,
        ),
        "applications": applications_analysis.analyze(
            today=today,
            window_days=args.days,
            applications_csv=APPLICATIONS_CSV,
            pipeline_events_csv=PIPELINE_EVENTS_CSV,
        ),
    }

    out_path = Path(args.output) if args.output else DEFAULT_OUT_DIR / f"data_analysis_{today.isoformat()}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        if args.pretty:
            json.dump(report, f, indent=2)
        else:
            json.dump(report, f)

    summary = _summary_line(report)
    print(f"Wrote: {out_path.relative_to(REPO_ROOT)}", file=sys.stdout)
    print(summary, file=sys.stdout)
    return 0


def _summary_line(report: dict) -> str:
    r = report["roles"]
    b = report["boards"]
    a = report["applications"]

    role_classes: dict[str, int] = {}
    for row in r["roles"]:
        role_classes[row["classification"]] = role_classes.get(row["classification"], 0) + 1
    board_classes: dict[str, int] = {}
    for row in b["firecrawl_boards"]:
        board_classes[row["recommendation"]] = board_classes.get(row["recommendation"], 0) + 1

    parts = [
        f"Window: {report['windows']['role_board_days']}d",
        f"Roles: {len(r['roles'])} ({_fmt_classes(role_classes)})",
        f"Boards: {len(b['firecrawl_boards'])} ({_fmt_classes(board_classes)}), "
        f"silent_in_config: {len(b['silent_boards_in_config'])}",
        f"Applications: {a['total_applications_in_window']}",
    ]
    return " | ".join(parts)


def _fmt_classes(counts: dict[str, int]) -> str:
    if not counts:
        return "n/a"
    return ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))


if __name__ == "__main__":
    raise SystemExit(main())
