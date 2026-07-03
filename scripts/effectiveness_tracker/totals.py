"""Tracker schema definitions and rolling-total computation.

Each tracker is an append-only CSV under results/tracking/data/. Rolling
totals (runs, total-found, avg-rate, trend) are recomputed from the full
CSV rather than mutated in place — the CSV is the source of truth.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Iterable


@dataclass(frozen=True)
class TrackerSchema:
    name: str
    csv_filename: str
    columns: list[str]
    # Which column identifies the entity whose rolling totals we compute.
    # None means no rolling aggregation (used for per-(date,key,reason) breakdowns).
    group_by: str | None
    # Column holding the "found" denominator. Optional.
    found_col: str | None
    # Column holding the "qualified" numerator. Optional.
    qualified_col: str | None


SCHEMAS: dict[str, TrackerSchema] = {
    "browser_role": TrackerSchema(
        name="browser_role",
        csv_filename="browser_role_effectiveness.csv",
        columns=["date", "source", "role", "found", "qualified"],
        group_by="role",
        found_col="found",
        qualified_col="qualified",
    ),
    "ats_role": TrackerSchema(
        name="ats_role",
        csv_filename="ats_role_effectiveness.csv",
        columns=["date", "role", "found", "qualified"],
        group_by="role",
        found_col="found",
        qualified_col="qualified",
    ),
    "linkedin_api_role": TrackerSchema(
        name="linkedin_api_role",
        csv_filename="linkedin_api_role_effectiveness.csv",
        columns=["date", "role", "found", "qualified"],
        group_by="role",
        found_col="found",
        qualified_col="qualified",
    ),
    "builtin_api_role": TrackerSchema(
        name="builtin_api_role",
        csv_filename="builtin_api_role_effectiveness.csv",
        columns=["date", "role", "found", "qualified"],
        group_by="role",
        found_col="found",
        qualified_col="qualified",
    ),
    "ats_board": TrackerSchema(
        name="ats_board",
        csv_filename="ats_board_effectiveness.csv",
        columns=["date", "board", "queries", "found", "qualified"],
        group_by="board",
        found_col="found",
        qualified_col="qualified",
    ),
    "ats_api_platform": TrackerSchema(
        name="ats_api_platform",
        csv_filename="ats_api_platform_effectiveness.csv",
        columns=["date", "platform", "companies", "fetched", "qualified"],
        group_by="platform",
        found_col="fetched",
        qualified_col="qualified",
    ),
    "ats_api_company": TrackerSchema(
        name="ats_api_company",
        csv_filename="ats_api_company_effectiveness.csv",
        columns=[
            "date", "company", "platform", "fetched", "qualified",
            "top_rejection", "rejection_breakdown",
        ],
        group_by="company",
        found_col="fetched",
        qualified_col="qualified",
    ),
    # Per-(date, company, platform, reason) breakdown — one row per rejection reason.
    # Lets analyzers slice "which companies are dominated by no_remote_signal" without
    # parsing the rejection_breakdown string in ats_api_company_effectiveness.csv.
    "ats_api_company_rejection": TrackerSchema(
        name="ats_api_company_rejection",
        csv_filename="ats_api_company_rejections.csv",
        columns=["date", "company", "platform", "reason", "count"],
        group_by=None,
        found_col=None,
        qualified_col=None,
    ),
}


def tracker_names() -> list[str]:
    return list(SCHEMAS.keys())


def get_schema(name: str) -> TrackerSchema:
    if name not in SCHEMAS:
        raise SystemExit(
            f"Unknown tracker '{name}'. Valid: {', '.join(SCHEMAS)}"
        )
    return SCHEMAS[name]


def read_rows(csv_path: Path, schema: TrackerSchema) -> list[dict[str, str]]:
    if not csv_path.exists():
        return []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [{col: (row.get(col) or "") for col in schema.columns} for row in reader]


def append_rows(
    csv_path: Path, schema: TrackerSchema, rows: Iterable[dict[str, str]]
) -> int:
    rows = list(rows)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=schema.columns)
        if not file_exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({col: str(row.get(col, "")) for col in schema.columns})
    return len(rows)


def _safe_int(val: str | int | None) -> int:
    if val is None or val == "":
        return 0
    try:
        return int(val)
    except (TypeError, ValueError):
        try:
            return int(float(val))
        except (TypeError, ValueError):
            return 0


@dataclass
class RollingRow:
    group: str
    runs: int
    total_found: int
    total_qualified: int
    avg_rate_pct: float
    latest_rate_pct: float
    trend: str
    zero_runs: int


def compute_rolling(
    rows: list[dict[str, str]], schema: TrackerSchema
) -> list[RollingRow]:
    if not schema.group_by or not schema.found_col or not schema.qualified_col:
        return []

    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        key = row.get(schema.group_by, "").strip()
        if not key:
            continue
        grouped.setdefault(key, []).append(row)

    out: list[RollingRow] = []
    for group, group_rows in grouped.items():
        runs = len(group_rows)
        total_found = sum(_safe_int(r.get(schema.found_col)) for r in group_rows)
        total_qualified = sum(_safe_int(r.get(schema.qualified_col)) for r in group_rows)
        per_run_rates = []
        zero_runs = 0
        for r in group_rows:
            found = _safe_int(r.get(schema.found_col))
            qualified = _safe_int(r.get(schema.qualified_col))
            if found == 0:
                zero_runs += 1
                per_run_rates.append(0.0)
            else:
                per_run_rates.append(qualified / found * 100.0)
        avg_rate = mean(per_run_rates) if per_run_rates else 0.0
        latest_rate = per_run_rates[-1] if per_run_rates else 0.0
        out.append(
            RollingRow(
                group=group,
                runs=runs,
                total_found=total_found,
                total_qualified=total_qualified,
                avg_rate_pct=avg_rate,
                latest_rate_pct=latest_rate,
                trend=_trend_symbol(latest_rate, avg_rate, runs),
                zero_runs=zero_runs,
            )
        )
    out.sort(key=lambda r: r.group)
    return out


def _trend_symbol(latest: float, avg: float, runs: int) -> str:
    if runs <= 1:
        return "---"
    delta = latest - avg
    if delta >= 2.0:
        return ">>>"
    if delta <= -2.0:
        return "<<<"
    return "==="
