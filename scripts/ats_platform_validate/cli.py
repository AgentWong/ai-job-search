"""Python-driven Firecrawl ATS platform validation — CLI.

Validate candidate ATS / job-board domains (from candidates.yml) against live
Firecrawl results before they're added to config/config.yml. Same direct
`/v2/search` API path as scripts.ats_platform_search (no MCP), but one query per
candidate domain with hardcoded validation params, and a pass/fail verdict per
candidate instead of a queue write.

Usage:
    .venv/bin/python -m scripts.ats_platform_validate.cli
    .venv/bin/python -m scripts.ats_platform_validate.cli \
        --candidates claude_desktop/ats_platform_curation/candidates.yml

Common options:
    --candidates PATH      candidates.yml path (default: the curation file).
    --time-window WINDOW   past_day|past_2_days|past_week|past_month|past_year
                           (default: past_month — the validation sample window).
    --search-limit N       Results per candidate (default: 10).
    --concurrency N        Parallel searches (default: 4).
    --no-feedback          Skip the credit-refund feedback call (testing).
    --no-scrape            Drop scrapeOptions — cheap, markdown-less (testing;
                           disables the qualified-count health gate).
    --dry-run              Print the queries that would run; make no calls.

Outputs (under --cache-dir, default results/ats_platform_validation_cache/):
    q{NN}_raw.json                 Verbatim Firecrawl response (debug; never read by an LLM).
    validation_summary.json        Small manifest the orchestrator reads (no markdown).

Stdout: a human-readable summary; the orchestrator parses validation_summary.json.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import yaml

from scripts.ats_scraper.config import load_config
from scripts.ats_scraper.location import LocationConfig
from scripts.ats_platform_filter.filters import (
    filter_result,
    listing_health,
    load_excluded_companies,
)
from scripts.ats_platform_search.firecrawl_client import FirecrawlClient, FirecrawlError
from scripts.ats_platform_search import query_builder as qb

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
DEFAULT_CANDIDATES = REPO_ROOT / "claude_desktop" / "ats_platform_curation" / "candidates.yml"
DEFAULT_CACHE_DIR = REPO_ROOT / "results" / "ats_platform_validation_cache"

# Validation defaults — a small past-month sample is enough to prove a platform
# is Google-indexable and reachable via Firecrawl. Overridable via flags.
DEFAULT_WINDOW = "past_month"
DEFAULT_SEARCH_LIMIT = 10


def _normalize_base(domain: str) -> str:
    """Lowercase + strip a leading wildcard ('*.foo.com' -> 'foo.com')."""
    d = (domain or "").strip().lower()
    return d[2:] if d.startswith("*.") else d


def _web_results(resp: dict) -> list[dict]:
    """Extract the result list from a /v2/search response (data.web)."""
    data = resp.get("data") if isinstance(resp, dict) else None
    if isinstance(data, dict):
        return list(data.get("web") or [])
    if isinstance(data, list):  # defensive: alternate shape
        return list(data)
    return []


def _covered_bases(cfg: dict) -> list[str]:
    """Normalized domains already in config.yml job_boards (primary+watch+secondary)."""
    boards = (cfg or {}).get("job_boards") or {}
    bases: list[str] = []
    for tier in ("primary", "watch", "secondary"):
        for entry in boards.get(tier) or []:
            domain = entry.get("domain") if isinstance(entry, dict) else entry
            if domain:
                bases.append(_normalize_base(domain))
    return bases


def _covered_match(cand_base: str, covered: list[str]) -> str | None:
    """Return the covering config.yml entry for cand_base, else None.

    Wildcard-aware: a candidate subdomain (foo.applytojob.com) is covered by a
    base entry (applytojob.com, from '*.applytojob.com').
    """
    for base in covered:
        if cand_base == base or cand_base.endswith("." + base):
            return base
    return None


def _primary_roles(cfg: dict) -> list[str]:
    roles = ((cfg or {}).get("target_roles") or {}).get("primary") or []
    out: list[str] = []
    for entry in roles:
        name = entry.get("name") if isinstance(entry, dict) else entry
        if name:
            out.append(name.strip())
    return out


def _classify(results_found: int, qualified: int, error: str | None) -> str:
    if error:
        return "FAIL_ERROR"
    if results_found >= 5 and qualified >= 1:
        return "PASS_STRONG"
    if results_found >= 5:
        return "PASS_WEAK"
    if results_found >= 1:
        return "MARGINAL"
    return "FAIL_EMPTY"


def _process_candidate(
    cand: dict,
    query_number: int,
    roles: list[str],
    client: FirecrawlClient,
    loc_cfg: LocationConfig,
    excluded: set,
    tbs: str,
    cache_dir: Path,
    args: argparse.Namespace,
) -> dict:
    """Search one candidate domain, write raw, refund, classify. Never raises."""
    base = _normalize_base(cand["domain"])
    query = qb.Query(query_number, "primary", roles, cand["domain"], [base])
    query_string = qb.build_query_string(query, loc_cfg)

    record: dict = {
        "domain": cand["domain"],
        "vendor": cand.get("vendor", ""),
        "vendor_variant": bool(cand.get("vendor_variant", False)),
        "scrapability": cand.get("scrapability", ""),
        "notes": cand.get("notes", ""),
        "query_number": query_number,
        "query_string": query_string,
        "search_id": None,
        "credits_used": None,
        "results_found": 0,
        "qualified_count": 0,
        "by_reason": {},
        "sample_qualified_urls": [],
        "refund": {"status": "skipped"},
        "verdict": None,
        "error": None,
    }

    try:
        resp = client.search(
            query_string,
            limit=args.search_limit,
            tbs=tbs,
            location=qb.search_location(loc_cfg),
            scrape_markdown=not args.no_scrape,
        )
    except FirecrawlError as exc:
        record["error"] = str(exc)
        record["verdict"] = _classify(0, 0, record["error"])
        (cache_dir / f"q{query_number:02d}_raw.json").write_text(
            json.dumps({"error": str(exc)}, indent=2), encoding="utf-8"
        )
        return record

    record["search_id"] = resp.get("id")
    record["credits_used"] = resp.get("creditsUsed")
    (cache_dir / f"q{query_number:02d}_raw.json").write_text(
        json.dumps(resp, indent=2), encoding="utf-8"
    )

    results = _web_results(resp)
    record["results_found"] = len(results)

    # Refund 1 credit — same visible-success/failure contract as the search CLI.
    if not args.no_feedback and record["search_id"]:
        try:
            if results:
                fb = client.submit_feedback(
                    record["search_id"],
                    valuable_urls=[r.get("url", "") for r in results[:5]],
                )
            else:
                topic = f"US-remote {'/'.join(roles[:3])} roles on {cand['domain']}"
                fb = client.submit_feedback(record["search_id"], missing_topic=topic)
            record["refund"] = {
                "status": "ok",
                "credits_refunded": fb.get("creditsRefunded"),
                "credits_refunded_today": fb.get("creditsRefundedToday"),
                "daily_refund_cap": fb.get("dailyRefundCap"),
            }
        except FirecrawlError as exc:
            record["refund"] = {"status": "failed", "error": str(exc)}

    # Regex pre-filter for the bonus qualified signal (results_found is primary).
    by_reason: Counter = Counter()
    sample: list[str] = []
    for item in results:
        keep, reason = filter_result(item, excluded, loc_cfg.remote)
        if keep and not args.no_scrape:
            health = listing_health(item)
            if health:
                keep, reason = False, health
        if keep:
            record["qualified_count"] += 1
            if len(sample) < 3:
                sample.append(item.get("url", "") or "")
        else:
            by_reason[reason] += 1

    record["by_reason"] = dict(by_reason)
    record["sample_qualified_urls"] = sample
    record["verdict"] = _classify(record["results_found"], record["qualified_count"], None)
    return record


def run(args: argparse.Namespace) -> int:
    candidates_path = Path(args.candidates)
    if not candidates_path.exists():
        print(
            "Candidates file missing: "
            f"{candidates_path}\nRun Claude Desktop Research Mode with "
            "claude_desktop/ats_platform_curation/project_instructions.md first, "
            "then save its YAML output to that path.",
            file=sys.stderr,
        )
        return 2

    try:
        data = yaml.safe_load(candidates_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        print(f"Could not parse candidates YAML: {exc}", file=sys.stderr)
        return 2
    candidates = [c for c in (data.get("candidates") or []) if c.get("domain")]
    if not candidates:
        print(f"No candidates with a 'domain' field in {candidates_path}", file=sys.stderr)
        return 2

    cfg = load_config(CONFIG_DIR / "config.yml")
    loc_cfg = LocationConfig.from_dict(cfg)
    excluded = load_excluded_companies(str(CONFIG_DIR / "exclusions.yml"))
    roles = _primary_roles(cfg)
    if not roles:
        print("No primary target_roles in config.yml — nothing to validate.", file=sys.stderr)
        return 2

    # Filter candidates against the already-covered set.
    covered = _covered_bases(cfg)
    to_validate: list[dict] = []
    skipped: list[dict] = []
    for cand in candidates:
        base = _normalize_base(cand["domain"])
        match = _covered_match(base, covered)
        if match and not cand.get("vendor_variant", False):
            skipped.append({
                "domain": cand["domain"],
                "vendor": cand.get("vendor", ""),
                "matched_entry": match,
            })
        else:
            to_validate.append(cand)

    if not to_validate:
        print(
            f"All {len(candidates)} candidate(s) already covered by config.yml — nothing to validate.",
            file=sys.stderr,
        )
        # Still write a summary so the orchestrator can report the skips.

    try:
        from scripts.firecrawl_tbs import tbs_for_window
        tbs = tbs_for_window(args.time_window)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    role_terms = "(" + " OR ".join(f'"{r}"' for r in roles) + ")"
    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"ats-platform-validate: {len(to_validate)} candidate(s) "
        f"({len(skipped)} skipped already-covered) | limit={args.search_limit} | "
        f"tbs={tbs} | mode={loc_cfg.describe()} | concurrency={args.concurrency}"
    )
    if args.dry_run:
        for i, cand in enumerate(to_validate, start=1):
            base = _normalize_base(cand["domain"])
            q = qb.Query(i, "primary", roles, cand["domain"], [base])
            print(f"  q{i:02d} [{cand['domain']}] {qb.build_query_string(q, loc_cfg)}")
        return 0

    client = FirecrawlClient(timeout=args.timeout)
    records: list[dict] = []
    if to_validate:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
            futures = {
                pool.submit(
                    _process_candidate, cand, i, roles, client, loc_cfg,
                    excluded, tbs, cache_dir, args,
                ): i
                for i, cand in enumerate(to_validate, start=1)
            }
            for fut in concurrent.futures.as_completed(futures):
                records.append(fut.result())
        records.sort(key=lambda r: r["query_number"])

    # ---- Aggregate ----
    verdict_counts: Counter = Counter(r["verdict"] for r in records)
    feedback = {"refunded": 0, "failed": 0, "credits_refunded": 0,
                "daily_cap_reached": False, "credits_refunded_today": None}
    errors: list[str] = []
    for rec in records:
        rf = rec["refund"]
        if rf.get("status") == "ok":
            feedback["refunded"] += 1
            feedback["credits_refunded"] += rf.get("credits_refunded") or 0
            if rf.get("credits_refunded_today") is not None:
                feedback["credits_refunded_today"] = rf["credits_refunded_today"]
            cap, today = rf.get("daily_refund_cap"), rf.get("credits_refunded_today")
            if cap and today and today >= cap:
                feedback["daily_cap_reached"] = True
        elif rf.get("status") == "failed":
            feedback["failed"] += 1
        if rec["error"]:
            errors.append(f"q{rec['query_number']:02d} [{rec['domain']}]: {rec['error']}")

    summary = {
        "generated_date": date.today().isoformat(),
        "candidates_file": str(candidates_path),
        "time_filter": tbs,
        "time_window": args.time_window,
        "search_limit": args.search_limit,
        "location_mode": loc_cfg.describe(),
        "role_terms": role_terms,
        "loaded": len(candidates),
        "skipped_already_covered": skipped,
        "validated_count": len(records),
        "verdict_counts": {
            v: verdict_counts.get(v, 0)
            for v in ("PASS_STRONG", "PASS_WEAK", "MARGINAL", "FAIL_EMPTY", "FAIL_ERROR")
        },
        "feedback": feedback,
        "candidates": [
            {k: rec[k] for k in (
                "domain", "vendor", "vendor_variant", "scrapability", "notes",
                "query_number", "search_id", "credits_used", "results_found",
                "qualified_count", "by_reason", "sample_qualified_urls",
                "refund", "verdict", "error",
            )}
            for rec in records
        ],
        "errors": errors,
    }
    summary_path = cache_dir / "validation_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # ---- Human-readable stdout ----
    vc = summary["verdict_counts"]
    print(
        f"Verdicts: PASS_STRONG={vc['PASS_STRONG']} PASS_WEAK={vc['PASS_WEAK']} "
        f"MARGINAL={vc['MARGINAL']} FAIL_EMPTY={vc['FAIL_EMPTY']} FAIL_ERROR={vc['FAIL_ERROR']}"
    )
    print(
        f"Refunds: {feedback['refunded']} ok ({feedback['credits_refunded']} credits), "
        f"{feedback['failed']} failed"
        + (" | DAILY CAP REACHED" if feedback["daily_cap_reached"] else "")
    )
    print(f"Summary: {summary_path}")
    if errors:
        print(f"Candidate errors ({len(errors)}):", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Python-driven Firecrawl ATS platform validation")
    p.add_argument("--candidates", default=str(DEFAULT_CANDIDATES),
                   help="candidates.yml path (default: the curation file).")
    p.add_argument("--time-window", default=DEFAULT_WINDOW,
                   help="past_day|past_2_days|past_week|past_month|past_year (default: past_month).")
    p.add_argument("--search-limit", type=int, default=DEFAULT_SEARCH_LIMIT,
                   help="Results per candidate (default: 10).")
    p.add_argument("--concurrency", type=int, default=4, help="Parallel searches (default: 4).")
    p.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR), help="Output directory.")
    p.add_argument("--timeout", type=int, default=180, help="Per-request HTTP timeout (s).")
    p.add_argument("--no-feedback", action="store_true", help="Skip the credit-refund feedback call.")
    p.add_argument("--no-scrape", action="store_true",
                   help="Drop scrapeOptions (cheap, markdown-less; disables the health gate).")
    p.add_argument("--dry-run", action="store_true",
                   help="Print the queries that would run; make no calls.")
    args = p.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
