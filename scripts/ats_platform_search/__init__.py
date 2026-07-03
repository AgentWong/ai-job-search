"""Python-driven Firecrawl ATS platform search (Option A).

This package replaces the LLM-in-the-data-path search that the
`firecrawl-job-search` subagent used to perform for Task Type 1. Python now
owns the deterministic half of the workflow end-to-end:

    1. Build the query queue from config/config.yml (boards + roles + location).
    2. Call Firecrawl /v2/search directly (scrapeOptions preserved — identical
       2cr/10 credit cost as the old MCP call).
    3. Write q{NN}_raw.json verbatim (never touches an LLM context).
    4. Submit the 1-credit refund via /v2/search/{id}/feedback.
    5. Run the existing regex pre-filter (scripts.ats_platform_filter.filters).
    6. Stage kept results (with full markdown + deterministic board/role
       attribution) into review batches for the ats-platform-review subagent.

See docs/ats-platform-search-token-regression-assessment.md "Option A".
"""
