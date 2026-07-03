#!/usr/bin/env python3
"""Build a manifest of (app_id, folder_path) for every row in applications.csv.

Used by the match-% rescore workflow: subagents consume the manifest to find
the posting + resume for each application and score them against the new rubric.
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = REPO_ROOT / "job_search_log"
CSV_PATH = LOG_DIR / "applications.csv"
OUT_PATH = REPO_ROOT / "scripts" / "match_rescore" / "manifest.json"


def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", "", text.lower())
    return text


def candidate_folders(month: str) -> list[Path]:
    month_dir = LOG_DIR / month
    if not month_dir.is_dir():
        return []
    return sorted(p for p in month_dir.iterdir() if p.is_dir())


# Hardcoded overrides where the folder name doesn't contain the company/role
# verbatim (e.g., scraper landed an Indeed-branded folder name, or the CSV
# company label was inferred later from the posting content).
FOLDER_OVERRIDES: dict[str, str] = {
    "unknown-company__2026-02-21": "2026-02/GitLab - Intermediate Site Reliability Engineer, Tenant Scale Tenant Services",
    "mayo-clinic__2026-04-27": "2026-04/Cloud Platform Engineering - IT Cloud Engineer",
    "mindex__2026-04-30": "2026-04/Remote - Cloud Engineer",
}


def find_folder(company: str, role: str, month: str, app_id: str) -> Path | None:
    """Match a CSV row to its folder by fuzzy company+role slug overlap."""
    if app_id in FOLDER_OVERRIDES:
        candidate = LOG_DIR.parent / "job_search_log" / FOLDER_OVERRIDES[app_id]
        return candidate if candidate.is_dir() else None

    target_company = slug(company)
    target_role = slug(role)
    if not target_company:
        return None

    best: tuple[int, Path] | None = None
    for folder in candidate_folders(month):
        name = folder.name
        # Folder format is roughly "Company - Role" or "Role - Company" (older)
        parts = [p.strip() for p in name.split(" - ", 1)]
        if len(parts) != 2:
            continue
        a_slug = slug(parts[0])
        b_slug = slug(parts[1])

        score = 0
        # Strongest signal: company matches one side
        if target_company and (
            target_company in a_slug
            or a_slug in target_company
            or target_company in b_slug
            or b_slug in target_company
        ):
            score += 10
        # Role overlap
        if target_role and (
            target_role[:8] in (a_slug + b_slug) or (a_slug + b_slug)[:8] in target_role
        ):
            score += 3
        # Tiebreaker: any token overlap
        for token in re.split(r"\s+", role.lower()):
            if len(token) >= 4 and slug(token) and slug(token) in (a_slug + b_slug):
                score += 1

        if score >= 10:
            if best is None or score > best[0]:
                best = (score, folder)

    return best[1] if best else None


def main() -> None:
    rows = list(csv.DictReader(CSV_PATH.open()))
    manifest: list[dict] = []
    unmatched: list[dict] = []

    for row in rows:
        app_id = row["app_id"]
        company = row["company"]
        role = row["role"]
        date_applied = row["date_applied"]

        if not date_applied:
            continue  # placeholder rows like Members 1st FCU
        try:
            month = datetime.strptime(date_applied, "%Y-%m-%d").strftime("%Y-%m")
        except ValueError:
            continue

        folder = find_folder(company, role, month, app_id)
        if folder is None:
            unmatched.append({"app_id": app_id, "company": company, "role": role, "month": month})
            continue

        posting = folder / "posting.md"
        resume = folder / "resume.txt"
        manifest.append(
            {
                "app_id": app_id,
                "company": company,
                "role": role,
                "month": month,
                "folder": str(folder.relative_to(REPO_ROOT)),
                "posting": str(posting.relative_to(REPO_ROOT)) if posting.exists() else None,
                "resume": str(resume.relative_to(REPO_ROOT)) if resume.exists() else None,
                "old_match_pct": row["match_pct"],
            }
        )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps({"manifest": manifest, "unmatched": unmatched}, indent=2))

    print(f"matched: {len(manifest)}")
    print(f"unmatched: {len(unmatched)}")
    print(f"missing posting: {sum(1 for m in manifest if not m['posting'])}")
    print(f"missing resume: {sum(1 for m in manifest if not m['resume'])}")
    print(f"wrote: {OUT_PATH.relative_to(REPO_ROOT)}")
    if unmatched:
        print("\nUnmatched rows (need manual review):")
        for u in unmatched:
            print(f"  {u['app_id']}: {u['company']} - {u['role']} ({u['month']})")


if __name__ == "__main__":
    main()
