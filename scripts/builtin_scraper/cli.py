"""
Built In jobs API scraper CLI.

Usage:
    .venv/bin/python -m scripts.builtin_scraper.cli [OPTIONS]

Mirrors scripts/linkedin_scraper/cli.py: discovers postings, applies cheap
regex filters in Python, optionally stages survivors for LLM fuzzy review.

Options:
    --roles ROLE [...]           Filter to specific roles (default: all from config.yml)
    --posted-within WINDOW       past_day, past_2_days, past_week, past_month (default: from config.yml)
    --max-pages N                Max search pages per role (default: 3)
    --max-per-role N             Max survivors to detail-fetch per role (default: 15)
    --search-delay S             Seconds between search requests (default: 2.0)
    --detail-delay S             Seconds between detail requests (default: 3.0)
    --spam-threshold N           Drop all postings when a single (company, title) appears N+ times (default: 3)
    --dry-run                    Print plan without making any HTTP requests
    --verbose                    Per-role progress output
    --no-cooldown                Skip cooldown/ghost job checks
    --no-llm-review              Write directly to application_queue.csv (legacy)
    --output PATH                Summary JSON output (default: results/builtin_api_results.json)
"""

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

from scripts.ats_scraper.config import load_config, load_exclusions
from scripts.ats_scraper.location import LocationConfig
from scripts.ats_scraper.roles import active_role_buckets
from scripts.ats_scraper.cooldown import (
    get_company_recent_applications,
    load_cooldown_data,
    normalize_company,
    normalize_role,
)
from scripts.ats_scraper.scorer import score_posting, score_posting_no_description
from scripts.effectiveness_tracker import totals as tracker_totals
from scripts.tracking_dashboard import cli as dashboard_cli

from .dedup import detect_spam_and_dedupe
from .detail import fetch_detail
from .fetcher import RateLimitedSession, RateLimitError
from .filters import filter_card
from .search import search_role

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
RESULTS_DIR = REPO_ROOT / "results"
TRACKING_DATA_DIR = RESULTS_DIR / "tracking" / "data"
LOG_DIR = REPO_ROOT / "job_search_log"
APPLICATION_QUEUE = RESULTS_DIR / "application_queue.csv"
PENDING_REVIEW = RESULTS_DIR / "builtin_pending_review.json"

TRACKER_NAME = "builtin_api_role"

CSV_HEADERS = [
    "company", "title", "url", "source_track", "discovered_date",
    "quality_score", "iac_tools", "cloud_platform", "remote_status",
    "match_reasons", "disqualifiers",
]


def _collect_roles(inclusions: dict, loc_cfg: LocationConfig) -> list[dict]:
    """Flatten configured target_roles into one priority-ordered list.

    Always covers primary + secondary; the high-noise `local_only` tier is
    included only in local mode (location.remote: false) — see
    active_role_buckets.
    """
    target_roles_cfg = inclusions.get("target_roles") or {}
    roles: list[dict] = []
    for tier in active_role_buckets(loc_cfg):
        for entry in target_roles_cfg.get(tier) or []:
            if isinstance(entry, dict) and entry.get("name"):
                roles.append({
                    "name": entry["name"],
                    "tier": tier,
                    "priority": entry.get("priority", 99),
                })
    roles.sort(key=lambda r: r["priority"])
    return roles


