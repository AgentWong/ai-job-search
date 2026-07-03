"""Migrate markdown execution-log tables to CSV.

Each source markdown file contains one or more markdown tables under
H2/H3 section headings. We extract only the EXECUTION LOG tables (not
the rolling-totals tables, which are derived). The effectiveness_tracker
recomputes totals on every append, so the legacy totals tables are discarded.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

from scripts.effectiveness_tracker import totals as tracker_totals

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACKING_DIR = REPO_ROOT / "results" / "tracking"
DATA_DIR = TRACKING_DIR / "data"


_HEADING_RE = re.compile(r"^(#{2,3})\s+(.+?)\s*$")
_TABLE_ROW_RE = re.compile(r"^\|(.+)\|\s*$")


def _parse_markdown_tables(text: str) -> list[tuple[str, list[str], list[list[str]]]]:
    """Return list of (section_heading, header_cells, rows) triples.

    Only the first table under each heading is captured. Alignment rows
    (|---|---|) are skipped.
    """
    sections: list[tuple[str, list[str], list[list[str]]]] = []
    current_heading = ""
    in_table = False
    header: list[str] = []
    rows: list[list[str]] = []

    def flush():
        nonlocal in_table, header, rows
        if in_table and header:
            sections.append((current_heading, header, rows))
        in_table = False
        header = []
        rows = []

    for line in text.splitlines():
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            flush()
            current_heading = heading_match.group(2).strip()
            continue

        row_match = _TABLE_ROW_RE.match(line)
        if row_match:
            cells = [c.strip() for c in row_match.group(1).split("|")]
            if all(set(c) <= {"-", ":"} for c in cells if c):
                continue  # alignment row
            if not in_table:
                header = cells
                in_table = True
            else:
                rows.append(cells)
        else:
            if in_table and line.strip() == "":
                # blank line ends a table but we keep current_heading
                flush()
            elif in_table:
                flush()

    flush()
    return sections


def _find_section(
    sections: list[tuple[str, list[str], list[list[str]]]], target_heading: str
) -> tuple[list[str], list[list[str]]] | None:
    for heading, header, rows in sections:
        if heading.lower() == target_heading.lower():
            return header, rows
    return None


def _slugify_header(cells: list[str]) -> list[str]:
    return [c.lower().replace(" ", "_") for c in cells]


def _write_csv(csv_path: Path, columns: list[str], rows: list[dict[str, str]]) -> int:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in columns})
    return len(rows)


def _migrate_simple_execlog(
    md_path: Path,
    tracker: str,
    heading: str,
    column_map: dict[str, str],
) -> int:
    """Migrate a single execution-log table under `heading` into the tracker CSV.

    column_map maps the CSV column name -> the markdown cell header name.
    """
    schema = tracker_totals.get_schema(tracker)
    text = md_path.read_text(encoding="utf-8")
    sections = _parse_markdown_tables(text)
    found = _find_section(sections, heading)
    if not found:
        raise SystemExit(f"{md_path}: could not find table under heading '{heading}'")
    header_cells, rows = found
    slug_header = _slugify_header(header_cells)

    out_rows: list[dict[str, str]] = []
    for raw in rows:
        row_dict = dict(zip(slug_header, [c.strip() for c in raw]))
        csv_row = {}
        for csv_col, md_col in column_map.items():
            csv_row[csv_col] = row_dict.get(md_col, "")
        out_rows.append(csv_row)

    csv_path = DATA_DIR / schema.csv_filename
    return _write_csv(csv_path, schema.columns, out_rows)


def migrate_browser_role(md_path: Path) -> int:
    return _migrate_simple_execlog(
        md_path=md_path,
        tracker="browser_role",
        heading="Execution Log",
        column_map={
            "date": "date",
            "source": "source",
            "role": "role",
            "found": "found",
            "qualified": "qualified",
        },
    )


def migrate_ats_role_and_board(md_path: Path) -> tuple[int, int]:
    # ats_role.md has BOTH a role execution log AND a board execution log
    role_n = _migrate_simple_execlog(
        md_path=md_path,
        tracker="ats_role",
        heading="Execution Log",
        column_map={
            "date": "date",
            "role": "role",
            "found": "found",
            "qualified": "qualified",
        },
    )
    board_n = _migrate_simple_execlog(
        md_path=md_path,
        tracker="ats_board",
        heading="Board Execution Log",
        column_map={
            "date": "date",
            "board": "board",
            "queries": "queries",
            "found": "found",
            "qualified": "qualified",
        },
    )
    return role_n, board_n


def migrate_ats_api(md_path: Path) -> tuple[int, int]:
    # ats_api.md has Platform Execution Log + Company Execution Log
    platform_n = _migrate_simple_execlog(
        md_path=md_path,
        tracker="ats_api_platform",
        heading="Platform Execution Log",
        column_map={
            "date": "date",
            "platform": "platform",
            "companies": "companies",
            "fetched": "fetched",
            "qualified": "qualified",
        },
    )
    company_n = _migrate_simple_execlog(
        md_path=md_path,
        tracker="ats_api_company",
        heading="Company Execution Log",
        column_map={
            "date": "date",
            "company": "company",
            "platform": "platform",
            "fetched": "fetched",
            "qualified": "qualified",
            "top_rejection": "top_rejection",
        },
    )
    return platform_n, company_n


def cmd_run(args: argparse.Namespace) -> int:
    md_root = Path(args.md_dir) if args.md_dir else TRACKING_DIR
    plan = [
        ("browser_role", md_root / "browser_role_effectiveness.md"),
        ("ats_role_and_board", md_root / "ats_role_effectiveness.md"),
        ("ats_api", md_root / "ats_api_effectiveness.md"),
    ]
    results: list[str] = []
    for job, path in plan:
        if not path.exists():
            results.append(f"{job}: SKIPPED (missing {path})")
            continue
        if job == "browser_role":
            n = migrate_browser_role(path)
            results.append(f"{job}: {n} rows -> {DATA_DIR / 'browser_role_effectiveness.csv'}")
        elif job == "ats_role_and_board":
            role_n, board_n = migrate_ats_role_and_board(path)
            results.append(f"ats_role: {role_n} rows")
            results.append(f"ats_board: {board_n} rows")
        elif job == "ats_api":
            plat_n, comp_n = migrate_ats_api(path)
            results.append(f"ats_api_platform: {plat_n} rows")
            results.append(f"ats_api_company: {comp_n} rows")

    for line in results:
        print(line)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scripts.tracking_migrate.cli",
        description="One-time migration of tracking markdown tables into CSV.",
    )
    parser.add_argument(
        "--md-dir",
        default="",
        help="Directory holding *.md tracker files (default: results/tracking/).",
    )
    parser.set_defaults(func=cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
