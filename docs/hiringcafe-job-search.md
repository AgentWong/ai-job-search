# Hiring Cafe Job Search Workflow

**Prompt file:** `.github/prompts/hiringcafe-job-search.prompt.md`
**Agent:** `hiringcafe-job-search` (via Chrome DevTools MCP)

## What It Does

Searches [Hiring Cafe](https://hiring.cafe) using browser automation, parsing AI-enriched metadata cards that include title, company, salary, years of experience, tech tools, and requirements summaries. Qualified results are added to `results/application_queue.csv`.

## Prerequisites

- Google Chrome installed
- Chrome DevTools MCP configured in `.mcp.json` (included by default)

## How to Run

1. **Start Chrome with remote debugging:**
   ```bash
   ./scripts/start-chrome-debug.sh
   ```

2. Open VS Code with Copilot enabled

3. Run the `/hiringcafe-job-search` prompt

4. Watch the AI navigate the browser and parse results

## How It Works

This workflow uses a **single-phase agent** pattern (unlike the multi-phase Firecrawl workflows). This is possible because Hiring Cafe's search cards display all the metadata needed for scoring without visiting individual job detail pages:

- Job title, company name, salary range
- Years of experience required
- Tech tools and stack
- Requirements summary
- URL-based filter state (no UI form interaction needed)
- No login required

The agent navigates to Hiring Cafe with filter parameters encoded in the URL, reads the search result cards, scores each position, and returns structured JSON.

## Customization

The default filters balance result volume with relevance. They filter for things that are non-negotiable (e.g., Remote, no startups, no Top Secret clearance) without being so restrictive that good results get excluded.

If the default filtering produces poor results, you can ask Claude to explore the website for different filter combinations and evaluate what works better for your search criteria.

## Tips

- **Observe the browser:** Since this uses Chrome DevTools, you can watch the AI interact with the page in real time. This is helpful for debugging filter issues.
- **Filter tuning:** If results are too broad or too narrow, adjust the URL filter parameters in the agent file. The filters are encoded as URL query parameters.
- **Complementary workflow:** Hiring Cafe aggregates from many sources, so there may be overlap with `/ats-platform-search` results. The orchestrator handles deduplication automatically.

## Related

- [ATS Platform Search](ats-platform-search.md) -- ATS platform search (complementary)
- [Company Monitoring](company-monitoring.md) -- Direct career page monitoring (complementary)
