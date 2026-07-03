"""Case-insensitive (company, title) dedup for the application queue."""

from __future__ import annotations

from typing import Iterable

from scripts.curation_appender.dedup import norm


def row_key(row: dict[str, str]) -> str:
    """Build the case-insensitive `company|title` dedup key."""
    company = norm(row.get("company", ""))
    title = norm(row.get("title", ""))
    return f"{company}|{title}"


def existing_keys(rows: Iterable[dict[str, str]]) -> set[str]:
    keys: set[str] = set()
    for row in rows:
        key = row_key(row)
        if key.strip("|"):
            keys.add(key)
    return keys


def partition(
    incoming: Iterable[dict[str, str]], existing: set[str]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Split incoming rows into (new, duplicates).

    `existing` is mutated: the key of each newly accepted row is added so
    incoming duplicates within a single call are also filtered.
    """
    new: list[dict[str, str]] = []
    dupes: list[dict[str, str]] = []
    for row in incoming:
        key = row_key(row)
        if not key.strip("|"):
            continue
        if key in existing:
            dupes.append(row)
            continue
        existing.add(key)
        new.append(row)
    return new, dupes
