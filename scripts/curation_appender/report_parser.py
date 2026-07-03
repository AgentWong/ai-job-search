"""Extract CSV content from fenced codeblocks inside a markdown report."""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path


FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*$")


def extract_csv_blocks(report_path: Path) -> list[str]:
    """Return the raw text of every fenced codeblock in the report.

    Claude Desktop research reports wrap the CSV in triple-backtick blocks;
    we tolerate optional language tags (```csv, ```text, or just ```).
    """
    if not report_path.exists():
        return []

    text = report_path.read_text(encoding="utf-8")
    blocks: list[str] = []
    buf: list[str] = []
    in_block = False

    for line in text.splitlines():
        if FENCE_RE.match(line):
            if in_block:
                blocks.append("\n".join(buf))
                buf = []
                in_block = False
            else:
                in_block = True
            continue
        if in_block:
            buf.append(line)

    return blocks


def parse_csv_rows(block: str, expected_header_first_col: str = "Company_Name") -> list[dict[str, str]]:
    """Parse a CSV block into dicts keyed by column name.

    The reports emit the header line as the first row of the block, and use
    ", " (comma + space) as the delimiter. Python's csv.reader treats a
    leading space before a quote as data, so `", "Fake, multi"` gets split
    wrong. We normalize the delimiter to a plain comma before parsing so
    standard csv quoting rules apply to values that contain embedded commas.
    """
    normalized_lines = [_normalize_delimiter(line) for line in block.splitlines()]
    normalized = "\n".join(normalized_lines)
    reader = csv.reader(io.StringIO(normalized))
    rows = list(reader)
    if not rows:
        return []

    header = [h.strip() for h in rows[0]]
    if not header or not header[0].startswith(expected_header_first_col):
        return []

    out: list[dict[str, str]] = []
    for raw in rows[1:]:
        if not raw or all(not c.strip() for c in raw):
            continue
        # Pad/truncate to header length so csv misalignments surface as empty fields
        padded = (raw + [""] * len(header))[: len(header)]
        out.append({h: padded[i].strip() for i, h in enumerate(header)})
    return out


def _normalize_delimiter(line: str) -> str:
    """Replace ', ' delimiter with ',' outside of quoted fields.

    Walks the line char by char, tracking whether we're inside a double-quoted
    field. When we hit a comma outside quotes followed by a space, drop the
    space so csv.reader sees a standard comma delimiter.
    """
    out: list[str] = []
    in_quotes = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == '"':
            in_quotes = not in_quotes
            out.append(ch)
            i += 1
            continue
        if ch == "," and not in_quotes and i + 1 < len(line) and line[i + 1] == " ":
            out.append(",")
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def load_report(report_path: Path) -> list[dict[str, str]]:
    """Load all rows from all CSV codeblocks in the report, concatenated."""
    all_rows: list[dict[str, str]] = []
    for block in extract_csv_blocks(report_path):
        all_rows.extend(parse_csv_rows(block))
    return all_rows
