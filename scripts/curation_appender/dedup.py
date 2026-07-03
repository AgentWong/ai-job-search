"""Case-insensitive deduplication helpers for company-name matching."""

from __future__ import annotations


def norm(name: str) -> str:
    """Normalize a company name for comparison — lowercase + collapsed whitespace."""
    return " ".join(name.lower().split())


def dedupe_rows_by_name(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[str]]:
    """Drop duplicate entries within a single report.

    Returns (unique_rows, duplicates_dropped). First occurrence wins.
    """
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    dropped: list[str] = []
    for row in rows:
        name = row.get("Company_Name", "").strip()
        if not name:
            continue
        key = norm(name)
        if key in seen:
            dropped.append(name)
            continue
        seen.add(key)
        unique.append(row)
    return unique, dropped


def partition_against_existing(
    rows: list[dict[str, str]],
    existing_names: set[str],
) -> tuple[list[dict[str, str]], list[str]]:
    """Split rows into (new, already_existing) based on normalized-name membership.

    existing_names should already be lowercased via csv_reader.read_company_names().
    """
    new: list[dict[str, str]] = []
    already: list[str] = []
    for row in rows:
        name = row.get("Company_Name", "").strip()
        if not name:
            continue
        key = norm(name)
        if key in existing_names:
            already.append(name)
        else:
            new.append(row)
    return new, already
