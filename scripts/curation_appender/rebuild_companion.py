"""Rebuild the lean companion JSON file from the authoritative ATS CSV.

The full CSV is the source of truth, but pasting it into Claude Desktop
research mode burns context — each row has paragraphs of research notes that
aren't needed for duplicate detection. The companion JSON contains only the
fields needed to answer "is this company already covered?" so the research
agents can cross-reference efficiently.

Runnable standalone for a one-off regenerate, or called by cli.py after
every append run to keep the JSON in sync with the CSV.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .csv_reader import read_rows


ROOT = Path(__file__).parent.parent.parent
ATS_CSV = ROOT / "config" / "company_targets_ats.csv"
ATS_JSON = ROOT / "config" / "company_targets_ats.json"


def rebuild_ats(csv_path: Path = ATS_CSV, json_path: Path = ATS_JSON) -> int:
    """Emit {name, company_url, career_page_url, ats_platform} per company."""
    _, rows = read_rows(csv_path)
    companies = [
        {
            "name": r.get("Company_Name", ""),
            "company_url": r.get("Company_URL", ""),
            "career_page_url": r.get("Career_Page_URL", ""),
            "ats_platform": r.get("ATS_Platform", ""),
        }
        for r in rows
        if r.get("Company_Name", "").strip()
    ]
    _write_json(json_path, {"companies": companies})
    return len(companies)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def rebuild_all(verbose: bool = False) -> int:
    ats_count = rebuild_ats()
    if verbose:
        print(f"Rebuilt {ATS_JSON.name}: {ats_count} companies")
    return ats_count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Regenerate the lean companion JSON from the ATS target CSV")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    rebuild_all(verbose=args.verbose)
    return 0


if __name__ == "__main__":
    sys.exit(main())
