"""Lightweight readers for the existing target CSVs.

We read the full rows (needed for the ATS-priority move case) but keep the
API narrow: callers only ask for what they need so most call sites never
hold the full dataset.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

from .report_parser import _normalize_delimiter


def _open_normalized(csv_path: Path) -> io.StringIO:
    """Read a CSV file and return a StringIO with ', ' delimiter normalized to ','."""
    text = csv_path.read_text(encoding="utf-8")
    normalized = "\n".join(_normalize_delimiter(line) for line in text.splitlines())
    return io.StringIO(normalized)


def read_header(csv_path: Path) -> list[str]:
    """Return the header row stripped of surrounding whitespace."""
    if not csv_path.exists():
        return []
    reader = csv.reader(_open_normalized(csv_path))
    try:
        header = next(reader)
    except StopIteration:
        return []
    return [h.strip() for h in header]


def read_company_names(csv_path: Path) -> set[str]:
    """Return the set of Company_Name values, lowercased for case-insensitive comparison."""
    if not csv_path.exists():
        return set()

    names: set[str] = set()
    reader = csv.reader(_open_normalized(csv_path))
    header = next(reader, None)
    if not header:
        return names
    stripped = [h.strip() for h in header]
    try:
        name_idx = stripped.index("Company_Name")
    except ValueError:
        return names
    for row in reader:
        if not row or len(row) <= name_idx:
            continue
        val = row[name_idx].strip()
        if val:
            names.add(val.lower())
    return names


def read_rows(csv_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Return (header, rows) — rows are dicts keyed by header column."""
    if not csv_path.exists():
        return [], []

    reader = csv.reader(_open_normalized(csv_path))
    header_raw = next(reader, None)
    if not header_raw:
        return [], []
    header = [h.strip() for h in header_raw]
    rows = []
    for raw in reader:
        if not raw or all(not c.strip() for c in raw):
            continue
        padded = (raw + [""] * len(header))[: len(header)]
        rows.append({h: padded[i].strip() for i, h in enumerate(header)})
    return header, rows


def format_row(header: list[str], row: dict[str, str]) -> str:
    """Render a row using ', ' delimiter to match the existing file convention."""
    values = [row.get(col, "") for col in header]
    # csv.writer to handle embedded commas/quotes, then post-process to add space after delimiter
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="")
    writer.writerow(values)
    line = buf.getvalue()
    # Replace the csv module's "," delimiter with ", " only outside of quoted fields.
    return _inject_space_after_commas(line)


def _inject_space_after_commas(line: str) -> str:
    """Insert a space after each comma that's not inside a quoted field."""
    out: list[str] = []
    in_quotes = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == '"':
            in_quotes = not in_quotes
            out.append(ch)
        elif ch == "," and not in_quotes:
            out.append(", ")
        else:
            out.append(ch)
        i += 1
    return "".join(out)
