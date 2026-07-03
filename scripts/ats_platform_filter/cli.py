"""CLI for Firecrawl ATS platform search pre-filter.

Usage:
    .venv/bin/python -m scripts.ats_platform_filter.cli \
        --input  results/ats_platform_cache/q01_raw.json \
        --output results/ats_platform_cache/q01_filtered.json

Output JSON shape:
    {
      "search_id": "...",        # forwarded from raw file for feedback call
      "stats": {
        "input_count": N,
        "kept_count": K,
        "discarded_count": D,
        "by_reason": { "senior_title": 4, ... }
      },
      "kept":      [ {url, title, description, ...}, ... ],
      "discarded": [ {url, title, reason},            ... ]
    }

Stdout: single summary line for the orchestrator's batch log.
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

from .filters import filter_result, load_excluded_companies


def _load_remote_mode(config_path: str = "config/config.yml") -> bool:
    """Read location.remote from config/config.yml (defaults True)."""
    try:
        with open(config_path) as f:
            data = yaml.safe_load(f)
        return bool((data or {}).get("location", {}).get("remote", True))
    except (FileNotFoundError, yaml.YAMLError):
        return True


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Deterministic pre-filter for Firecrawl ATS platform search results"
    )
    parser.add_argument("--input",      required=True, help="Raw search results JSON from firecrawl_search")
    parser.add_argument("--output",     required=True, help="Path to write filtered results JSON")
    parser.add_argument("--exclusions", default="config/exclusions.yml")
    parser.add_argument("--config",     default="config/config.yml")
    args = parser.parse_args(argv)

    excluded_companies = load_excluded_companies(args.exclusions)
    remote_mode = _load_remote_mode(args.config)

    try:
        with open(args.input) as f:
            raw = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read {args.input}: {exc}", file=sys.stderr)
        sys.exit(1)

    # Normalise across the shapes this file can hold:
    #   - bare list:                    [ {...}, ... ]
    #   - legacy MCP-returned:          {"results": [...], "id": "..."}
    #   - Firecrawl /v2/search verbatim: {"data": {"web": [...]}, "id": "..."}
    #     (what scripts.ats_platform_search.cli writes to q{NN}_raw.json)
    if isinstance(raw, list):
        results = raw
        search_id = None
    else:
        data = raw.get("data")
        if isinstance(data, dict):
            results = data.get("web", [])
        elif isinstance(data, list):
            results = raw.get("results", data)
        else:
            results = raw.get("results", [])
        search_id = raw.get("id")

    kept = []
    discarded = []
    by_reason: dict = {}

    for item in results:
        keep, reason = filter_result(item, excluded_companies, remote_mode)
        if keep:
            kept.append(item)
        else:
            discarded.append({
                "url":    item.get("url", ""),
                "title":  item.get("title", ""),
                "reason": reason,
            })
            by_reason[reason] = by_reason.get(reason, 0) + 1

    output = {
        "search_id": search_id,
        "stats": {
            "input_count":     len(results),
            "kept_count":      len(kept),
            "discarded_count": len(discarded),
            "by_reason":       by_reason,
        },
        "kept":      kept,
        "discarded": discarded,
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    reason_str = ", ".join(f"{k}={v}" for k, v in by_reason.items()) or "none"
    print(
        f"Pre-filter: {len(results)} in → {len(kept)} kept / {len(discarded)} discarded"
        f" | {reason_str}"
    )


if __name__ == "__main__":
    main()
