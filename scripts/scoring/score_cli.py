"""
JSON-in / JSON-out wrapper around `scripts.ats_scraper.scorer.score_posting`.

Lets non-ATS pipelines (browser-fetch, manual scoring) share one scoring
implementation with the ATS API scraper. Same regex rules, same base score,
same boosters/penalties/disqualifiers — without an LLM re-deriving them from
`shared/scoring_framework.md` on every run.

Usage:
    .venv/bin/python -m scripts.scoring.score_cli --input-file postings.json
    .venv/bin/python -m scripts.scoring.score_cli --input-stdin < postings.json
    .venv/bin/python -m scripts.scoring.score_cli --json '[{...}]'

Input shape (array of postings; single-object input is wrapped automatically):

    [
      {
        "url": "https://...",                 # required — passed through to output
        "title": "DevOps Engineer",
        "description": "...full job text...",
        "company": "Foo Corp",                # optional
        "location": "Remote - US",            # optional
        "compensation": "$120k-$150k",        # optional
        "workplace_type": "remote",           # optional
        "description_available": true         # optional, default true
      }
    ]

Output: an array (same order) of:

    [
      {
        "url": "https://...",
        "score": 7,
        "iac_tools": "Terraform, Ansible",
        "cloud_platform": "AWS",
        "match_reasons": "Terraform +2, Ansible +2, AWS-focused +2",
        "disqualifiers": "None",
        "description_disqualified": false,
        "disqualify_reason": ""
      }
    ]

Exit codes: 0 always (errors per-item land in the output as
`description_disqualified=false, score=0, disqualify_reason="error: ..."`). The
caller decides how to react.
"""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from scripts.ats_scraper.config import JobPosting
from scripts.ats_scraper.scorer import score_posting, score_posting_no_description


def score_one(item: dict[str, Any]) -> dict[str, Any]:
    url = item.get("url", "")
    description = item.get("description", "") or item.get("description_text", "")
    description_available = item.get("description_available", bool(description))

    posting = JobPosting(
        company=item.get("company", ""),
        title=item.get("title", ""),
        url=url,
        location=item.get("location", ""),
        department=item.get("department", ""),
        description_text=description,
        ats_platform=item.get("ats_platform", ""),
        compensation=item.get("compensation", ""),
        posted_date=item.get("posted_date", ""),
        workplace_type=item.get("workplace_type", ""),
        description_available=bool(description_available),
    )

    if not description_available or not description:
        result = score_posting_no_description(posting)
    else:
        result = score_posting(posting)

    out = asdict(result)
    out["url"] = url
    return out


def main():
    parser = argparse.ArgumentParser(
        description="Score job postings via the shared regex scoring framework."
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--input-file", type=Path, help="Path to JSON file (array or single object)")
    src.add_argument("--input-stdin", action="store_true", help="Read JSON from stdin")
    src.add_argument("--json", dest="inline_json", help="Inline JSON string (array or single object)")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print output")
    args = parser.parse_args()

    if args.input_file:
        raw = args.input_file.read_text(encoding="utf-8")
    elif args.input_stdin:
        raw = sys.stdin.read()
    else:
        raw = args.inline_json

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON input: {e}", file=sys.stderr)
        sys.exit(2)

    if isinstance(data, dict):
        data = [data]
    elif not isinstance(data, list):
        print(f"ERROR: input must be JSON object or array, got {type(data).__name__}", file=sys.stderr)
        sys.exit(2)

    results = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            results.append({
                "url": "",
                "score": 0,
                "iac_tools": "",
                "cloud_platform": "",
                "match_reasons": "",
                "disqualifiers": "",
                "description_disqualified": False,
                "disqualify_reason": f"error: item {i} is not an object",
            })
            continue
        try:
            results.append(score_one(item))
        except Exception as e:
            results.append({
                "url": item.get("url", ""),
                "score": 0,
                "iac_tools": "",
                "cloud_platform": "",
                "match_reasons": "",
                "disqualifiers": "",
                "description_disqualified": False,
                "disqualify_reason": f"error: {type(e).__name__}: {e}",
            })

    indent = 2 if args.pretty else None
    print(json.dumps(results, indent=indent))


if __name__ == "__main__":
    main()
