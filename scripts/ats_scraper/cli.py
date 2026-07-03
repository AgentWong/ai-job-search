"""
ATS API Scraper CLI

Usage:
    .venv/bin/python -m scripts.ats_scraper.cli [OPTIONS]

Options:
    --platforms PLATFORM [...]   Filter to specific platforms (default: all)
    --companies SLUG [...]       Filter to specific board tokens
    --posted-within WINDOW       Date filter: past_day, past_2_days, past_week, past_month
    --output PATH                JSON output file (default: results/ats_api_results.json)
    --dry-run                    Show targets without making API calls
    --verbose                    Per-company progress output
    --no-cooldown                Skip cooldown/ghost job checks
"""

import argparse
import concurrent.futures
import csv
import json
import re
import sys
import threading
import time
from datetime import date
from pathlib import Path

from scripts.effectiveness_tracker import totals as tracker_totals
from scripts.tracking_dashboard import cli as dashboard_cli

from .config import load_targets, load_config, load_exclusions, JobPosting
from .filters import apply_filters, build_target_roles_pattern, set_target_roles, FilterResult
from .location import LocationConfig
from .roles import active_role_buckets
from .platforms import PLATFORM_REGISTRY

CONFIG_DIR = Path(__file__).parent.parent.parent / "config"
RESULTS_DIR = Path(__file__).parent.parent.parent / "results"
TRACKING_DIR = RESULTS_DIR / "tracking"
TRACKING_DATA_DIR = TRACKING_DIR / "data"
LOG_DIR = Path(__file__).parent.parent.parent / "job_search_log"
APPLICATION_QUEUE = RESULTS_DIR / "application_queue.csv"
PENDING_REVIEW = RESULTS_DIR / "ats_api_pending_review.json"

PLATFORM_LIMITS = {
    "greenhouse": 8,
    "ashby": 6,
    "lever": 4,
    "rippling": 4,
    "workday": 2,
    "smartrecruiters": 2,
    "pinpoint": 2,
    "recruitee": 2,
    "bamboohr": 2,
    "breezy": 2,
    "oracle": 2,
    "trakstar": 4,
    "polymer": 4,
    "gem": 4,
    "comeet": 4,
    "careerpuck": 4,
    "eightfold": 2,
    "dayforce": 2,
    "workable": 4,
    "isolvedhire": 2,
}

CSV_HEADERS = [
    "company", "title", "url", "source_track", "discovered_date",
    "quality_score", "iac_tools", "cloud_platform", "remote_status",
    "match_reasons", "disqualifiers",
]


def build_description_snippet(text: str, length: int = 500) -> str:
    if not text:
        return ""
    return text[:length].strip()


def posting_to_dict(p: JobPosting) -> dict:
    return {
        "company": p.company,
        "title": p.title,
        "url": p.url,
        "location": p.location,
        "department": p.department,
        "compensation": p.compensation,
        "posted_date": p.posted_date,
        "workplace_type": p.workplace_type,
        "ats_platform": p.ats_platform,
        "description_snippet": build_description_snippet(p.description_text),
    }


