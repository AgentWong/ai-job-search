"""Render a tracker CSV into a sortable HTML dashboard."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from scripts.effectiveness_tracker import totals

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = Path(__file__).resolve().parent / "template.html"
DATA_DIR = REPO_ROOT / "results" / "tracking" / "data"
OUT_DIR = REPO_ROOT / "results" / "tracking"


_TITLES = {
    "browser_role": "Browser Workflows – Role Effectiveness",
    "ats_role": "ATS Platform Search – Role Effectiveness",
    "ats_board": "ATS Platform Search – Board Effectiveness",
    "ats_api_platform": "ATS API Scraper – Platform Effectiveness",
    "ats_api_company": "ATS API Scraper – Company Effectiveness",
    "linkedin_api_role": "LinkedIn API Scraper – Role Effectiveness",
}


def _rolling_rows_to_dicts(rolling: list[totals.RollingRow], schema: totals.TrackerSchema) -> tuple[list[str], list[dict[str, str]], list[str]]:
    group_label = schema.group_by or "group"
    extra_found_label = f"total_{schema.found_col}" if schema.found_col else ""
    cols = [group_label, "runs", extra_found_label, "total_qualified", "avg_rate_pct", "zero_runs", "trend"]
    numeric = ["runs", extra_found_label, "total_qualified", "avg_rate_pct", "zero_runs"]
    out = []
    for r in rolling:
        out.append(
            {
                group_label: r.group,
                "runs": r.runs,
                extra_found_label: r.total_found,
                "total_qualified": r.total_qualified,
                "avg_rate_pct": f"{r.avg_rate_pct:.2f}",
                "zero_runs": r.zero_runs,
                "trend": r.trend,
            }
        )
    return cols, out, numeric


def _log_rows_to_dicts(rows: list[dict[str, str]], schema: totals.TrackerSchema) -> tuple[list[str], list[dict[str, str]], list[str]]:
    numeric = [c for c in schema.columns if c in {"found", "qualified", "queries", "fetched", "companies"}]
    return list(schema.columns), rows, numeric


def render(tracker: str, out_path: Path | None = None) -> Path:
    schema = totals.get_schema(tracker)
    csv_path = DATA_DIR / schema.csv_filename
    rows = totals.read_rows(csv_path, schema)
    rolling = totals.compute_rolling(rows, schema)

    rolling_cols, rolling_rows, rolling_numeric = _rolling_rows_to_dicts(rolling, schema)
    log_cols, log_rows, log_numeric = _log_rows_to_dicts(rows, schema)

    payload = {
        "rolling_columns": rolling_cols,
        "rolling_rows": rolling_rows,
        "rolling_numeric": rolling_numeric,
        "log_columns": log_cols,
        "log_rows": log_rows,
        "log_numeric": log_numeric,
    }

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = (
        template
        .replace("%%TITLE%%", _TITLES.get(tracker, tracker))
        .replace("%%CSV_PATH%%", str(csv_path.relative_to(REPO_ROOT)))
        .replace("%%GENERATED_AT%%", datetime.now().strftime("%Y-%m-%d %H:%M"))
        .replace("%%DATA_JSON%%", json.dumps(payload))
    )

    target = out_path or OUT_DIR / f"{tracker}_effectiveness.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    return target


def cmd_render(args: argparse.Namespace) -> int:
    if args.tracker == "all":
        for name in totals.tracker_names():
            out = render(name)
            print(f"Rendered {name} -> {out.relative_to(REPO_ROOT)}")
    else:
        out_path = Path(args.out) if args.out else None
        out = render(args.tracker, out_path)
        print(f"Rendered {args.tracker} -> {out.relative_to(REPO_ROOT)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scripts.tracking_dashboard.cli",
        description="Render tracker CSVs into sortable HTML dashboards.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    render_cmd = sub.add_parser("render", help="Render HTML for one tracker or 'all'.")
    render_cmd.add_argument(
        "--tracker",
        required=True,
        choices=[*totals.tracker_names(), "all"],
        help="Tracker name, or 'all' for every tracker.",
    )
    render_cmd.add_argument("--out", default="", help="Override output path.")
    render_cmd.set_defaults(func=cmd_render)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
