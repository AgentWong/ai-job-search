"""
Queue writer CLI for the ats-api-llm-review agent.

Reads a JSON file containing the LLM agent's review verdicts and appends
qualified rows to results/application_queue.csv with the same dedup logic
used by the main scraper.

Input JSON shape:
    {
      "qualified": [
        {
          "company": "...",
          "title": "...",
          "url": "...",
          "ats_platform": "...",
          "remote_status": "...",
          "quality_score": 7,
          "iac_tools": "Terraform",
          "cloud_platform": "AWS",
          "match_reasons": "...",
          "disqualifiers": "None",
          "discovered_date": "2026-04-24"
        }
      ],
      "disqualified": [
        {
          "company": "...",
          "title": "...",
          "url": "...",
          "disqualification_reason": "Senior-level role (Level III)"
        }
      ]
    }

Usage:
    .venv/bin/python -m scripts.ats_scraper.queue_writer <verdicts_json_path>
"""

import csv
import json
import sys
from pathlib import Path

from .cooldown import normalize_company, normalize_role

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results"
LOG_DIR = REPO_ROOT / "job_search_log"
APPLICATION_QUEUE = RESULTS_DIR / "application_queue.csv"

CSV_HEADERS = [
    "company", "title", "url", "source_track", "discovered_date",
    "quality_score", "iac_tools", "cloud_platform", "remote_status",
    "match_reasons", "disqualifiers",
]


def _load_applied_entries() -> set[tuple[str, str]]:
    """Return normalized (company, role) pairs from job_search_log/applications.csv.

    Uses the same normalization rules as the cooldown filter so the safety-net
    check here matches what the upstream filter pipeline applied.
    """
    apps_csv = LOG_DIR / "applications.csv"
    if not apps_csv.exists():
        return set()
    entries: set[tuple[str, str]] = set()
    with open(apps_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            company = normalize_company((row.get("company") or "").strip())
            role = normalize_role((row.get("role") or "").strip())
            if company and role:
                entries.add((company, role))
    return entries


def _already_applied(company: str, title: str, applied: set[tuple[str, str]]) -> bool:
    """Return True if this (company, title) pair matches a logged application
    after normalization (corporate suffixes stripped, seniority modifiers
    stripped, SRE collapsed to Site Reliability Engineer).
    """
    return (normalize_company(company), normalize_role(title)) in applied


def _load_existing_queue_keys() -> set[str]:
    if not APPLICATION_QUEUE.exists():
        return set()
    keys = set()
    with open(APPLICATION_QUEUE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            keys.add(f"{row.get('company', '')}|{row.get('title', '')}")
    return keys


def _ensure_queue_headers() -> None:
    if APPLICATION_QUEUE.exists():
        return
    APPLICATION_QUEUE.parent.mkdir(parents=True, exist_ok=True)
    with open(APPLICATION_QUEUE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: queue_writer.py <verdicts_json_path>", file=sys.stderr)
        return 2

    verdicts_path = Path(argv[1])
    if not verdicts_path.exists():
        print(f"Verdicts file not found: {verdicts_path}", file=sys.stderr)
        return 2

    with open(verdicts_path, encoding="utf-8") as f:
        verdicts = json.load(f)

    qualified = verdicts.get("qualified", [])
    disqualified = verdicts.get("disqualified", [])

    _ensure_queue_headers()
    existing_keys = _load_existing_queue_keys()
    applied_entries = _load_applied_entries()

    written = 0
    dupes_skipped = 0
    already_applied_skipped = 0
    rows_to_write = []

    for entry in qualified:
        company = entry.get("company", "")
        title = entry.get("title", "")
        key = f"{company}|{title}"
        if _already_applied(company, title, applied_entries):
            already_applied_skipped += 1
            continue
        if key in existing_keys:
            dupes_skipped += 1
            continue
        existing_keys.add(key)

        platform = entry.get("ats_platform", "")
        rows_to_write.append({
            "company": company,
            "title": title,
            "url": entry.get("url", ""),
            "source_track": f"ats-api-{platform}" if platform else "ats-api",
            "discovered_date": entry.get("discovered_date", ""),
            "quality_score": entry.get("quality_score", ""),
            "iac_tools": entry.get("iac_tools", ""),
            "cloud_platform": entry.get("cloud_platform", ""),
            "remote_status": entry.get("remote_status", ""),
            "match_reasons": entry.get("match_reasons", ""),
            "disqualifiers": entry.get("disqualifiers", "None"),
        })

    if rows_to_write:
        with open(APPLICATION_QUEUE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            for row in rows_to_write:
                writer.writerow(row)
                written += 1

    summary = {
        "qualified_input": len(qualified),
        "disqualified_input": len(disqualified),
        "written_to_queue": written,
        "duplicates_skipped": dupes_skipped,
        "already_applied_skipped": already_applied_skipped,
        "queue_path": str(APPLICATION_QUEUE),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
