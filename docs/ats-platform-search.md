# ATS Platform Search Workflow

**Prompt file:** `.github/prompts/ats-platform-search.prompt.md`
**Agent:** `firecrawl-job-search` (via Firecrawl MCP)

## What It Does

Searches across multiple ATS platforms for open positions matching your target roles, scores them, and adds qualified results to `results/application_queue.csv`. This is typically the highest-volume discovery workflow.

## How to Run

1. Open VS Code with Copilot enabled
2. Run the `/ats-platform-search` prompt

The orchestrator reads `config/inclusions.yml` to determine which ATS platforms to search and which role titles to look for, then dispatches Firecrawl agents for each platform + role combination.

## Configuration

### Search Parameters (`config/inclusions.yml`)

The key settings to tune:

- **`google_time_filter`** -- Controls how far back to search
  - `"qdr:d"` -- Past 24 hours (good for daily runs, lower API credit usage)
  - `"qdr:w"` -- Past week (good for weekly runs, higher API credit usage)

- **`search_limit`** -- Results per search query
  - `10` -- Conservative, good for daily runs with `qdr:d`
  - `25` -- More results, good for weekly runs with `qdr:w` (uses more Firecrawl credits)

- **`target_roles`** -- Role titles to search for, split into primary (always searched) and secondary (searched if primary yields insufficient results)

- **`job_boards`** -- ATS platform domains to search against

### Balancing Coverage vs. Cost

| Cadence | Time Filter | Search Limit | Approximate Credit Usage |
|---------|-------------|-------------|------------------------|
| Daily | `qdr:d` | 10 | Lower |
| Weekly | `qdr:w` | 25 | Higher |

If you want more results, increase both the time window and the search limit together. Using `qdr:w` with `search_limit: 10` may miss results; using `qdr:d` with `search_limit: 25` wastes credits on a small result pool.

## Tips

- **Adjust incrementally:** Start with the default daily settings. If you're missing good positions, try weekly runs with higher limits for a cycle, then dial back.
- **Monitor credit usage:** Each search query consumes Firecrawl credits. With 8 ATS platforms and 7 role titles, a full run is up to 56 searches (though secondary roles may be skipped if the target position count is reached).
- **Exclusions matter:** Keep `config/exclusions.yml` updated with companies you've already applied to. This prevents wasting time re-scoring positions you've already seen.

## Related

- [Hiring Cafe Search](hiringcafe-job-search.md) -- Complementary browser-based search
- [Company Monitoring](company-monitoring.md) -- Direct career page monitoring
