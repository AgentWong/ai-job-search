"""Organize files in Clippings/ into per-month job folders under job_search_log/.

Replaces steps 1-6 of the process-clippings workflow. Parses the YAML frontmatter
of each primary clipping .md file to determine the target month folder and the
company/role for the per-job folder name, then moves/renames the clipping,
matching resume pdf, and matching cover letter into that folder.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path


COVER_LETTER_SUFFIX = "Cover_Letter.md"
TITLE_SEPARATORS = [" - ", " @ ", " at ", " | "]
DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def strip_cover_letter_suffix(stem: str) -> str:
    """Given a file stem ending with 'Cover_Letter', derive the group base name.

    Strips a trailing 'Cover_Letter' plus an optional separator char (space, dash,
    underscore). Examples:
        'Acme - DevOpsCover_Letter'   -> 'Acme - DevOps'
        'Acme - DevOps Cover_Letter'  -> 'Acme - DevOps'
        'Acme - DevOps-Cover_Letter'  -> 'Acme - DevOps'
        'Acme - DevOps_Cover_Letter'  -> 'Acme - DevOps'
    """
    if not stem.endswith("Cover_Letter"):
        return stem
    base = stem[: -len("Cover_Letter")]
    if base and base[-1] in (" ", "-", "_"):
        base = base[:-1]
    return base


def is_cover_letter_file(path: Path) -> bool:
    return path.name.endswith(COVER_LETTER_SUFFIX)


def group_base_name(path: Path) -> str:
    """Return the group base name for a file in Clippings/."""
    if is_cover_letter_file(path):
        return strip_cover_letter_suffix(path.stem)
    return path.stem


def parse_frontmatter(md_path: Path) -> dict[str, str]:
    """Parse a simple YAML-ish frontmatter block from a markdown file.

    Looks for an opening '---' line and reads until the closing '---' line,
    splitting each intermediate line on the first ':'. Values are stripped of
    surrounding quotes and whitespace. Returns an empty dict if no frontmatter
    block is present.
    """
    try:
        text = md_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        # Strip surrounding quotes.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if key:
            fields[key] = value
    return fields


def split_title(title: str) -> tuple[str, str] | None:
    """Split a title like 'Role - Company' into (role, company).

    Tries each separator in priority order. Returns None if no separator matches.
    """
    for sep in TITLE_SEPARATORS:
        if sep in title:
            role, _, company = title.partition(sep)
            role = role.strip()
            company = company.strip()
            if role and company:
                return role, company
    return None


def parse_created_to_month(created: str) -> str | None:
    """Return 'YYYY-MM' if `created` matches YYYY-MM-DD, else None."""
    m = DATE_RE.match(created.strip())
    if not m:
        return None
    return f"{m.group(1)}-{m.group(2)}"


def scan_clippings(clippings_dir: Path) -> dict[str, dict[str, Path]]:
    """Scan a Clippings directory for .md and .pdf files and group by base name.

    Returns a mapping:
        { base_name: { 'primary_md': Path?, 'pdf': Path?, 'cover_letter': Path? } }
    """
    groups: dict[str, dict[str, Path]] = defaultdict(dict)
    if not clippings_dir.exists():
        return {}

    for entry in sorted(clippings_dir.iterdir()):
        if not entry.is_file():
            continue
        suffix = entry.suffix.lower()
        if suffix not in (".md", ".pdf"):
            continue

        base = group_base_name(entry)
        group = groups[base]

        if suffix == ".md":
            if is_cover_letter_file(entry):
                group["cover_letter"] = entry
            else:
                group["primary_md"] = entry
        elif suffix == ".pdf":
            group["pdf"] = entry

    return dict(groups)


def plan_group(
    base: str,
    files: dict[str, Path],
    logs_root: Path,
    verbose: bool,
) -> dict | None:
    """Produce a plan dict for one group, or None if the group should be skipped.

    Plan dict has keys:
        folder_name, month, target_dir, moves: list[(src, dst)]
    """
    primary = files.get("primary_md")
    if primary is None:
        if verbose:
            print(
                f"[warn] Group '{base}' has no primary .md file — skipping.",
                file=sys.stderr,
            )
        return None

    fm = parse_frontmatter(primary)
    created = fm.get("created", "")
    title = fm.get("title", "")

    month = parse_created_to_month(created)
    if month is None:
        if verbose:
            print(
                f"[warn] Group '{base}' has missing/malformed 'created' date "
                f"({created!r}) — skipping.",
                file=sys.stderr,
            )
        return None

    split = split_title(title)
    if split is None:
        if verbose:
            print(
                f"[warn] Group '{base}' has unparseable 'title' {title!r} — "
                f"no separator matched. Skipping.",
                file=sys.stderr,
            )
        return None

    role, company = split
    folder_name = f"{company} - {role}"
    target_dir = logs_root / month / folder_name

    moves: list[tuple[Path, Path]] = [(primary, target_dir / "posting.md")]
    if "pdf" in files:
        moves.append((files["pdf"], target_dir / "resume.pdf"))
    if "cover_letter" in files:
        moves.append((files["cover_letter"], target_dir / "cover_letter.md"))

    return {
        "folder_name": folder_name,
        "month": month,
        "target_dir": target_dir,
        "moves": moves,
    }


def execute_plan(
    plan: dict,
    archive_dir: Path | None,
    verbose: bool,
) -> tuple[int, int]:
    """Execute a single plan. Returns (moved, skipped_overwrite) counts."""
    target_dir: Path = plan["target_dir"]
    target_dir.mkdir(parents=True, exist_ok=True)

    moved = 0
    skipped = 0
    for src, dst in plan["moves"]:
        if dst.exists():
            print(
                f"[warn] Target {dst} already exists — skipping move of {src.name}.",
                file=sys.stderr,
            )
            skipped += 1
            continue
        if archive_dir is not None:
            # Copy to destination, then move original to archive.
            shutil.copy2(src, dst)
            archive_dir.mkdir(parents=True, exist_ok=True)
            archive_dst = archive_dir / src.name
            # If an archive file already exists with the same name, leave the
            # original in place rather than clobbering.
            if archive_dst.exists():
                if verbose:
                    print(
                        f"[warn] Archive target {archive_dst} exists — "
                        f"leaving original {src} in place.",
                        file=sys.stderr,
                    )
            else:
                shutil.move(str(src), str(archive_dst))
        else:
            shutil.move(str(src), str(dst))
        moved += 1
    return moved, skipped


def format_dry_run(plan: dict, clippings_dir: Path, logs_root: Path) -> str:
    rel_month = plan["target_dir"].parent
    try:
        rel_month_display = rel_month.relative_to(Path.cwd())
    except ValueError:
        rel_month_display = rel_month
    lines = [f"[dry-run] {plan['folder_name']} → {rel_month_display}/"]
    for src, dst in plan["moves"]:
        try:
            src_display = src.relative_to(Path.cwd())
        except ValueError:
            src_display = src
        lines.append(f"            {dst.name}  (from {src_display})")
    return "\n".join(lines)


def run(
    clippings_dir: Path,
    logs_root: Path,
    dry_run: bool,
    archive_instead_of_delete: bool,
    verbose: bool,
) -> int:
    clippings_dir = clippings_dir.resolve()
    logs_root = logs_root.resolve()

    groups = scan_clippings(clippings_dir)

    processed = 0
    skipped_groups = 0
    skip_reasons: dict[str, int] = defaultdict(int)

    archive_dir = (
        clippings_dir / ".processed" if archive_instead_of_delete else None
    )

    for base in sorted(groups):
        files = groups[base]
        plan = plan_group(base, files, logs_root, verbose)
        if plan is None:
            skipped_groups += 1
            if "primary_md" not in files:
                skip_reasons["no primary .md"] += 1
            else:
                fm = parse_frontmatter(files["primary_md"])
                if parse_created_to_month(fm.get("created", "")) is None:
                    skip_reasons["bad created date"] += 1
                elif split_title(fm.get("title", "")) is None:
                    skip_reasons["unparseable title"] += 1
                else:
                    skip_reasons["other"] += 1
            continue

        if dry_run:
            print(format_dry_run(plan, clippings_dir, logs_root))
        else:
            execute_plan(plan, archive_dir, verbose)
            try:
                month_display = plan["target_dir"].parent.relative_to(Path.cwd())
            except ValueError:
                month_display = plan["target_dir"].parent
            print(f"Processed: {plan['folder_name']} → {month_display}/")
        processed += 1

    try:
        logs_root_display = logs_root.relative_to(Path.cwd())
    except ValueError:
        logs_root_display = logs_root

    reasons_part = ""
    if skipped_groups:
        reasons = ", ".join(f"{k}: {v}" for k, v in sorted(skip_reasons.items()))
        reasons_part = f" ({reasons})"

    if dry_run:
        print(
            f"Would organize {processed} jobs | Skipped {skipped_groups}"
            f"{reasons_part} | Path: {logs_root_display}"
        )
    else:
        print(
            f"Organized {processed} jobs | Skipped {skipped_groups}"
            f"{reasons_part} | Path: {logs_root_display}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Organize files in Clippings/ into per-month job folders under "
            "job_search_log/."
        )
    )
    parser.add_argument(
        "--clippings-dir",
        default="Clippings",
        help="Directory to scan for clipping files (default: Clippings).",
    )
    parser.add_argument(
        "--logs-root",
        default="job_search_log",
        help="Root directory for per-month logs (default: job_search_log).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned moves without touching the filesystem.",
    )
    parser.add_argument(
        "--archive-instead-of-delete",
        action="store_true",
        help=(
            "After moving, keep original files under "
            "<clippings-dir>/.processed/ instead of deleting them."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Emit warnings for skipped groups and other notable events.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(
        clippings_dir=Path(args.clippings_dir),
        logs_root=Path(args.logs_root),
        dry_run=args.dry_run,
        archive_instead_of_delete=args.archive_instead_of_delete,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    sys.exit(main())