def _load_existing_queue() -> set[str]:
    """Read existing application_queue.csv and return dedup keys (company|title)."""
    if not APPLICATION_QUEUE.exists():
        return set()
    keys = set()
    with open(APPLICATION_QUEUE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            keys.add(f"{row.get('company', '')}|{row.get('title', '')}")
    return keys


def _ensure_queue_headers() -> None:
    """Create application_queue.csv with headers if it doesn't exist."""
    if APPLICATION_QUEUE.exists():
        return
    APPLICATION_QUEUE.parent.mkdir(parents=True, exist_ok=True)
    with open(APPLICATION_QUEUE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()


def _append_to_queue(rows: list[dict]) -> int:
    """Append rows to application_queue.csv. Returns number of rows written."""
    if not rows:
        return 0
    with open(APPLICATION_QUEUE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        for row in rows:
            writer.writerow(row)
    return len(rows)


def _update_tracking(
    result: "FilterResult",
    per_company_counts: dict[str, int],
    targets: list,
) -> None:
    """Append this run's stats to the CSV trackers and refresh HTML dashboards."""
    today = date.today().isoformat()

    company_platform: dict[str, str] = {t.name: t.ats_platform for t in targets}

    platform_stats: dict[str, dict] = {}
    for company, summary in result.per_company.items():
        plat = company_platform.get(company, "Unknown")
        ps = platform_stats.setdefault(plat, {"companies": 0, "fetched": 0, "qualified": 0})
        ps["companies"] += 1
        ps["fetched"] += summary.fetched
        ps["qualified"] += summary.qualified

    plat_schema = tracker_totals.get_schema("ats_api_platform")
    plat_rows = [
        {
            "date": today,
            "platform": plat,
            "companies": ps["companies"],
            "fetched": ps["fetched"],
            "qualified": ps["qualified"],
        }
        for plat, ps in sorted(platform_stats.items())
    ]
    tracker_totals.append_rows(TRACKING_DATA_DIR / plat_schema.csv_filename, plat_schema, plat_rows)

    co_schema = tracker_totals.get_schema("ats_api_company")
    rej_schema = tracker_totals.get_schema("ats_api_company_rejection")
    co_rows = []
    rej_rows = []
    for company, summary in sorted(result.per_company.items()):
        platform = company_platform.get(company, "Unknown")
        top_rej = ""
        breakdown = ""
        if summary.rejections:
            reason, count = max(summary.rejections.items(), key=lambda x: x[1])
            top_rej = f"{reason} ({count})"
            # Sorted descending by count for stable ordering across runs;
            # `;` separator with `:` key/value is grep-friendly and CSV-safe.
            ordered = sorted(summary.rejections.items(), key=lambda x: (-x[1], x[0]))
            breakdown = ";".join(f"{r}:{c}" for r, c in ordered)
            for reason, count in ordered:
                rej_rows.append({
                    "date": today,
                    "company": company,
                    "platform": platform,
                    "reason": reason,
                    "count": count,
                })
        co_rows.append({
            "date": today,
            "company": company,
            "platform": platform,
            "fetched": summary.fetched,
            "qualified": summary.qualified,
            "top_rejection": top_rej,
            "rejection_breakdown": breakdown,
        })
    tracker_totals.append_rows(TRACKING_DATA_DIR / co_schema.csv_filename, co_schema, co_rows)
    tracker_totals.append_rows(TRACKING_DATA_DIR / rej_schema.csv_filename, rej_schema, rej_rows)

    plat_html = dashboard_cli.render("ats_api_platform")
    co_html = dashboard_cli.render("ats_api_company")
    print(
        f"\nTracking updated: {len(plat_rows)} platform rows, {len(co_rows)} company rows, "
        f"{len(rej_rows)} rejection-reason rows"
        f"\n  CSV: {(TRACKING_DATA_DIR / plat_schema.csv_filename).relative_to(RESULTS_DIR.parent)}"
        f"\n  CSV: {(TRACKING_DATA_DIR / co_schema.csv_filename).relative_to(RESULTS_DIR.parent)}"
        f"\n  CSV: {(TRACKING_DATA_DIR / rej_schema.csv_filename).relative_to(RESULTS_DIR.parent)}"
        f"\n  HTML: {plat_html.relative_to(RESULTS_DIR.parent)}"
        f"\n  HTML: {co_html.relative_to(RESULTS_DIR.parent)}"
    )


def run(args: argparse.Namespace) -> int:
    csv_path = CONFIG_DIR / "company_targets_ats.csv"
    config_path = CONFIG_DIR / "config.yml"
    exclusions_path = CONFIG_DIR / "exclusions.yml"

    targets = load_targets(csv_path)
    inclusions = load_config(config_path)
    excluded_companies = load_exclusions(exclusions_path)
    loc_cfg = LocationConfig.from_dict(inclusions)

    # Build the title-matching regex from config.yml so the role list
    # stays in sync with the YAML config used by the browser workflows.
    target_roles_cfg = inclusions.get("target_roles") or {}
    role_names: list[str] = []
    for bucket in active_role_buckets(loc_cfg):
        for entry in target_roles_cfg.get(bucket) or []:
            name = entry.get("name") if isinstance(entry, dict) else entry
            if name:
                role_names.append(name)
    if not role_names:
        print(
            "ERROR: config/config.yml has no target_roles.primary or .secondary entries",
            file=sys.stderr,
        )
        return 2
    set_target_roles(build_target_roles_pattern(role_names))

    # Skip rows explicitly marked as disabled (e.g. board taken offline upstream)
    targets = [t for t in targets if t.ats_platform.lower() != "disabled"]

    # Filter by platform
    selected_platforms = {p.lower() for p in args.platforms} if args.platforms else None
    if selected_platforms:
        targets = [t for t in targets if t.ats_platform.lower() in selected_platforms]

    # Filter by company slug
    if args.companies:
        slug_filter = {s.lower() for s in args.companies}
        targets = [t for t in targets if t.board_token.lower() in slug_filter]

    print(f"Targets: {len(targets)} companies")
    print(f"Mode: {loc_cfg.describe()}")
    if args.dry_run:
        for t in targets:
            print(f"  [{t.ats_platform}] {t.name} ({t.board_token})")
        return 0

    # Load cooldown/ghost job data (unless disabled)
    cooldown_data = None
    if not args.no_cooldown:
        from .cooldown import load_cooldown_data
        cooldown_data = load_cooldown_data(LOG_DIR, date.today())
        if cooldown_data.cooldown or cooldown_data.ghost:
            print(
                f"Cooldown: {len(cooldown_data.cooldown)} (company, role) pairs applied in past 60 days"
            )
            print(
                f"Ghost jobs: {len(cooldown_data.ghost)} suspected ghost job signals (no-response, >60d old)"
            )

    all_postings: list[JobPosting] = []
    errors: list[str] = []
    per_company_counts: dict[str, int] = {}

    for spec in args.max_workers_per_platform:
        if "=" not in spec:
            continue
        plat, n = spec.split("=", 1)
        try:
            PLATFORM_LIMITS[plat.lower()] = max(1, int(n))
        except ValueError:
            print(f"Ignoring invalid override: {spec}", file=sys.stderr)

    platform_semaphores = {
        plat: threading.Semaphore(n) for plat, n in PLATFORM_LIMITS.items()
    }
    max_workers = max(1, sum(PLATFORM_LIMITS.values()))

    def _fetch_one(target):
        platform_key = target.ats_platform.lower()
        fetcher = PLATFORM_REGISTRY.get(platform_key)
        if fetcher is None:
            return target, None, f"Unknown platform '{target.ats_platform}' for {target.name}"
        sem = platform_semaphores.get(platform_key)
        if sem is None:
            return target, None, f"No concurrency limit configured for platform '{platform_key}'"
        start = time.monotonic()
        with sem:
            try:
                postings = fetcher(target)
                return target, (postings, time.monotonic() - start), None
            except Exception as exc:
                return target, None, f"{target.name}: {exc}"

    total = len(targets)
    completed = 0
    overall_start = time.monotonic()

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_fetch_one, t) for t in targets]
        for fut in concurrent.futures.as_completed(futures):
            target, result, err = fut.result()
            completed += 1
            if err:
                errors.append(err)
                per_company_counts[target.name] = 0
                if args.verbose:
                    print(f"  [{completed}/{total}] ERROR {target.name}: {err}", file=sys.stderr)
                continue
            postings, elapsed = result
            per_company_counts[target.name] = len(postings)
            all_postings.extend(postings)
            if args.verbose:
                print(
                    f"  [{completed}/{total}] [{target.ats_platform}] {target.name}: "
                    f"{len(postings)} jobs ({elapsed:.1f}s)"
                )

    # Restore deterministic order regardless of completion sequence
    all_postings.sort(key=lambda p: (p.company.lower(), p.title.lower()))

    print(f"\nTotal jobs fetched: {len(all_postings)} in {time.monotonic() - overall_start:.1f}s")

    # Apply filter pipeline (includes cooldown, ghost detection, description disqualifiers)
    result: FilterResult = apply_filters(
        all_postings, excluded_companies, args.posted_within, cooldown_data, loc_cfg
    )

    # Print filter funnel
    print("\nFilter funnel:")
    for s in result.stats:
        pct = (s.output_count / s.input_count * 100) if s.input_count else 0
        print(f"  {s.stage}: {s.input_count} → {s.output_count} ({pct:.0f}% pass)")
        for reason, count in sorted(s.rejections.items(), key=lambda x: -x[1]):
            print(f"    - {reason}: {count}")

    print(f"\nQualified (with description): {len(result.qualified)}")
    print(f"No description (Rippling): {len(result.no_description)}")

    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(f"  {e}")

    # Per-platform breakdown
    platform_counts: dict[str, int] = {}
    for p in all_postings:
        platform_counts[p.ats_platform] = platform_counts.get(p.ats_platform, 0) + 1
    print("\nPer-platform breakdown:")
    for plat, cnt in sorted(platform_counts.items()):
        print(f"  {plat}: {cnt} jobs")

    # Per-company filter breakdown
    print("\nPer-company filter breakdown:")
    print(f"  {'Company':<28} {'Fetched':>7} {'Qualified':>9}  Top rejection")
    print(f"  {'-'*28} {'-'*7} {'-'*9}  {'-'*30}")
    for company, summary in sorted(result.per_company.items()):
        top = ""
        if summary.rejections:
            reason, count = max(summary.rejections.items(), key=lambda x: x[1])
            top = f"{reason} ({count})"
        print(f"  {company:<28} {summary.fetched:>7} {summary.qualified:>9}  {top}")

    # Score qualified postings
    from .scorer import score_posting, score_posting_no_description
    scored_qualified = [(p, score_posting(p)) for p in result.qualified]
    scored_no_desc = [(p, score_posting_no_description(p)) for p in result.no_description]

    # Print scored results
    if scored_qualified or scored_no_desc:
        print("\nScored positions:")
        for p, sc in sorted(scored_qualified, key=lambda x: -x[1].score):
            print(f"  [{sc.score}/10] {p.company} — {p.title}")
            print(f"         {sc.match_reasons} | {sc.disqualifiers}")
        for p, sc in scored_no_desc:
            print(f"  [{sc.score}/10] {p.company} — {p.title}  (no description — needs verification)")

    # --- Persist scored candidates ---
    today_str = date.today().isoformat()

    if args.no_llm_review:
        # Legacy path: write directly to application_queue.csv with score >= 4 cutoff
        _ensure_queue_headers()
        existing_keys = _load_existing_queue()

        queue_rows_to_write: list[dict] = []
        dupes_skipped = 0

        for p, sc in scored_qualified + scored_no_desc:
            key = f"{p.company}|{p.title}"
            if key in existing_keys:
                dupes_skipped += 1
                continue
            existing_keys.add(key)

            if sc.score < 4 and p not in result.no_description:
                print(f"  SKIP (score {sc.score} < 4): {p.company} — {p.title}")
                continue

            queue_rows_to_write.append({
                "company": p.company,
                "title": p.title,
                "url": p.url,
                "source_track": f"ats-api-{p.ats_platform}",
                "discovered_date": today_str,
                "quality_score": sc.score,
                "iac_tools": sc.iac_tools,
                "cloud_platform": sc.cloud_platform,
                "remote_status": p.workplace_type or p.location or "",
                "match_reasons": sc.match_reasons,
                "disqualifiers": sc.disqualifiers,
            })

        written = _append_to_queue(queue_rows_to_write)
        print(f"\nApplication queue: {written} new positions written, {dupes_skipped} duplicates skipped")
        print(f"Queue file: {APPLICATION_QUEUE}")
    else:
        # Default path: stage scored candidates for LLM fuzzy review.
        # The orchestrator will invoke the ats-api-llm-review agent on this file.
        # All candidates are staged (including score < 4) — the LLM may catch
        # signals the regex scoring missed.
        from .cooldown import get_company_recent_applications
        pending_records = []
        for p, sc in scored_qualified + scored_no_desc:
            recent_apps = get_company_recent_applications(p.company, LOG_DIR, date.today())
            pending_records.append({
                "company": p.company,
                "title": p.title,
                "url": p.url,
                "ats_platform": p.ats_platform,
                "location": p.location,
                "workplace_type": p.workplace_type,
                "department": p.department,
                "compensation": p.compensation,
                "posted_date": p.posted_date,
                "description_full": p.description_text or "",
                "description_available": p.description_available,
                "regex_score": sc.score,
                "regex_iac_tools": sc.iac_tools,
                "regex_cloud_platform": sc.cloud_platform,
                "regex_match_reasons": sc.match_reasons,
                "regex_disqualifiers": sc.disqualifiers,
                "discovered_date": today_str,
                "recent_company_applications": recent_apps,
            })

        PENDING_REVIEW.parent.mkdir(parents=True, exist_ok=True)
        with open(PENDING_REVIEW, "w", encoding="utf-8") as f:
            json.dump(pending_records, f, indent=2)

        print(f"\nPending LLM review: {len(pending_records)} candidates staged")
        print(f"Staging file: {PENDING_REVIEW}")
        print(f"Next step: orchestrator should invoke the ats-api-llm-review agent on this file")

    # Build output JSON
    output_data = {
        "summary": {
            "total_companies": len(targets),
            "total_fetched": len(all_postings),
            "filter_funnel": [
                {
                    "stage": s.stage,
                    "input": s.input_count,
                    "output": s.output_count,
                    "pass_rate": round(s.output_count / s.input_count, 3) if s.input_count else 0,
                    "rejections": s.rejections,
                }
                for s in result.stats
            ],
            "per_platform": platform_counts,
            "per_company_fetch_counts": per_company_counts,
            "per_company_filter": {
                company: {
                    "fetched": s.fetched,
                    "qualified": s.qualified,
                    "rejections": s.rejections,
                }
                for company, s in sorted(result.per_company.items())
            },
            "errors": errors,
        },
        "qualified_positions": [
            {**posting_to_dict(p), "quality_score": sc.score, "iac_tools": sc.iac_tools,
             "cloud_platform": sc.cloud_platform, "match_reasons": sc.match_reasons,
             "disqualifiers": sc.disqualifiers}
            for p, sc in scored_qualified
        ],
        "positions_without_descriptions": [
            {**posting_to_dict(p), "quality_score": sc.score}
            for p, sc in scored_no_desc
        ],
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print(f"\nJSON output written to {output_path}")

    # Update effectiveness tracking
    _update_tracking(result, per_company_counts, targets)

    return 0


def main():
    parser = argparse.ArgumentParser(description="ATS API scraper")
    parser.add_argument(
        "--platforms", nargs="+", metavar="PLATFORM",
        help="Filter to specific platforms (ashby, bamboohr, breezy, careerpuck, comeet, "
             "dayforce, eightfold, gem, greenhouse, lever, oracle, pinpoint, polymer, "
             "recruitee, rippling, smartrecruiters, trakstar, workday)",
    )
    parser.add_argument(
        "--companies", nargs="+", metavar="SLUG",
        help="Filter to specific board tokens",
    )
    parser.add_argument(
        "--posted-within", choices=["past_day", "past_2_days", "past_week", "past_month"],
        default=None,
        help="Filter to jobs posted within time window (past_day, past_2_days, past_week, past_month)",
    )
    parser.add_argument(
        "--output", default=str(RESULTS_DIR / "ats_api_results.json"),
        help="JSON output file path (default: results/ats_api_results.json)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show targets without making API calls",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Per-company progress output",
    )
    parser.add_argument(
        "--no-cooldown", action="store_true",
        help="Skip cooldown/ghost job checks (useful for testing)",
    )
    parser.add_argument(
        "--max-workers-per-platform", nargs="+", metavar="PLATFORM=N", default=[],
        help="Override per-platform concurrency limits, e.g. --max-workers-per-platform workday=1 greenhouse=12",
    )
    parser.add_argument(
        "--no-llm-review", action="store_true",
        help="Skip LLM fuzzy review and write directly to application_queue.csv (legacy behavior). "
             "By default, scored candidates are staged to results/ats_api_pending_review.json for the "
             "ats-api-llm-review agent to review before queue write.",
    )
    args = parser.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
