#!/usr/bin/env python3
"""Chunk a month's manifest into smaller pieces for sequential subagent dispatch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BY_MONTH_DIR = REPO_ROOT / "scripts" / "match_rescore" / "by_month"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("month", help="e.g. 2026-04")
    parser.add_argument("--chunks", type=int, default=2)
    args = parser.parse_args()

    src = BY_MONTH_DIR / f"{args.month}.json"
    entries = json.loads(src.read_text())
    n = len(entries)
    size = (n + args.chunks - 1) // args.chunks

    for i in range(args.chunks):
        chunk = entries[i * size : (i + 1) * size]
        if not chunk:
            continue
        out = BY_MONTH_DIR / f"{args.month}-part{i+1}.json"
        out.write_text(json.dumps(chunk, indent=2))
        print(f"part {i+1}: {len(chunk)} apps -> {out.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
