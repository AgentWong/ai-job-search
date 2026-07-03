"""CSV/YAML loaders shared across analysis modules."""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

import yaml


def parse_iso_date(s: str) -> date | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def in_window(row_date: date | None, cutoff: date) -> bool:
    return row_date is not None and row_date >= cutoff


def cutoff_date(today: date, window_days: int) -> date:
    return today - timedelta(days=window_days)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def filter_by_date(rows: Iterable[dict[str, str]], date_col: str, cutoff: date) -> list[dict[str, str]]:
    return [r for r in rows if in_window(parse_iso_date(r.get(date_col, "")), cutoff)]


def safe_int(val: object) -> int:
    if val is None or val == "":
        return 0
    try:
        return int(val)
    except (TypeError, ValueError):
        try:
            return int(float(val))
        except (TypeError, ValueError):
            return 0


def load_config(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        # The file uses --- to separate documents; we want the first one (job_boards/target_roles)
        # plus the third (search_config) is irrelevant. Just load all and merge.
        merged: dict = {}
        for doc in yaml.safe_load_all(f):
            if isinstance(doc, dict):
                merged.update(doc)
        return merged
