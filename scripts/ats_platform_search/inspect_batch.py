"""Inspect a review_batch_*.json file without dumping full descriptions.

The ats-platform-review agent needs to eyeball individual candidate records —
title, url, snippet, and a truncated slice of the (often huge) description_full —
when deciding a borderline score or disqualification. Doing that with an inline
`python3 -c "..."` heredoc trips a per-invocation permission prompt and is easy
to get wrong. This static module is invoked as a normal allowlisted command:

    .venv/bin/python -m scripts.ats_platform_search.inspect_batch BATCH [options]

Examples
--------
# Size a scoring loop — record count to stdout, nothing else:
    ... inspect_batch BATCH --count

# SCORING a record: pull ONE record's FULL, untruncated description:
    ... inspect_batch BATCH --index 5 --desc-chars 0

# Spot-check / triage a range with a short slice (NOT for scoring decisions):
    ... inspect_batch BATCH --start 18 --end 38

# Just titles + urls, no description at all, as JSON (triage pass):
    ... inspect_batch BATCH --no-desc --json

The output goes to stdout. With --desc-chars 0 the full description is printed;
any positive value truncates each description to that many characters.

IMPORTANT: a truncated slice (--desc-chars > 0) is for eyeballing only. A
disqualifier such as an on-site requirement, a salary floor, or a non-US
location can appear anywhere in the description — so any scoring or
disqualification decision MUST be made against the FULL text (--desc-chars 0),
never a slice.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load(batch_path: Path) -> list[dict]:
    with batch_path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise SystemExit(
            f"Expected a JSON array of records, got {type(data).__name__}"
        )
    return data


def _select(records: list[dict], args: argparse.Namespace) -> list[tuple[int, dict]]:
    """Return (original_index, record) pairs honoring --index / --start / --end."""
    if args.index is not None:
        if not (0 <= args.index < len(records)):
            raise SystemExit(
                f"--index {args.index} out of range (0..{len(records) - 1})"
            )
        return [(args.index, records[args.index])]

    start = args.start if args.start is not None else 0
    end = args.end if args.end is not None else len(records)
    start = max(start, 0)
    end = min(end, len(records))
    if start >= end:
        raise SystemExit(f"Empty selection: start={start} >= end={end}")
    return [(i, records[i]) for i in range(start, end)]


def _truncate(text: str, limit: int) -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    return text[:limit] + f"… [+{len(text) - limit} more chars]"


def _emit_json(selected: list[tuple[int, dict]], args: argparse.Namespace) -> None:
    out = []
    for idx, rec in selected:
        item = {
            "index": idx,
            "title": rec.get("title", ""),
            "url": rec.get("url", ""),
            "matched_role": rec.get("matched_role", ""),
            "source_domain": rec.get("source_domain", ""),
            "description_available": rec.get("description_available"),
        }
        if not args.no_snippet:
            item["snippet"] = rec.get("snippet", "")
        if not args.no_desc:
            item["description_full"] = _truncate(
                rec.get("description_full", ""), args.desc_chars
            )
        out.append(item)
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def _emit_text(selected: list[tuple[int, dict]], args: argparse.Namespace) -> None:
    for idx, rec in selected:
        print(f"=== [{idx}] {rec.get('title', '')} ===")
        print(f"URL: {rec.get('url', '')}")
        print(
            f"ROLE: {rec.get('matched_role', '')} | "
            f"DOMAIN: {rec.get('source_domain', '')} | "
            f"DESC_AVAILABLE: {rec.get('description_available')}"
        )
        if not args.no_snippet:
            print(f"SNIPPET: {rec.get('snippet', '')}")
        if not args.no_desc:
            print(f"DESC: {_truncate(rec.get('description_full', ''), args.desc_chars)}")
        print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="inspect_batch",
        description="Inspect review_batch_*.json records with truncated descriptions.",
    )
    parser.add_argument("batch", type=Path, help="Path to review_batch_*.json")
    sel = parser.add_argument_group("selection")
    sel.add_argument("--index", type=int, help="Single record index (0-based)")
    sel.add_argument("--start", type=int, help="Start index (inclusive, 0-based)")
    sel.add_argument("--end", type=int, help="End index (exclusive)")
    fmt = parser.add_argument_group("output")
    fmt.add_argument(
        "--count",
        action="store_true",
        help="Print only the record count (to stdout) and exit. Use to size a scoring loop.",
    )
    fmt.add_argument(
        "--desc-chars",
        type=int,
        default=800,
        help="Truncate each description to N chars (0 = full, no truncation). Default 800.",
    )
    fmt.add_argument("--no-desc", action="store_true", help="Omit description_full entirely")
    fmt.add_argument("--no-snippet", action="store_true", help="Omit the SERP snippet")
    fmt.add_argument("--json", action="store_true", help="Emit JSON instead of text blocks")
    args = parser.parse_args(argv)

    if not args.batch.exists():
        raise SystemExit(f"Batch file not found: {args.batch}")

    records = _load(args.batch)

    if args.count:
        print(len(records))
        return 0

    if not records:
        print(f"(batch is empty: {args.batch})")
        return 0

    selected = _select(records, args)
    print(f"# {args.batch.name}: {len(records)} records total, showing {len(selected)}",
          file=sys.stderr)

    if args.json:
        _emit_json(selected, args)
    else:
        _emit_text(selected, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
