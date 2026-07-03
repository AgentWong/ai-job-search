"""Python-driven Firecrawl ATS platform search (Option A) — CLI.

Runs one role tier of the query queue end-to-end without an LLM in the data
path: search Firecrawl directly, write raw JSON to disk, refund a credit,
regex pre-filter, and stage kept results (with full markdown + deterministic
board/role attribution) into review batches for the ats-platform-review agent.

Usage:
    .venv/bin/python -m scripts.ats_platform_search.cli --tier primary
    .venv/bin/python -m scripts.ats_platform_search.cli --tier secondary

Common options:
    --tier {primary,secondary}   Role tier to execute (required).
    --time-window WINDOW         past_day|past_2_days|past_week|past_month|past_year
                                 (default: search_config.time_filter from config.yml)
    --tbs STRING                 Raw Google tbs override (bypasses --time-window).
    --search-limit N             Results per query (default: search_config.search_limit).
    --concurrency N              Parallel searches (default: 4).
    --review-batch-size N        Kept items per review batch file (default: 0 =
                                 ALL kept in a single batch → one review subagent;
                                 set N>0 only to split an unusually large run).
    --no-feedback                Skip the credit-refund feedback call (testing).
    --no-scrape                  Drop scrapeOptions — cheap, markdown-less (testing).
    --no-workday-enrich          Skip the Workday CXS description backfill (testing).
    --no-workable-enrich         Skip the Workable JSON location resolution (testing).
    --boards DOMAIN [...]        Only run queries covering these domains (testing).
    --max-queries N              Only run the first N queries of the tier (testing).

Outputs (under --cache-dir, default results/ats_platform_cache/):
    q{NN}_raw.json               Verbatim Firecrawl response (debug; never read by an LLM).
    q{NN}_filtered.json          {search_id, stats, kept[], discarded[]} (kept carry markdown).
    review_batch_{tier}_{BB}.json  Annotated kept items for the review subagent
                                   (one file by default; multiple only if --review-batch-size>0).
    search_summary_{tier}.json   Small manifest the orchestrator reads (no markdown).

Stdout: a human-readable summary; the orchestrator parses search_summary_{tier}.json.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

from scripts.ats_scraper.config import load_config
from scripts.ats_scraper.location import LocationConfig
from scripts.ats_platform_filter.filters import filter_result, listing_health, load_excluded_companies
from scripts.ats_platform_filter.workday_enrich import enrich_workday_result
from scripts.ats_platform_filter.workable_enrich import enrich_workable_result

from .firecrawl_client import FirecrawlClient, FirecrawlError
from . import query_builder as qb

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
DEFAULT_CACHE_DIR = REPO_ROOT / "results" / "ats_platform_cache"


def _web_results(resp: dict) -> list[dict]:
    """Extract the result list from a /v2/search response (data.web)."""
    data = resp.get("data") if isinstance(resp, dict) else None
    if isinstance(data, dict):
        return list(data.get("web") or [])
    if isinstance(data, list):  # defensive: alternate shape
        return list(data)
    return []


def _annotate_kept(item: dict, query: "qb.Query", max_md: int) -> dict:
    """Build a review-batch record from a kept Firecrawl result."""
    markdown = item.get("markdown") or ""
    if max_md and len(markdown) > max_md:
        markdown = markdown[:max_md]
    url = item.get("url", "") or ""
    return {
        "query_number": query.query_number,
        "tier": query.tier,
        "job_board": query.board_label,
        "source_domain": qb.attribute_board(url, query.bundled_domains),
        "matched_role": qb.attribute_role(item.get("title", ""), query.roles),
        "title": item.get("title", "") or "",
        "url": url,
        "snippet": item.get("description", "") or "",
        "description_full": markdown,
        "description_available": bool(markdown.strip()),
    }


def _process_query(
    query: "qb.Query",
    client: FirecrawlClient,
    loc_cfg: LocationConfig,
    excluded: set,
    remote_mode: bool,
    cache_dir: Path,
    args: argparse.Namespace,
) -> dict:
    """Search one query, write raw + filtered, refund, return a result record.

    Runs inside the thread pool. Returns a dict (never raises) so one failed
    query doesn't sink the batch — errors are recorded in the record.
    """
    qn = query.query_number
    query_string = qb.build_query_string(query, loc_cfg)
    record: dict = {
        "query_number": qn,
        "tier": query.tier,
        "board_label": query.board_label,
        "bundled_domains": query.bundled_domains,
        "roles": query.roles,
        "query_string": query_string,
        "search_id": None,
        "credits_used": None,
        "results_found": 0,
        "kept": 0,
        "discarded": 0,
        "workday_enriched": 0,
        "workable_dropped": 0,
        "by_reason": {},
        "refund": {"status": "skipped"},
        "kept_items": [],
        "found_by_domain": defaultdict(int),
        "kept_by_domain": defaultdict(int),
        "found_by_role": defaultdict(int),
        "kept_by_role": defaultdict(int),
        "error": None,
    }

    try:
        resp = client.search(
            query_string,
            limit=args.search_limit,
            tbs=args.tbs,
            location=qb.search_location(loc_cfg),
            scrape_markdown=not args.no_scrape,
        )
    except FirecrawlError as exc:
        record["error"] = str(exc)
        # Still write an (empty) raw file so the cache-file contract holds.
        (cache_dir / f"q{qn:02d}_raw.json").write_text(
            json.dumps({"error": str(exc)}, indent=2), encoding="utf-8"
        )
        return record

    record["search_id"] = resp.get("id")
    record["credits_used"] = resp.get("creditsUsed")

    # Write raw verbatim — this is the offload that keeps the payload out of any
    # LLM context. Always written, regardless of size (no coverage gap).
    (cache_dir / f"q{qn:02d}_raw.json").write_text(json.dumps(resp, indent=2), encoding="utf-8")

    results = _web_results(resp)
    record["results_found"] = len(results)

    # Refund 1 credit. Visible success/failure — never a silent cost leak.
    if not args.no_feedback and record["search_id"]:
        try:
            if results:
                fb = client.submit_feedback(
                    record["search_id"],
                    valuable_urls=[r.get("url", "") for r in results[:5]],
                )
            else:
                topic = f"US-remote {'/'.join(query.roles[:3])} roles on {query.board_label}"
                fb = client.submit_feedback(record["search_id"], missing_topic=topic)
            record["refund"] = {
                "status": "ok",
                "credits_refunded": fb.get("creditsRefunded"),
                "credits_refunded_today": fb.get("creditsRefundedToday"),
                "daily_refund_cap": fb.get("dailyRefundCap"),
            }
        except FirecrawlError as exc:
            record["refund"] = {"status": "failed", "error": str(exc)}

    # Regex pre-filter + attribution.
    kept_items: list[dict] = []
    discarded: list[dict] = []
    by_reason: dict = {}
    # Reused across this query's Workday CXS / Workable JSON fetches
    # (keep-alive); created lazily on first hit of each platform.
    wd_session = None
    wk_session = None
    for item in results:
        url = item.get("url", "") or ""
        domain = qb.attribute_board(url, query.bundled_domains)
        role = qb.attribute_role(item.get("title", ""), query.roles)
        record["found_by_domain"][domain] += 1
        record["found_by_role"][role] += 1

        # Backfill Workday descriptions Firecrawl couldn't render (its only
        # no_description source) via the public CXS API — before filtering, so
        # the CXS location also feeds the non-US/US-signal snippet checks. Skip
        # in --no-scrape (markdown-less by design) and --no-workday-enrich.
        if (
            not args.no_scrape
            and not args.no_workday_enrich
            and "myworkdayjobs.com" in url.lower()
        ):
            if wd_session is None:
                from scripts.ats_platform_filter.workday_enrich import make_workday_session
                wd_session = make_workday_session()
            if enrich_workday_result(item, session=wd_session):
                record["workday_enriched"] += 1

        # Resolve Workable's client-side location via its public JSON API
        # (its country is absent from the scraped markdown, so a non-US-only
        # "Remote" posting otherwise passes every gate). Authoritative drop —
        # not a snippet heuristic. Skip in --no-scrape / --no-workable-enrich.
        workable_drop = None
        if (
            not args.no_scrape
            and not args.no_workable_enrich
            and "apply.workable.com" in url.lower()
        ):
            if wk_session is None:
                from scripts.ats_platform_filter.workable_enrich import make_workable_session
                wk_session = make_workable_session()
            workable_drop = enrich_workable_result(item, session=wk_session)
            if workable_drop:
                record["workable_dropped"] += 1

        if workable_drop:
            keep, reason = False, workable_drop
        else:
            keep, reason = filter_result(item, excluded, remote_mode)
        # Content-quality gate: drop dead/expired/un-rendered pages with no
        # scoreable JD. Only when markdown was actually scraped (skip in
        # --no-scrape, where every result is markdown-less by design).
        if keep and not args.no_scrape:
            health = listing_health(item)
            if health:
                keep, reason = False, health
        if keep:
            annotated = _annotate_kept(item, query, args.max_markdown_chars)
            kept_items.append(annotated)
            record["kept_by_domain"][domain] += 1
            record["kept_by_role"][role] += 1
        else:
            discarded.append({"url": url, "title": item.get("title", ""), "reason": reason})
            by_reason[reason] = by_reason.get(reason, 0) + 1

    record["kept"] = len(kept_items)
    record["discarded"] = len(discarded)
    record["by_reason"] = by_reason
    record["kept_items"] = kept_items

    # Per-query filtered file (debug + --no-llm-review-style inspection).
    filtered = {
        "search_id": record["search_id"],
        "query_number": qn,
        "tier": query.tier,
        "board_label": query.board_label,
        "stats": {
            "input_count": len(results),
            "kept_count": len(kept_items),
            "discarded_count": len(discarded),
            "by_reason": by_reason,
        },
        "kept": kept_items,
        "discarded": discarded,
    }
    (cache_dir / f"q{qn:02d}_filtered.json").write_text(json.dumps(filtered, indent=2), encoding="utf-8")
    return record


def run(args: argparse.Namespace) -> int:
    cfg = load_config(CONFIG_DIR / "config.yml")
    loc_cfg = LocationConfig.from_dict(cfg)
    excluded = load_excluded_companies(str(CONFIG_DIR / "exclusions.yml"))
    remote_mode = loc_cfg.remote

    # Resolve time filter.
    if not args.tbs:
        from scripts.firecrawl_tbs import tbs_for_window
        window = args.time_window or (cfg.get("search_config") or {}).get("time_filter") or "past_week"
        try:
            args.tbs = tbs_for_window(window)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2

    if args.search_limit is None:
        args.search_limit = int((cfg.get("search_config") or {}).get("search_limit") or 25)

    # Build + filter the queue to the requested tier.
    full_queue = qb.build_queue(cfg, loc_cfg)
    queue = [q for q in full_queue if q.tier == args.tier]
    if args.boards:
        wanted = {b.lower() for b in args.boards}
        queue = [q for q in queue if any(d.lower() in wanted for d in q.bundled_domains)]
    if args.max_queries:
        queue = queue[: args.max_queries]

    if not queue:
        print(f"No queries for tier '{args.tier}' (check config.yml target_roles/job_boards).", file=sys.stderr)
        return 1

    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"ats-platform-search [{args.tier}]: {len(queue)} queries | "
        f"limit={args.search_limit} | tbs={args.tbs} | mode={loc_cfg.describe()} | "
        f"concurrency={args.concurrency}"
    )
    if args.dry_run:
        for q in queue:
            print(f"  q{q.query_number:02d} [{q.board_label}] {qb.build_query_string(q, loc_cfg)}")
        return 0

    client = FirecrawlClient(timeout=args.timeout)

    # Fan out searches (network-bound HTTP; ThreadPoolExecutor matches the
    # house pattern in scripts/ats_scraper/cli.py — NOT an asyncio reimpl of
    # the agent SDK's fan-out, which the offload strategy warns against).
    records: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futures = [
            pool.submit(_process_query, q, client, loc_cfg, excluded, remote_mode, cache_dir, args)
            for q in queue
        ]
        for fut in concurrent.futures.as_completed(futures):
            records.append(fut.result())

    records.sort(key=lambda r: r["query_number"])

    # ---- Aggregate ----
    by_board: dict[str, dict] = defaultdict(lambda: {"queries": 0, "found": 0, "kept": 0})
    by_role: dict[str, dict] = defaultdict(lambda: {"found": 0, "kept": 0})
    totals = {"input": 0, "kept": 0, "discarded": 0, "workday_enriched": 0,
              "workable_dropped": 0, "by_reason": defaultdict(int)}
    feedback = {"refunded": 0, "failed": 0, "credits_refunded": 0, "daily_cap_reached": False,
                "credits_refunded_today": None}
    errors: list[str] = []

    all_kept: list[dict] = []
    for rec in records:
        totals["input"] += rec["results_found"]
        totals["kept"] += rec["kept"]
        totals["discarded"] += rec["discarded"]
        totals["workday_enriched"] += rec.get("workday_enriched", 0)
        totals["workable_dropped"] += rec.get("workable_dropped", 0)
        for reason, count in rec["by_reason"].items():
            totals["by_reason"][reason] += count
        for domain in rec["bundled_domains"]:
            by_board[domain]["queries"] += 1
        for domain, n in rec["found_by_domain"].items():
            by_board[domain]["found"] += n
        for domain, n in rec["kept_by_domain"].items():
            by_board[domain]["kept"] += n
        for role, n in rec["found_by_role"].items():
            by_role[role]["found"] += n
        for role, n in rec["kept_by_role"].items():
            by_role[role]["kept"] += n
        rf = rec["refund"]
        if rf.get("status") == "ok":
            feedback["refunded"] += 1
            feedback["credits_refunded"] += rf.get("credits_refunded") or 0
            if rf.get("credits_refunded_today") is not None:
                feedback["credits_refunded_today"] = rf["credits_refunded_today"]
            cap = rf.get("daily_refund_cap")
            today = rf.get("credits_refunded_today")
            if cap and today and today >= cap:
                feedback["daily_cap_reached"] = True
        elif rf.get("status") == "failed":
            feedback["failed"] += 1
        if rec["error"]:
            errors.append(f"q{rec['query_number']:02d} [{rec['board_label']}]: {rec['error']}")
        all_kept.extend(rec["kept_items"])

    # ---- Stage review batches (markdown lives here; orchestrator never reads them) ----
    # Default (--review-batch-size 0): ALL kept go in ONE batch → the orchestrator
    # dispatches a SINGLE review subagent (reads the scoring configs once, not
    # once-per-batch). Set N>0 only to split an unusually large run across subagents.
    if args.review_batch_size and args.review_batch_size > 0:
        batch_size = args.review_batch_size
    else:
        batch_size = max(1, len(all_kept))
    batch_paths: list[str] = []
    for i in range(0, len(all_kept), batch_size):
        b = i // batch_size + 1
        path = cache_dir / f"review_batch_{args.tier}_{b:02d}.json"
        path.write_text(json.dumps(all_kept[i : i + batch_size], indent=2), encoding="utf-8")
        batch_paths.append(str(path))

    summary = {
        "tier": args.tier,
        "generated_date": date.today().isoformat(),
        "time_filter": args.tbs,
        "search_limit": args.search_limit,
        "location_mode": loc_cfg.describe(),
        "query_count": len(queue),
        "queries": [
            {k: rec[k] for k in (
                "query_number", "board_label", "bundled_domains", "roles",
                "search_id", "credits_used", "results_found", "kept", "discarded",
                "by_reason", "refund", "error",
            )}
            for rec in records
        ],
        "totals": {
            "input": totals["input"],
            "kept": totals["kept"],
            "discarded": totals["discarded"],
            "workday_enriched": totals["workday_enriched"],
            "workable_dropped": totals["workable_dropped"],
            "by_reason": dict(totals["by_reason"]),
        },
        "by_board": {d: v for d, v in sorted(by_board.items())},
        "by_role": {r: v for r, v in sorted(by_role.items())},
        "review_batches": batch_paths,
        "feedback": feedback,
        "errors": errors,
    }
    summary_path = cache_dir / f"search_summary_{args.tier}.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # ---- Human-readable stdout ----
    reason_str = ", ".join(f"{k}={v}" for k, v in sorted(totals["by_reason"].items())) or "none"
    print(
        f"Search [{args.tier}]: {totals['input']} found → {totals['kept']} kept / "
        f"{totals['discarded']} discarded | {reason_str}"
    )
    if totals["workday_enriched"]:
        print(f"Workday CXS enrich: {totals['workday_enriched']} description(s) backfilled")
    if totals["workable_dropped"]:
        print(f"Workable location enrich: {totals['workable_dropped']} non-US posting(s) dropped")
    print(
        f"Refunds: {feedback['refunded']} ok ({feedback['credits_refunded']} credits), "
        f"{feedback['failed']} failed"
        + (" | DAILY CAP REACHED" if feedback["daily_cap_reached"] else "")
    )
    print(f"Review batches: {len(batch_paths)} (size {batch_size}) → {len(all_kept)} kept items")
    print(f"Summary: {summary_path}")
    if errors:
        print(f"Query errors ({len(errors)}):", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Python-driven Firecrawl ATS platform search (Option A)")
    p.add_argument("--tier", choices=["primary", "secondary"], required=True,
                   help="Role tier to execute (primary roles first, secondary only if target unmet).")
    p.add_argument("--time-window", default=None,
                   help="past_day|past_2_days|past_week|past_month|past_year (default: config time_filter)")
    p.add_argument("--tbs", default=None, help="Raw Google tbs string override (bypasses --time-window).")
    p.add_argument("--search-limit", type=int, default=None, help="Results per query (default: config).")
    p.add_argument("--concurrency", type=int, default=4, help="Parallel searches (default: 4).")
    p.add_argument("--review-batch-size", type=int, default=0,
                   help="Kept items per review batch file (0 = single batch / one subagent, the default).")
    p.add_argument("--max-markdown-chars", type=int, default=0,
                   help="Truncate each kept description_full to N chars (0 = unlimited).")
    p.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR), help="Output directory.")
    p.add_argument("--timeout", type=int, default=180, help="Per-request HTTP timeout (s).")
    p.add_argument("--no-feedback", action="store_true", help="Skip the credit-refund feedback call.")
    p.add_argument("--no-scrape", action="store_true", help="Drop scrapeOptions (cheap, markdown-less).")
    p.add_argument("--no-workday-enrich", action="store_true",
                   help="Skip the Workday CXS description backfill (testing).")
    p.add_argument("--no-workable-enrich", action="store_true",
                   help="Skip the Workable JSON location resolution (testing).")
    p.add_argument("--boards", nargs="+", default=None, help="Only run queries covering these domains.")
    p.add_argument("--max-queries", type=int, default=None, help="Only run the first N queries of the tier.")
    p.add_argument("--dry-run", action="store_true", help="Print the queries that would run; make no calls.")
    args = p.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