def _load_existing_queue_keys() -> set[str]:
    if not APPLICATION_QUEUE.exists():
        return set()
    keys = set()
    with open(APPLICATION_QUEUE, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            keys.add(f"{row.get('company', '')}|{row.get('title', '')}")
    return keys


def _ensure_queue_headers() -> None:
    if APPLICATION_QUEUE.exists():
        return
    APPLICATION_QUEUE.parent.mkdir(parents=True, exist_ok=True)
    with open(APPLICATION_QUEUE, "w", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=CSV_HEADERS).writeheader()


def _update_tracking(
    per_role_stats: dict[str, dict],
    pending_records: list[dict],
    today_iso: str,
) -> None:
    """
    Append per-role results to results/tracking/data/builtin_api_role_effectiveness.csv
    and refresh its HTML dashboard.

    Uses the dedicated `builtin_api_role` schema so long-term trend data for
    this workflow stays isolated from the shared `browser_role` tracker (now
    hiringcafe-only; it historically also aggregated the retired browser
    linkedin + builtin workflows).

    `qualified` count = pending records where regex_score >= 4 (the same
    threshold downstream consumers use for queue write). The downstream LLM
    review may further reject some, but that mirrors how the linkedin-api and
    ats-api trackers write their regex-qualified counts too.
    """
    if not per_role_stats:
        return

    # Count regex-qualified records per role (regex_score >= 4)
    qualified_by_role: dict[str, int] = {}
    for rec in pending_records:
        role = rec.get("builtin_role_searched", "")
        if rec.get("regex_score", 0) >= 4:
            qualified_by_role[role] = qualified_by_role.get(role, 0) + 1

    schema = tracker_totals.get_schema(TRACKER_NAME)
    rows = [
        {
            "date": today_iso,
            "role": role,
            "found": stats["found"],
            "qualified": qualified_by_role.get(role, 0),
        }
        for role, stats in sorted(per_role_stats.items())
    ]
    csv_path = TRACKING_DATA_DIR / schema.csv_filename
    tracker_totals.append_rows(csv_path, schema, rows)
    html_path = dashboard_cli.render(TRACKER_NAME)

    print(
        f"\nTracking: appended {len(rows)} rows to "
        f"{csv_path.relative_to(REPO_ROOT)}\n"
        f"  HTML: {html_path.relative_to(REPO_ROOT)}"
    )


def run(args: argparse.Namespace) -> int:
    inclusions = load_config(CONFIG_DIR / "config.yml")
    excluded_companies = load_exclusions(CONFIG_DIR / "exclusions.yml")
    loc_cfg = LocationConfig.from_dict(inclusions)

    roles = _collect_roles(inclusions, loc_cfg)
    if not roles:
        print("ERROR: config/config.yml has no target_roles.primary or .secondary entries", file=sys.stderr)
        return 2

    # Filter to requested roles if --roles given
    if args.roles:
        wanted = {r.lower() for r in args.roles}
        roles = [r for r in roles if r["name"].lower() in wanted]
        if not roles:
            print(f"ERROR: none of {args.roles} matched config.yml roles", file=sys.stderr)
            return 2

    # Resolve time_filter
    time_filter = args.posted_within or (
        inclusions.get("search_config", {}).get("time_filter") or "past_2_days"
    )

    print(f"Roles: {len(roles)}  |  time_filter: {time_filter}  |  mode: {loc_cfg.describe()}  |  max_pages: {args.max_pages}  |  max_per_role: {args.max_per_role}")
    for r in roles:
        print(f"  [{r['tier']:9s} p{r['priority']:>2}] {r['name']}")

    if args.dry_run:
        return 0

    # Cooldown
    cooldown_data = None
    if not args.no_cooldown:
        cooldown_data = load_cooldown_data(LOG_DIR, date.today())
        print(
            f"Cooldown: {len(cooldown_data.cooldown)} (company, role) pairs in past 60 days; "
            f"{len(cooldown_data.ghost)} suspected ghost jobs"
        )

    session = RateLimitedSession(
        search_delay=args.search_delay,
        detail_delay=args.detail_delay,
        verbose=args.verbose,
    )

    # ------------------------------------------------------------------
    # Phase 1: search & pre-fetch filter per role
    # ------------------------------------------------------------------
    today_iso = date.today().isoformat()
    per_role_stats: dict[str, dict] = {}
    survivors_by_role: dict[str, list] = {}  # role_name -> list of SearchCard
    rejections: dict[str, int] = {}

    try:
        for role in roles:
            name = role["name"]
            print(f"\n=== {name} ({role['tier']}) ===")
            cards = search_role(
                session,
                name,
                time_filter=time_filter,
                loc_cfg=loc_cfg,
                max_pages=args.max_pages,
                verbose=args.verbose,
            )
            print(f"  found: {len(cards)} cards")

            kept: list = []
            role_rejections: dict[str, int] = {}
            for card in cards:
                v = filter_card(card, excluded_companies, loc_cfg)
                if not v.keep:
                    bucket = v.reason.split(":", 1)[0]
                    role_rejections[bucket] = role_rejections.get(bucket, 0) + 1
                    rejections[bucket] = rejections.get(bucket, 0) + 1
                    continue
                kept.append(card)

            print(f"  after filters: {len(kept)} (rejected {len(cards) - len(kept)})")
            if args.verbose and role_rejections:
                for r, c in sorted(role_rejections.items(), key=lambda x: -x[1]):
                    print(f"    - {r}: {c}")

            # Cooldown — exact-match URL-style check via normalized (company, role)
            if cooldown_data is not None:
                pre = len(kept)
                kept = [
                    c for c in kept
                    if (normalize_company(c.company), normalize_role(c.title))
                    not in cooldown_data.cooldown
                ]
                skipped = pre - len(kept)
                if skipped:
                    rejections["Cooldown"] = rejections.get("Cooldown", 0) + skipped
                    print(f"  after cooldown: {len(kept)} (skipped {skipped} same-role-recent)")

            survivors_by_role[name] = kept
            per_role_stats[name] = {
                "found": len(cards),
                "kept_after_filters": len(kept),
            }

        # ------------------------------------------------------------------
        # Phase 1b: cross-role dedup + spam removal
        # ------------------------------------------------------------------
        # Done after all roles are filtered+cooldowned so we have the full
        # cross-role view. Must run BEFORE max_per_role cap so a spammy company
        # can't burn the cap with 15 identical (company, title) cards.
        survivors_by_role, dedup_stats = detect_spam_and_dedupe(
            survivors_by_role, spam_threshold=args.spam_threshold
        )
        if dedup_stats.spam_dropped:
            rejections["Spam (3+ identical postings)"] = dedup_stats.spam_dropped
            print(
                f"\nSpam removal ({args.spam_threshold}+ identical postings): "
                f"dropped {dedup_stats.spam_dropped} cards across "
                f"{len(dedup_stats.spam_pairs)} (company, title) pairs"
            )
            for company, title, count in dedup_stats.spam_pairs:
                print(f"  [{count}x] {company} - {title}")
        if dedup_stats.duplicate_dropped:
            rejections["Cross-role duplicate"] = dedup_stats.duplicate_dropped
            print(
                f"\nCross-role duplicates removed: {dedup_stats.duplicate_dropped} "
                f"(same job surfaced under multiple role searches)"
            )

        # Cap to max_per_role. Runs after dedup so the cap reflects the deduped pool.
        cap_total_dropped = 0
        for name, kept in survivors_by_role.items():
            if len(kept) > args.max_per_role:
                if args.verbose:
                    print(f"  capping {name} to {args.max_per_role} of {len(kept)} survivors")
                cap_total_dropped += len(kept) - args.max_per_role
                survivors_by_role[name] = kept[: args.max_per_role]
            per_role_stats[name]["kept_after_filters"] = len(survivors_by_role[name])
        if cap_total_dropped:
            rejections["max_per_role cap"] = cap_total_dropped

        # ------------------------------------------------------------------
        # Phase 2: detail-fetch each survivor and score
        # ------------------------------------------------------------------
        pending_records: list[dict] = []
        fetch_errors: list[str] = []

        total_to_fetch = sum(len(s) for s in survivors_by_role.values())
        print(f"\n=== Phase 2: detail fetch ({total_to_fetch} URLs) ===")
        fetched = 0
        for role_name, cards in survivors_by_role.items():
            for card in cards:
                fetched += 1
                if args.verbose:
                    print(f"  [{fetched}/{total_to_fetch}] {card.company} - {card.title}")
                try:
                    posting = fetch_detail(session, card)
                except RateLimitError as exc:
                    fetch_errors.append(str(exc))
                    print(f"\nABORT: {exc}", file=sys.stderr)
                    # Save what we have so far and exit cleanly
                    break
                except Exception as exc:
                    fetch_errors.append(f"{card.url}: {exc}")
                    continue

                if posting is None:
                    fetch_errors.append(f"{card.url}: empty/404")
                    continue

                # Score
                if posting.description_available:
                    sc = score_posting(posting)
                else:
                    sc = score_posting_no_description(posting)

                # Collect recent applications at this company for the LLM agent's
                # Step 0 fuzzy same-role match
                recent_apps = (
                    get_company_recent_applications(posting.company, LOG_DIR, date.today())
                    if not args.no_cooldown else []
                )

                pending_records.append({
                    "company": posting.company,
                    "title": posting.title,
                    "url": posting.url,
                    "ats_platform": "Built In",
                    "location": posting.location,
                    "workplace_type": posting.workplace_type,
                    "department": posting.department,
                    "compensation": posting.compensation,
                    "posted_date": posting.posted_date,
                    "description_full": posting.description_text or "",
                    "description_available": posting.description_available,
                    "regex_score": sc.score,
                    "regex_iac_tools": sc.iac_tools,
                    "regex_cloud_platform": sc.cloud_platform,
                    "regex_match_reasons": sc.match_reasons,
                    "regex_disqualifiers": sc.disqualifiers,
                    "discovered_date": today_iso,
                    "recent_company_applications": recent_apps,
                    "builtin_role_searched": role_name,
                })
            else:
                continue  # role complete
            break  # rate-limit abort propagated

    except RateLimitError as exc:
        print(f"\nABORT: {exc}", file=sys.stderr)
        # Fall through to write partial results

    # ------------------------------------------------------------------
    # Persist
    # ------------------------------------------------------------------
    if args.no_llm_review:
        # Legacy path: filter to score >= 4 and append directly
        _ensure_queue_headers()
        existing_keys = _load_existing_queue_keys()
        written = 0
        skipped_low_score = 0
        dupes = 0
        with open(APPLICATION_QUEUE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            for rec in pending_records:
                key = f"{rec['company']}|{rec['title']}"
                if key in existing_keys:
                    dupes += 1
                    continue
                if rec["regex_score"] < 4 and rec["description_available"]:
                    skipped_low_score += 1
                    continue
                writer.writerow({
                    "company": rec["company"],
                    "title": rec["title"],
                    "url": rec["url"],
                    "source_track": "builtin-api",
                    "discovered_date": rec["discovered_date"],
                    "quality_score": rec["regex_score"],
                    "iac_tools": rec["regex_iac_tools"],
                    "cloud_platform": rec["regex_cloud_platform"],
                    "remote_status": rec.get("workplace_type") or rec.get("location") or "",
                    "match_reasons": rec["regex_match_reasons"],
                    "disqualifiers": rec["regex_disqualifiers"],
                })
                existing_keys.add(key)
                written += 1
        print(f"\nApplication queue: {written} written, {dupes} dupes, {skipped_low_score} score<4")
        print(f"Queue file: {APPLICATION_QUEUE}")
    else:
        # Default: stage for LLM review
        PENDING_REVIEW.parent.mkdir(parents=True, exist_ok=True)
        with open(PENDING_REVIEW, "w", encoding="utf-8") as f:
            json.dump(pending_records, f, indent=2)
        print(f"\nPending LLM review: {len(pending_records)} candidates staged")
        print(f"Staging file: {PENDING_REVIEW}")
        print(f"Next step: orchestrator should invoke the builtin-llm-review agent on this file")

    # ------------------------------------------------------------------
    # Summary JSON
    # ------------------------------------------------------------------
    summary = {
        "summary": {
            "time_filter": time_filter,
            "roles_searched": len(roles),
            "total_cards_found": sum(s["found"] for s in per_role_stats.values()),
            "total_after_filters": sum(s["kept_after_filters"] for s in per_role_stats.values()),
            "total_fetched": len(pending_records),
            "rejection_breakdown": rejections,
            "per_role": per_role_stats,
            "fetch_errors": fetch_errors,
        },
        "staged_records": len(pending_records),
        "pending_review_file": str(PENDING_REVIEW) if not args.no_llm_review else None,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nJSON summary: {output_path}")

    # Filter funnel print
    if rejections:
        print("\nRejection breakdown (Phase 1 + cooldown):")
        for reason, count in sorted(rejections.items(), key=lambda x: -x[1]):
            print(f"  {reason}: {count}")

    # Effectiveness tracking
    _update_tracking(per_role_stats, pending_records, today_iso)

    return 0


def main():
    parser = argparse.ArgumentParser(description="Built In jobs API scraper")
    parser.add_argument("--roles", nargs="+", metavar="ROLE",
        help="Filter to specific roles (default: all from config.yml)")
    parser.add_argument("--posted-within",
        choices=["past_day", "past_2_days", "past_week", "past_month"],
        default=None,
        help="Time filter (default: from config.yml search_config.time_filter)")
    parser.add_argument("--max-pages", type=int, default=3,
        help="Max search pages per role (default: 3)")
    parser.add_argument("--max-per-role", type=int, default=15,
        help="Max detail fetches per role after filters (default: 15)")
    parser.add_argument("--search-delay", type=float, default=2.0,
        help="Seconds between search requests (default: 2.0)")
    parser.add_argument("--detail-delay", type=float, default=3.0,
        help="Seconds between detail requests (default: 3.0)")
    parser.add_argument("--spam-threshold", type=int, default=3,
        help="Drop all postings when a single (company, title) pair appears N+ times across cities (default: 3, min: 2)")
    parser.add_argument("--dry-run", action="store_true",
        help="Print plan without HTTP requests")
    parser.add_argument("--verbose", action="store_true",
        help="Per-role progress output")
    parser.add_argument("--no-cooldown", action="store_true",
        help="Skip cooldown/ghost-job checks")
    parser.add_argument("--no-llm-review", action="store_true",
        help="Write directly to application_queue.csv (legacy mode)")
    parser.add_argument("--output", default=str(RESULTS_DIR / "builtin_api_results.json"),
        help="JSON summary output path")

    args = parser.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
