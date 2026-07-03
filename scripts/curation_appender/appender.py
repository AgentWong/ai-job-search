"""Append new rows to the ATS target CSV."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .csv_reader import format_row, read_rows


@dataclass
class AppendResult:
    added_to_ats: list[str] = field(default_factory=list)
    skipped_already_in_ats: list[str] = field(default_factory=list)
    skipped_excluded: list[str] = field(default_factory=list)
    intra_report_duplicates_ats: list[str] = field(default_factory=list)


def append_rows(csv_path: Path, new_rows: list[dict[str, str]]) -> None:
    """Append rows to the CSV, preserving the existing header column order.

    Rows are serialized using the ', ' delimiter convention of these files.
    """
    if not new_rows:
        return

    header, _ = read_rows(csv_path)
    if not header:
        raise RuntimeError(f"Cannot append to {csv_path}: missing or empty header")

    with csv_path.open("rb") as fh:
        fh.seek(0, 2)
        size = fh.tell()
        ends_with_newline = True
        if size > 0:
            fh.seek(-1, 2)
            ends_with_newline = fh.read(1) == b"\n"

    with csv_path.open("a", encoding="utf-8", newline="") as fh:
        if not ends_with_newline:
            fh.write("\n")
        for row in new_rows:
            fh.write(format_row(header, row) + "\n")
