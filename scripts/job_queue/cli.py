"""CLI for appending qualified positions to results/application_queue.csv."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from scripts.ats_scraper.cooldown import (
    COOLDOWN_DAYS,
    normalize_company,
    normalize_role,
)
from scripts.job_queue import dedup, queue_io

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUEUE_PATH = REPO_ROOT / "results" / "application_queue.csv"
APPLICATIONS_CSV = REPO_ROOT / "job_search_log" / "applications.csv"


def _load_applied_entries() -> set[tuple[str, str]]:
    """Return normalized (company, role) pairs from job_search_log/applications.csv.

    Uses cooldown normalization (corp suffixes stripped, seniority modifiers
    stripped, SRE collapsed) so a logged "Sr DevOps Engineer" application
    still matches a current "DevOps Engineer" rediscovery.
    """
    if not APPLICATIONS_CSV.exists():
        return set()
    entries: set[tuple[str, str]] = set()
    with open(APPLICATIONS_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            company = normalize_company((row.get("company") or "").strip())
            role = normalize_role((row.get("role") or "").strip())
            if company and role:
                entries.add((company, role))
    return entries


def _is_already_applied(row: dict, applied: set[tuple[str, str]]) -> bool:
    return (
        normalize_company(row.get("company", "")),
        normalize_role(row.get("title", "")),
    ) in applied


def _build_company_recent_index(today: date) -> dict[str, list[dict]]:
    """Map normalized_company -> list of recent {role, date_applied} dicts.

    Roles are kept in their raw form so an LLM caller can fuzzy-judge them.
    """
    if not APPLICATIONS_CSV.exists():
        return {}
    cutoff = today - timedelta(days=COOLDOWN_DAYS)
    index: dict[str, list[dict]] = defaultdict(list)
    with APPLICATIONS_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            company_raw = (row.get("company") or "").strip()
            role_raw = (row.get("role") or "").strip()
            date_raw = (row.get("date_applied") or "").strip()
            if not company_raw or not role_raw:
                continue
            try:
                applied = datetime.strptime(date_raw, "%Y-%m-%d").date()
            except ValueError:
                continue
            if applied < cutoff:
                continue
            company_norm = normalize_company(company_raw)
            if not company_norm:
                continue
            index[company_norm].append({"role": role_raw, "date_applied": date_raw})
    return index


def _load_positions(positions_path: Path) -> list[dict]:
    with positions_path.open(encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        if "positions" in data:
            return list(data["positions"])
        if "qualified_positions" in data:
            return list(data["qualified_positions"])
        raise SystemExit(
            f"{positions_path}: JSON object must contain 'positions' or 'qualified_positions' list"
        )
    if isinstance(data, list):
        return data
    raise SystemExit(f"{positions_path}: JSON root must be a list or object")


def _apply_defaults(row: dict, source_track: str, today: str) -> dict:
    out = dict(row)
    if source_track and not out.get("source_track"):
        out["source_track"] = source_track
    if not out.get("discovered_date"):
        out["discovered_date"] = today
    return out


def _append_csv(
    queue_path: Path,
    positions: list[dict],
    source_track: str,
    today: str,
    dry_run: bool,
    verbose: bool,
) -> tuple[int, int, int]:
    existing = queue_io.read_rows(queue_path)
    keys = dedup.existing_keys(existing)
    applied = _load_applied_entries()
    prepared = [_apply_defaults(p, source_track, today) for p in positions]

    not_applied: list[dict] = []
    already_applied: list[dict] = []
    for row in prepared:
        if _is_already_applied(row, applied):
            already_applied.append(row)
        else:
            not_applied.append(row)

    new_rows, duplicates = dedup.partition(not_applied, keys)
    if verbose and already_applied:
        for row in already_applied:
            print(
                f"  already applied: {row.get('company', '')} | {row.get('title', '')}",
                file=sys.stderr,
            )
    if verbose and duplicates:
        for dupe in duplicates:
            print(
                f"  duplicate: {dupe.get('company', '')} | {dupe.get('title', '')}",
                file=sys.stderr,
            )
    if not dry_run and new_rows:
        queue_io.append_rows(queue_path, new_rows)
    return len(new_rows), len(duplicates), len(already_applied)


def cmd_fuzzy_check(args: argparse.Namespace) -> int:
    """Emit cooldown classifications for incoming positions.

    Output payload has two lists:
      - `exact_matches`: (company, role) already normalizes to an entry in
        applications.csv. Auto-skip with no LLM call needed.
      - `fuzzy_candidates`: company is in applications.csv but role doesn't
        exact-normalize-match. Each entry carries the company's recent
        applications so an LLM caller can judge same-role-or-not.

    Positions with no company match in the applied log are omitted entirely.
    Intended to be called BEFORE expensive Phase 2 fetching in browser
    workflows so the orchestrator can drop known-cooldown candidates before
    spending fetch + scoring tokens on them.
    """
    positions_path = Path(args.positions)
    positions = _load_positions(positions_path)
    today = date.fromisoformat(args.date) if args.date else date.today()

    company_index = _build_company_recent_index(today)
    applied = _load_applied_entries()

    exact_matches: list[dict] = []
    fuzzy_candidates: list[dict] = []
    for pos in positions:
        company_raw = (pos.get("company") or "").strip()
        title_raw = (pos.get("title") or "").strip()
        company_norm = normalize_company(company_raw)
        if not company_norm or company_norm not in company_index:
            continue
        position_view = {
            "company": company_raw,
            "title": title_raw,
            "url": pos.get("url", ""),
        }
        recent = sorted(
            company_index[company_norm],
            key=lambda r: r["date_applied"],
            reverse=True,
        )
        if _is_already_applied(pos, applied):
            # Find which logged role triggered the match for traceability.
            role_norm = normalize_role(title_raw)
            matched_prior = next(
                (r for r in recent if normalize_role(r["role"]) == role_norm),
                None,
            )
            exact_matches.append(
                {
                    "position": position_view,
                    "matched_prior_role": matched_prior["role"] if matched_prior else "",
                    "matched_prior_date": matched_prior["date_applied"] if matched_prior else "",
                }
            )
        else:
            fuzzy_candidates.append(
                {
                    "position": position_view,
                    "company_recent_applications": recent,
                }
            )

    payload = {
        "exact_matches": exact_matches,
        "fuzzy_candidates": fuzzy_candidates,
    }
    if args.output:
        out_path = Path(args.output)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(
            f"Exact matches: {len(exact_matches)} | "
            f"Fuzzy candidates: {len(fuzzy_candidates)} | "
            f"Path: {out_path}"
        )
    else:
        print(json.dumps(payload, indent=2))
    return 0


def cmd_append(args: argparse.Namespace) -> int:
    positions_path = Path(args.positions)
    positions = _load_positions(positions_path)
    today = args.date or date.today().isoformat()

    queue_path = Path(args.output) if args.output else DEFAULT_QUEUE_PATH
    source_track = args.source_track or ""
    added, dupes, already_applied = _append_csv(
        queue_path, positions, source_track, today, args.dry_run, args.verbose
    )
    path_label = queue_path

    suffix = " (dry-run, no writes)" if args.dry_run else ""
    print(
        f"Added: {added} | Already applied skipped: {already_applied} | "
        f"Duplicates skipped: {dupes} | Path: {path_label}{suffix}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scripts.job_queue.cli",
        description="Append qualified positions to the application queue.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    append = sub.add_parser("append", help="Append positions to the application queue CSV.")
    append.add_argument("--positions", required=True, help="Path to JSON file of positions.")
    append.add_argument(
        "--source-track",
        default="",
        help='Source label, e.g. "linkedin(verified)". Applied to rows missing source_track.',
    )
    append.add_argument(
        "--target",
        choices=["queue"],
        default="queue",
        help="Destination file (default: application_queue.csv).",
    )
    append.add_argument(
        "--output",
        default="",
        help="Override destination path (useful for tests).",
    )
    append.add_argument("--date", default="", help="Override discovered_date / last_run (ISO).")
    append.add_argument("--dry-run", action="store_true", help="Do not write; print summary only.")
    append.add_argument("--verbose", action="store_true", help="Print duplicate rows to stderr.")
    append.set_defaults(func=cmd_append)

    fuzzy = sub.add_parser(
        "fuzzy-check",
        help=(
            "Find positions whose company has recent applications but whose "
            "role doesn't exact-match — for LLM same-role judgment."
        ),
    )
    fuzzy.add_argument(
        "--positions",
        required=True,
        help="Path to JSON file of positions (same shape as `append`).",
    )
    fuzzy.add_argument(
        "--output",
        default="",
        help="Write JSON candidates list here. If omitted, prints to stdout.",
    )
    fuzzy.add_argument(
        "--date",
        default="",
        help="Anchor date for the 60-day cooldown window (ISO; defaults to today).",
    )
    fuzzy.set_defaults(func=cmd_fuzzy_check)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
