#!/usr/bin/env python3
"""Split the rescore manifest into per-month JSON files for subagent dispatch."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "scripts" / "match_rescore" / "manifest.json"
OUT_DIR = REPO_ROOT / "scripts" / "match_rescore" / "by_month"


def main() -> None:
    data = json.loads(MANIFEST.read_text())
    by_month: dict[str, list[dict]] = defaultdict(list)
    for entry in data["manifest"]:
        if entry.get("posting") and entry.get("resume"):
            by_month[entry["month"]].append(entry)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for month, entries in sorted(by_month.items()):
        out = OUT_DIR / f"{month}.json"
        out.write_text(json.dumps(entries, indent=2))
        print(f"{month}: {len(entries)} apps -> {out.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
