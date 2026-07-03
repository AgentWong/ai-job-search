"""Python-driven Firecrawl ATS platform VALIDATION.

A reachability probe for candidate ATS / job-board domains discovered via Claude
Desktop Research Mode (`claude_desktop/ats_platform_curation/candidates.yml`),
run before a domain is added to `config/config.yml`.

It shares the exact Firecrawl API path as `scripts.ats_platform_search` (direct
`/v2/search` + 1-credit feedback refund — no MCP server), and reuses the same
regex pre-filter and query builder. The differences are scope, not mechanism:

    1. One query per CANDIDATE domain (read from candidates.yml), not per
       config.yml board tier.
    2. Hardcoded validation params — limit 10, past month — overridable.
    3. Primary roles only (secondary roles add noise to the validation signal).
    4. NO queue write, NO review batches, NO effectiveness tracking. Each
       candidate is classified PASS_STRONG / PASS_WEAK / MARGINAL / FAIL_EMPTY /
       FAIL_ERROR from its raw-hit and qualified counts.

The raw Firecrawl payload is written verbatim to q{NN}_raw.json and never enters
an LLM context; the orchestrator reads only the small JSON summary.
"""
