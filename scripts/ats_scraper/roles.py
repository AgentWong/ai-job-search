"""Shared target_roles tier selection for the job-search scrapers.

config.yml `target_roles` has three buckets:

    primary, secondary  — always searched, in that order.
    local_only          — high-noise generalist titles (Systems Administrator,
                          Systems Engineer, ...) that flood remote searches with
                          non-remote / non-matching results. Searched ONLY in
                          local mode (location.remote: false); skipped entirely
                          in remote mode.

`active_role_buckets` is the single source of truth for "which buckets does a
search run cover, given the location mode". The deterministic per-role scrapers
(ats_scraper, builtin_scraper, linkedin_scraper) iterate it directly. The
bundled-query Firecrawl builder (ats_platform_search.query_builder) instead
folds the local_only roles into its `secondary` OR-group — see build_queue.
"""

from __future__ import annotations

from scripts.ats_scraper.location import LocationConfig


def active_role_buckets(loc_cfg: LocationConfig) -> tuple[str, ...]:
    """target_roles buckets to search, in priority order.

    `local_only` is appended only in local mode (location.remote: false); in
    remote mode these high-noise generalist titles are skipped entirely.
    """
    if loc_cfg.remote:
        return ("primary", "secondary")
    return ("primary", "secondary", "local_only")
