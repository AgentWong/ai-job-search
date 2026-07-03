"""
ATS slug validator.

Validate the ATS_Slug column in config/company_targets_ats.csv by issuing one
small request per company to the platform's public API. When a slug fails,
optionally probe a short list of platform-specific candidate slugs to suggest
a fix.

Usage:
    .venv/bin/python -m scripts.ats_slug_validator [options]

Common invocations:
    # Validate everything:
    .venv/bin/python -m scripts.ats_slug_validator

    # Validate only companies added in a specific commit:
    .venv/bin/python -m scripts.ats_slug_validator --since-commit 1f11867

    # Validate one company:
    .venv/bin/python -m scripts.ats_slug_validator --company "CrowdStrike"

    # Validate by platform:
    .venv/bin/python -m scripts.ats_slug_validator --platform greenhouse

    # Try to find fixes for broken slugs:
    .venv/bin/python -m scripts.ats_slug_validator --suggest-fixes

    # Output JSON for programmatic consumption:
    .venv/bin/python -m scripts.ats_slug_validator --json

Exit codes:
    0 - all probed slugs OK (or at least one suggestion was found for each)
    1 - one or more slugs failed and no fix was found
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from .probes import ProbeResult, probe, discover, DISCOVERY_PROBES
from .suggesters import suggest


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CSV = REPO_ROOT / "config" / "company_targets_ats.csv"


@dataclass
class Row:
    line_no: int
    name: str
    platform: str
    slug: str
    career_url: str

    @property
    def platform_key(self) -> str:
        return (self.platform or "").strip().lower()


def load_rows(csv_path: Path) -> list[Row]:
    rows: list[Row] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [h.strip() for h in (reader.fieldnames or [])]
        for i, raw in enumerate(reader, start=2):
            clean = {k.strip(): (v.strip() if v else "") for k, v in raw.items() if k is not None}
            rows.append(Row(
                line_no=i,
                name=clean.get("Company_Name", ""),
                platform=clean.get("ATS_Platform", ""),
                slug=clean.get("ATS_Slug", ""),
                career_url=clean.get("Career_Page_URL", ""),
            ))
    return rows


def rows_added_in_commit(commit: str, csv_path: Path) -> set[str]:
    """Return the set of Company_Name values added to csv_path in `commit`."""
    rel = csv_path.relative_to(REPO_ROOT)
    out = subprocess.check_output(
        ["git", "show", commit, "--", str(rel)],
        cwd=REPO_ROOT,
        text=True,
    )
    names: set[str] = set()
    for line in out.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        # CSV row starts with company name as the first comma-separated field.
        first = line[1:].split(",", 1)[0].strip()
        if first and first != "Company_Name":
            names.add(first)
    return names


def filter_rows(rows: list[Row], args) -> list[Row]:
    if args.since_commit:
        wanted: set[str] = set()
        for c in args.since_commit:
            wanted.update(rows_added_in_commit(c, args.csv))
        rows = [r for r in rows if r.name in wanted]
    if args.company:
        wanted = {c.strip().lower() for c in args.company}
        rows = [r for r in rows if r.name.lower() in wanted]
    if args.platform:
        wanted = {p.strip().lower() for p in args.platform}
        rows = [r for r in rows if r.platform_key in wanted]
    if args.only_supported:
        from .probes import PROBES
        rows = [r for r in rows if r.platform_key in PROBES]
    return rows


@dataclass
class ValidationOutcome:
    row: Row
    initial: ProbeResult
    suggestion: Optional[str] = None
    suggestion_result: Optional[ProbeResult] = None

    @property
    def status(self) -> str:
        if self.initial.ok:
            return "ok"
        if self.suggestion_result and self.suggestion_result.ok:
            return "fixable"
        return "broken"


def probe_one(row: Row, args) -> ValidationOutcome:
    initial = probe(row.platform_key, row.slug, row.career_url)
    outcome = ValidationOutcome(row=row, initial=initial)
    if initial.ok or not (args.suggest_fixes or args.cross_platform):
        return outcome
    # Same-platform candidates first (most-likely fixes)
    if args.suggest_fixes:
        candidates = suggest(row.platform_key, row.name, row.slug, row.career_url)
        for cand in candidates:
            if cand == row.slug:
                continue
            result = probe(row.platform_key, cand, row.career_url)
            if result.ok:
                outcome.suggestion = cand
                outcome.suggestion_result = result
                return outcome
    # Cross-platform: try the same slug (and basic variants) on other platforms
    if args.cross_platform:
        from .probes import PROBES
        # Build a small candidate slug list per platform
        base = row.slug
        from .suggesters import suggest as _suggest
        for plat_key in PROBES:
            if plat_key == row.platform_key:
                continue
            # Generate plat-specific candidates from the company name
            cands = _suggest(plat_key, row.name, base, row.career_url)
            for cand in cands[:5]:  # cap probes
                result = probe(plat_key, cand, row.career_url)
                if result.ok and (result.jobs_total or 0) > 0:
                    outcome.suggestion = f"[{plat_key}] {cand}"
                    outcome.suggestion_result = result
                    return outcome
    return outcome


def format_text(outcomes: list[ValidationOutcome]) -> str:
    lines: list[str] = []
    ok = [o for o in outcomes if o.status == "ok"]
    fixable = [o for o in outcomes if o.status == "fixable"]
    broken = [o for o in outcomes if o.status == "broken"]
    skipped = [o for o in outcomes if o.initial.status_code is None and o.initial.detail.startswith("no probe")]

    lines.append(f"Validated {len(outcomes)} slugs")
    lines.append(f"  OK:      {len(ok)}")
    lines.append(f"  Fixable: {len(fixable)}")
    lines.append(f"  Broken:  {len(broken)}")
    if skipped:
        lines.append(f"  Skipped (no probe): {len(skipped)}")
    lines.append("")

    if fixable:
        lines.append("=== FIXABLE (suggested replacements) ===")
        for o in fixable:
            lines.append(
                f"  [{o.row.platform}] {o.row.name} (line {o.row.line_no})"
            )
            lines.append(f"      current:  '{o.row.slug}'  -> {o.initial.detail}")
            sug = o.suggestion_result
            jobs = sug.jobs_total if sug and sug.jobs_total is not None else "?"
            lines.append(
                f"      suggest:  '{o.suggestion}'  -> ok ({jobs} jobs)"
            )
        lines.append("")

    if broken:
        lines.append("=== BROKEN (no working alternative found) ===")
        for o in broken:
            lines.append(
                f"  [{o.row.platform}] {o.row.name} (line {o.row.line_no})"
            )
            lines.append(f"      slug:   '{o.row.slug}'")
            lines.append(f"      detail: {o.initial.detail}")
            lines.append(f"      probed: {o.initial.probe_url}")
        lines.append("")

    if ok:
        lines.append("=== OK ===")
        for o in ok:
            jobs = o.initial.jobs_total if o.initial.jobs_total is not None else "?"
            warn = "  AMBIGUOUS" if "ambiguous" in (o.initial.detail or "").lower() else ""
            lines.append(
                f"  [{o.row.platform:<15}] {o.row.name:<30}  '{o.row.slug}'  -> {jobs} jobs{warn}"
            )

    return "\n".join(lines)


def format_json(outcomes: list[ValidationOutcome]) -> str:
    def serialize(o: ValidationOutcome) -> dict:
        d = {
            "company": o.row.name,
            "platform": o.row.platform,
            "slug": o.row.slug,
            "career_url": o.row.career_url,
            "line_no": o.row.line_no,
            "status": o.status,
            "initial": asdict(o.initial),
        }
        if o.suggestion is not None:
            d["suggestion"] = o.suggestion
            d["suggestion_result"] = asdict(o.suggestion_result) if o.suggestion_result else None
        return d

    return json.dumps([serialize(o) for o in outcomes], indent=2)


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ats_slug_validator", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", type=Path, default=DEFAULT_CSV,
                   help=f"Path to ATS targets CSV (default: {DEFAULT_CSV})")
    p.add_argument("--company", action="append", default=[],
                   help="Filter by Company_Name (case-insensitive). Repeatable.")
    p.add_argument("--platform", action="append", default=[],
                   help="Filter by ATS_Platform (case-insensitive). Repeatable.")
    p.add_argument("--since-commit", action="append", default=[],
                   help="Filter to rows added to the CSV in this commit. Repeatable.")
    p.add_argument("--only-supported", action="store_true", default=True,
                   help="Only validate platforms with a probe implementation (default: True).")
    p.add_argument("--all-platforms", dest="only_supported", action="store_false",
                   help="Include unsupported platforms in output (will be marked skipped).")
    p.add_argument("--suggest-fixes", action="store_true",
                   help="For broken slugs, probe a small set of plausible alternatives on the same platform.")
    p.add_argument("--cross-platform", action="store_true",
                   help="For broken slugs, also probe candidate slugs on other ATS platforms (slower).")
    p.add_argument("--discover", metavar="SLUG", action="append", default=[],
                   help="Probe SLUG against every known ATS platform. Repeatable.")
    p.add_argument("--discover-career-url", default="",
                   help="Career URL hint (helps Workday parse tenant/board for --discover).")
    p.add_argument("--discover-platform", action="append", default=[],
                   help="With --discover, probe only on these platform(s). Repeatable.")
    p.add_argument("--workers", type=int, default=8,
                   help="Concurrent probe workers (default: 8).")
    p.add_argument("--json", action="store_true",
                   help="Emit machine-readable JSON instead of human-readable text.")
    return p


def run_discover(slugs: list[str], career_url: str, platforms: list[str],
                 as_json: bool) -> int:
    all_results: dict[str, dict[str, ProbeResult]] = {}
    plat_filter = {p.strip().lower() for p in platforms} or None
    for slug in slugs:
        results = discover(slug, career_url)
        if plat_filter is not None:
            results = {p: r for p, r in results.items() if p in plat_filter}
        all_results[slug] = results

    if as_json:
        out = {
            slug: {
                "career_url": career_url,
                "results": {plat: asdict(r) for plat, r in results.items()},
                "hits": [plat for plat, r in results.items() if r.ok],
            }
            for slug, results in all_results.items()
        }
        print(json.dumps(out, indent=2))
    else:
        any_hits = False
        for slug, results in all_results.items():
            hits = [(plat, r) for plat, r in results.items() if r.ok]
            print(f"Discovery probe for slug '{slug}':")
            if hits:
                any_hits = True
                print(f"  Found on {len(hits)} platform(s):")
                for plat, r in hits:
                    print(f"    [{plat}] {r.detail}  ({r.probe_url})")
            else:
                print("  No platform responded OK.")
            print()
            print("  All probes:")
            for plat, r in results.items():
                mark = "OK " if r.ok else "-- "
                print(f"    {mark}{plat:<18} {r.detail}")
            print()
    return 0 if any(any(r.ok for r in v.values()) for v in all_results.values()) else 1


def main() -> int:
    args = build_argparser().parse_args()
    if args.discover:
        return run_discover(args.discover, args.discover_career_url,
                            args.discover_platform, args.json)
    all_rows = load_rows(args.csv)
    rows = filter_rows(all_rows, args)
    if not rows:
        print("No rows matched the given filters.", file=sys.stderr)
        return 0

    outcomes: list[ValidationOutcome] = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(probe_one, r, args): r for r in rows}
        for fut in as_completed(futures):
            outcomes.append(fut.result())

    # Stable ordering by CSV line for human readability
    outcomes.sort(key=lambda o: o.row.line_no)

    if args.json:
        print(format_json(outcomes))
    else:
        print(format_text(outcomes))

    has_unfixable = any(o.status == "broken" for o in outcomes)
    return 1 if has_unfixable else 0


if __name__ == "__main__":
    sys.exit(main())
