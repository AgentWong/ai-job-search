"""CLI for appending rows to effectiveness tracker CSVs."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from scripts.effectiveness_tracker import totals
from scripts.tracking_dashboard import cli as dashboard_cli

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "results" / "tracking" / "data"


def _load_rows(rows_path: Path) -> list[dict]:
    with rows_path.open(encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "rows" in data:
        return list(data["rows"])
    if isinstance(data, list):
        return data
    raise SystemExit(f"{rows_path}: JSON root must be a list or {{'rows': [...]}}.")


def _apply_defaults(row: dict, schema: totals.TrackerSchema, today: str, source: str) -> dict:
    out = {col: row.get(col, "") for col in schema.columns}
    if "date" in schema.columns and not out.get("date"):
        out["date"] = today
    if "source" in schema.columns and source and not out.get("source"):
        out["source"] = source
    return out


def cmd_append(args: argparse.Namespace) -> int:
    schema = totals.get_schema(args.tracker)
    rows_path = Path(args.rows)
    raw_rows = _load_rows(rows_path)
    today = args.date or date.today().isoformat()
    prepared = [_apply_defaults(r, schema, today, args.source) for r in raw_rows]

    csv_path = Path(args.output) if args.output else DATA_DIR / schema.csv_filename

    if args.dry_run:
        added = len(prepared)
    else:
        added = totals.append_rows(csv_path, schema, prepared)

    all_rows = totals.read_rows(csv_path, schema) if not args.dry_run else []
    rolling = totals.compute_rolling(all_rows, schema)
    group_label = schema.group_by or "n/a"
    suffix = " (dry-run, no writes)" if args.dry_run else ""
    html_suffix = ""
    if not args.dry_run and not args.no_render:
        html_path = dashboard_cli.render(args.tracker)
        html_suffix = f" | HTML: {html_path.relative_to(REPO_ROOT)}"
    print(
        f"Logged {added} rows | Rolling totals recomputed for {len(rolling)} {group_label}s | Path: {csv_path}{suffix}{html_suffix}"
    )
    if args.verbose and rolling:
        for rr in rolling:
            print(
                f"  {rr.group}: runs={rr.runs} found={rr.total_found} "
                f"qualified={rr.total_qualified} avg={rr.avg_rate_pct:.1f}% trend={rr.trend}",
                file=sys.stderr,
            )

    if args.progress_log:
        _ = Path(args.progress_log)  # reserved for Phase D; no-op for now

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    for name in totals.tracker_names():
        schema = totals.get_schema(name)
        print(f"{name} -> {DATA_DIR / schema.csv_filename} :: {', '.join(schema.columns)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scripts.effectiveness_tracker.cli",
        description="Append rows to an effectiveness-tracker CSV and recompute rolling totals.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    append = sub.add_parser("append", help="Append rows to a tracker CSV.")
    append.add_argument(
        "--tracker",
        required=True,
        choices=totals.tracker_names(),
        help="Which tracker to write to.",
    )
    append.add_argument("--rows", required=True, help="Path to JSON file of rows.")
    append.add_argument(
        "--source",
        default="",
        help="Browser source label (browser_role only), e.g. hiringcafe.",
    )
    append.add_argument("--date", default="", help="Override date column (ISO).")
    append.add_argument("--output", default="", help="Override destination CSV path.")
    append.add_argument(
        "--progress-log",
        default="",
        help="Reserved for ats-platform-search progress file. Currently ignored.",
    )
    append.add_argument("--dry-run", action="store_true", help="Skip writes.")
    append.add_argument(
        "--no-render",
        action="store_true",
        help="Skip refreshing the tracker's HTML dashboard after appending.",
    )
    append.add_argument("--verbose", action="store_true", help="Print rolling totals to stderr.")
    append.set_defaults(func=cmd_append)

    listing = sub.add_parser("list", help="Print tracker names and their CSV paths.")
    listing.set_defaults(func=cmd_list)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
