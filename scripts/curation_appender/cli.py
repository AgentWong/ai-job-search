"""Curation Appender CLI

Read the ATS Claude Desktop curation research report, deduplicate against the
existing ATS target CSV, append new companies, and print a summary.

Usage:
    .venv/bin/python -m scripts.curation_appender.cli [--dry-run] [--verbose]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .appender import AppendResult, append_rows
from .csv_reader import read_company_names
from .dedup import dedupe_rows_by_name, norm, partition_against_existing
from .platform_normalizer import normalize_rows
from .rebuild_companion import rebuild_all
from .report_parser import load_report


ROOT = Path(__file__).parent.parent.parent
ATS_REPORT = ROOT / ".ai_references" / "company_curation_ats" / "report.md"
ATS_CSV = ROOT / "config" / "company_targets_ats.csv"
EXCLUSIONS_YML = ROOT / "config" / "exclusions.yml"


def _load_excluded_names(exclusions_path: Path = EXCLUSIONS_YML) -> set[str]:
    """Return normalized company names from exclusions.yml."""
    if not exclusions_path.exists():
        return set()
    with exclusions_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    companies = (data or {}).get("excluded_companies", []) or []
    return {norm(c) for c in companies if c}


def _filter_excluded(
    rows: list[dict[str, str]],
    excluded: set[str],
) -> tuple[list[dict[str, str]], list[str]]:
    """Split rows into (kept, excluded_names)."""
    kept: list[dict[str, str]] = []
    excluded_hits: list[str] = []
    for row in rows:
        name = row.get("Company_Name", "").strip()
        if name and norm(name) in excluded:
            excluded_hits.append(name)
        else:
            kept.append(row)
    return kept, excluded_hits


def process(
    ats_report: Path = ATS_REPORT,
    ats_csv: Path = ATS_CSV,
    dry_run: bool = False,
    verbose: bool = False,
) -> AppendResult:
    result = AppendResult()

    ats_rows_raw = load_report(ats_report)

    if verbose:
        print(f"Parsed {len(ats_rows_raw)} rows from {ats_report}")

    platform_changes = normalize_rows(ats_rows_raw)
    if verbose and platform_changes:
        print(f"Normalized {len(platform_changes)} ATS_Platform value(s):")
        for change in platform_changes:
            print(f"  {change}")

    ats_rows, dropped_ats = dedupe_rows_by_name(ats_rows_raw)
    result.intra_report_duplicates_ats = dropped_ats

    excluded_names = _load_excluded_names()
    ats_rows, excl_ats = _filter_excluded(ats_rows, excluded_names)
    result.skipped_excluded = excl_ats

    existing_ats = read_company_names(ats_csv)

    ats_new, skipped_in_ats = partition_against_existing(ats_rows, existing_ats)
    result.skipped_already_in_ats = skipped_in_ats
    result.added_to_ats = [r["Company_Name"].strip() for r in ats_new]

    if dry_run:
        if verbose:
            print("[dry-run] No files modified.")
        return result

    append_rows(ats_csv, ats_new)

    # Keep the lean companion JSON in sync with the CSV so research agents in
    # Claude Desktop can cross-reference without loading the full CSV.
    rebuild_all(verbose=verbose)

    return result


def print_summary(result: AppendResult) -> None:
    def fmt(names: list[str]) -> str:
        if not names:
            return "(none)"
        return ", ".join(names)

    print("## Curation Append Summary")
    print()
    print(f"Added to company_targets_ats.csv ({len(result.added_to_ats)}): {fmt(result.added_to_ats)}")
    print()
    print(f"Skipped (already in ATS CSV) ({len(result.skipped_already_in_ats)}): {fmt(result.skipped_already_in_ats)}")
    print(f"Skipped (in exclusions.yml) ({len(result.skipped_excluded)}): {fmt(result.skipped_excluded)}")
    print(f"Intra-report duplicates dropped ({len(result.intra_report_duplicates_ats)}): {fmt(result.intra_report_duplicates_ats)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Append ATS curation report results to target CSV")
    parser.add_argument("--dry-run", action="store_true", help="Compute results without writing")
    parser.add_argument("--verbose", action="store_true", help="Print progress details")
    parser.add_argument("--ats-report", type=Path, default=ATS_REPORT)
    parser.add_argument("--ats-csv", type=Path, default=ATS_CSV)
    args = parser.parse_args(argv)

    result = process(
        ats_report=args.ats_report,
        ats_csv=args.ats_csv,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )
    print_summary(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
