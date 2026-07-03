"""CLI for persisting LLM-review per-position disqualifications.

LLM review agents (ats-api-llm-review, builtin-llm-review, linkedin-llm-review,
ats-platform-review) call this after they finish reviewing a batch, passing the
`disqualified` array from their JSON output. Each disqualified position is
appended as one row to results/tracking/data/llm_rejections.csv:

    date,source_agent,company,title,url,category,reason

`category` is the scoring-framework category the agent cited (e.g. "Category 8"),
parsed from the front of the disqualification_reason when present, so the rollup
can aggregate by category without re-parsing free text. `reason` keeps the full
cited reason for drill-down.

Usage (append mode — the agents' path):

    .venv/bin/python -m scripts.llm_rejections.cli append \
        --source-agent ats-api-llm-review \
        --json '<the disqualified array as JSON>'

  or read the JSON from a file / stdin:

    .venv/bin/python -m scripts.llm_rejections.cli append \
        --source-agent linkedin-llm-review --json-file /tmp/dq.json
    cat dq.json | .venv/bin/python -m scripts.llm_rejections.cli append \
        --source-agent builtin-llm-review --json -

The `disqualified` array elements are expected to carry at least
`disqualification_reason`; `company`, `title`/`role`, and `url` are used when
present and default to "" otherwise so a thin record still logs.

Usage (rollup mode — on-demand audit):

    .venv/bin/python -m scripts.llm_rejections.cli rollup [--since YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REJECTIONS_CSV = REPO_ROOT / "results" / "tracking" / "data" / "llm_rejections.csv"
FIELDNAMES = ["date", "source_agent", "company", "title", "url", "category", "reason"]

# Matches a leading "Category N" (with optional trailing " — ..." em-dash clause)
# at the start of a cited disqualification_reason. The scoring framework requires
# agents to cite this prefix, so it is the reliable aggregation key.
_CATEGORY_RE = re.compile(r"^\s*(Category\s+\d+)\b", re.IGNORECASE)


def _parse_category(reason: str) -> str:
    """Extract the cited 'Category N' prefix from a reason string.

    Returns "Uncited" when the reason does not lead with a Category citation
    (e.g. the cooldown / score-threshold reasons, which are legitimate but not
    framework categories). Keeping these visible in the rollup is the point:
    a spike in "Uncited" is itself a signal worth seeing.
    """
    m = _CATEGORY_RE.match(reason or "")
    return m.group(1).title() if m else "Uncited"


def _coerce_rows(items: list, source_agent: str, today: str) -> list[dict]:
    rows: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        reason = str(item.get("disqualification_reason", "")).strip()
        rows.append(
            {
                "date": today,
                "source_agent": source_agent,
                "company": str(item.get("company", "")).strip(),
                # agents use "title" (ATS) or "role" (browser) — accept either
                "title": str(item.get("title", item.get("role", ""))).strip(),
                "url": str(item.get("url", "")).strip(),
                "category": _parse_category(reason),
                "reason": reason,
            }
        )
    return rows


def _load_json(args: argparse.Namespace):
    if args.json_file:
        text = Path(args.json_file).read_text(encoding="utf-8")
    elif args.json == "-":
        text = sys.stdin.read()
    elif args.json is not None:
        text = args.json
    else:
        raise SystemExit("error: provide --json or --json-file")
    data = json.loads(text)
    # Accept either the bare disqualified array, or a full agent payload that
    # contains a "disqualified" key.
    if isinstance(data, dict):
        data = data.get("disqualified", [])
    if not isinstance(data, list):
        raise SystemExit("error: expected a JSON array of disqualified positions")
    return data


def cmd_append(args: argparse.Namespace) -> int:
    items = _load_json(args)
    today = args.date or date.today().isoformat()
    rows = _coerce_rows(items, args.source_agent, today)
    if not rows:
        print("llm_rejections: nothing to append (0 disqualified positions)")
        return 0

    REJECTIONS_CSV.parent.mkdir(parents=True, exist_ok=True)
    write_header = not REJECTIONS_CSV.exists() or REJECTIONS_CSV.stat().st_size == 0
    with open(REJECTIONS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)

    by_cat = Counter(r["category"] for r in rows)
    summary = ", ".join(f"{cat}: {n}" for cat, n in sorted(by_cat.items()))
    print(
        f"llm_rejections: appended {len(rows)} row(s) from {args.source_agent} "
        f"to {REJECTIONS_CSV.relative_to(REPO_ROOT)} ({summary})"
    )
    return 0


def cmd_rollup(args: argparse.Namespace) -> int:
    if not REJECTIONS_CSV.exists():
        print("llm_rejections: no data yet")
        return 0
    since = args.since
    by_cat: Counter = Counter()
    by_agent_cat: Counter = Counter()
    total = 0
    with open(REJECTIONS_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if since and row.get("date", "") < since:
                continue
            total += 1
            by_cat[row.get("category", "Uncited")] += 1
            by_agent_cat[(row.get("source_agent", ""), row.get("category", ""))] += 1

    scope = f" since {since}" if since else ""
    print(f"LLM disqualifications{scope}: {total} total\n")
    print("By category:")
    for cat, n in by_cat.most_common():
        pct = (100 * n / total) if total else 0
        print(f"  {cat:<14} {n:>5}  ({pct:4.1f}%)")
    print("\nBy agent + category:")
    for (agent, cat), n in sorted(by_agent_cat.items(), key=lambda x: -x[1]):
        print(f"  {agent:<22} {cat:<14} {n:>5}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_append = sub.add_parser("append", help="append disqualified positions to the CSV")
    p_append.add_argument(
        "--source-agent",
        required=True,
        help="name of the calling review agent (e.g. ats-api-llm-review)",
    )
    g = p_append.add_mutually_exclusive_group()
    g.add_argument("--json", help="disqualified array as a JSON string, or '-' for stdin")
    g.add_argument("--json-file", help="path to a file containing the JSON")
    p_append.add_argument("--date", help="override the logged date (YYYY-MM-DD); defaults to today")
    p_append.set_defaults(func=cmd_append)

    p_rollup = sub.add_parser("rollup", help="aggregate logged disqualifications by category")
    p_rollup.add_argument("--since", help="only count rows on/after this date (YYYY-MM-DD)")
    p_rollup.set_defaults(func=cmd_rollup)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
