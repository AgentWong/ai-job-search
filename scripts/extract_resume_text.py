#!/usr/bin/env python3
"""Extract plain text from resume.pdf files in job_search_log/ directories.

Walks the job_search_log/ tree and runs `pdftotext` on every resume.pdf,
writing resume.txt alongside it. By default, skips PDFs that already have
an up-to-date resume.txt (mtime newer than the PDF).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOG_DIR = REPO_ROOT / "job_search_log"


def find_resume_pdfs(root: Path) -> list[Path]:
    return sorted(root.rglob("resume.pdf"))


def needs_extraction(pdf: Path, txt: Path, force: bool) -> bool:
    if force:
        return True
    if not txt.exists():
        return True
    return txt.stat().st_mtime < pdf.stat().st_mtime


def extract(pdf: Path, txt: Path) -> tuple[bool, str]:
    # -layout preserves columns/spacing better for resume layouts.
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf), str(txt)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False, result.stderr.strip() or "pdftotext failed"
    return True, ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=DEFAULT_LOG_DIR,
        help=f"Root to search (default: {DEFAULT_LOG_DIR})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-extract even if resume.txt is newer than resume.pdf",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List what would be extracted without running pdftotext",
    )
    args = parser.parse_args()

    if shutil.which("pdftotext") is None:
        print("error: pdftotext not found in PATH (install poppler-utils)", file=sys.stderr)
        return 2

    if not args.log_dir.is_dir():
        print(f"error: {args.log_dir} is not a directory", file=sys.stderr)
        return 2

    pdfs = find_resume_pdfs(args.log_dir)
    if not pdfs:
        print(f"no resume.pdf files found under {args.log_dir}")
        return 0

    extracted = 0
    skipped = 0
    failed: list[tuple[Path, str]] = []

    for pdf in pdfs:
        txt = pdf.with_suffix(".txt")
        rel = pdf.relative_to(args.log_dir)
        if not needs_extraction(pdf, txt, args.force):
            skipped += 1
            continue
        if args.dry_run:
            print(f"would extract: {rel}")
            extracted += 1
            continue
        ok, err = extract(pdf, txt)
        if ok:
            print(f"extracted: {rel}")
            extracted += 1
        else:
            print(f"FAILED: {rel} ({err})", file=sys.stderr)
            failed.append((pdf, err))

    print(
        f"\nsummary: {extracted} extracted, {skipped} skipped (up-to-date), "
        f"{len(failed)} failed, {len(pdfs)} total"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
