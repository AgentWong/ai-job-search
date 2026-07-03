"""Read/write for results/application_queue.csv.

The CSV has 11 columns in this fixed order:
    company, title, url, source_track, discovered_date, quality_score,
    iac_tools, cloud_platform, remote_status, match_reasons, disqualifiers

All workflows write this header when creating the file, so we keep it
authoritative here and reuse it from every caller.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

HEADER: list[str] = [
    "company",
    "title",
    "url",
    "source_track",
    "discovered_date",
    "quality_score",
    "iac_tools",
    "cloud_platform",
    "remote_status",
    "match_reasons",
    "disqualifiers",
]


def read_rows(csv_path: Path) -> list[dict[str, str]]:
    if not csv_path.exists():
        return []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


def write_rows(csv_path: Path, rows: Iterable[dict[str, str]]) -> None:
    """Overwrite csv_path with header + rows."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in HEADER})


def append_rows(csv_path: Path, rows: Iterable[dict[str, str]]) -> None:
    """Append rows to csv_path, creating file + header if it does not exist."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HEADER)
        if not file_exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in HEADER})
