"""
Disable ATS entries where Employee_Count_Estimate upper bound is <= threshold.
Sets URL_Status from 'active' to 'disabled' for those rows.

Usage:
    python scripts/disable_small_companies.py [--threshold 50] [--dry-run]
"""

import argparse
import csv
import io
import re
import sys


def max_headcount(val: str) -> int | None:
    val = val.strip().lstrip("~").strip()
    nums = [int(n) for n in re.findall(r"\d+", val)]
    return max(nums) if nums else None


def run(csv_path: str, threshold: int, dry_run: bool) -> None:
    with open(csv_path, newline="", encoding="utf-8") as f:
        raw = f.read()

    reader = csv.DictReader(io.StringIO(raw), skipinitialspace=True)
    fieldnames = reader.fieldnames

    rows = list(reader)
    changed = []

    for row in rows:
        m = max_headcount(row["Employee_Count_Estimate"])
        if m is not None and m <= threshold and row["URL_Status"].strip().lower() == "active":
            changed.append((row["Company_Name"], row["Employee_Count_Estimate"], row["URL_Status"]))
            row["URL_Status"] = "disabled"

    if not changed:
        print("No rows matched — nothing to change.")
        return

    print(f"{'DRY RUN: ' if dry_run else ''}Updating {len(changed)} row(s):")
    for name, count, old_status in changed:
        print(f"  {name!r:40} | count={count!r:15} | {old_status!r} -> 'disabled'")

    if dry_run:
        return

    out = io.StringIO()
    # Preserve the original header spacing (leading space after comma)
    writer = csv.DictWriter(
        out,
        fieldnames=fieldnames,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        # DictWriter strips leading spaces from field names; restore original header line
        body = out.getvalue()
        lines = body.splitlines(keepends=True)
        # Replace generated header with original header line
        original_header = raw.splitlines(keepends=True)[0]
        lines[0] = original_header
        f.writelines(lines)

    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", default="config/company_targets_ats.csv")
    parser.add_argument("--threshold", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    run(args.csv, args.threshold, args.dry_run)
