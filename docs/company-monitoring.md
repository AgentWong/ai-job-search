# Company Monitoring Workflow

**Prompt file:** `.github/prompts/company-monitoring.prompt.md`
**Agent:** `firecrawl-job-search` (via Firecrawl MCP)

## What It Does

Scrapes career pages of your curated company list (`config/company_targets.csv`) to find new job openings. Each company's career page is checked for positions matching your role preferences, scored, and qualified results are added to `results/application_queue.csv`.

## When to Use

Run this on a regular basis (daily or weekly) after you've built a company targets list using the [Company Curation](company-curation.md) workflow. This catches positions that may not appear on ATS platform searches -- particularly companies that host their own career pages.

## How to Run

1. Ensure `config/company_targets.csv` has active companies (see [Company Curation](company-curation.md))
2. Open VS Code with Copilot enabled
3. Run the `/company-monitoring` prompt

## How It Works

The orchestrator reads your company targets CSV and sends each active company's career URL to the Firecrawl agent for scraping. The agent:

1. Scrapes the career page
2. Filters positions against your role preferences and exclusions
3. Scores each position using `shared/scoring_framework.md`
4. Returns structured JSON results

The orchestrator aggregates all results, deduplicates against existing entries in `results/application_queue.csv`, and appends new qualified positions.

## Evaluation Rules

Companies and positions are filtered using `shared/company_evaluation_rules.md`. Common reasons a company or position gets filtered out:

- Excessive outsourcing indicators
- Non-US positions (when targeting US remote)
- On-premise-only infrastructure
- Company size or industry mismatches

Customize these rules in `shared/company_evaluation_rules.md` to match your own criteria.

## Tips

- **Run frequency:** Weekly is a good cadence for most job searches. Daily if you're actively searching and want to catch new postings quickly.
- **Maintain your list:** After each run, review the validation report for URL issues (redirects, 404s, auth walls). See [Company Targets Maintenance](company_targets_maintenance.md) for the full maintenance process.
- **Complement with ATS search:** This workflow finds positions on direct career pages. Use `/ats-platform-search` in parallel to cover ATS platforms (Greenhouse, Lever, etc.).

## Related

- [Company Curation](company-curation.md) -- Build the company list this workflow uses
- [Company Targets Maintenance](company_targets_maintenance.md) -- Maintain the CSV over time
- [ATS Platform Search](ats-platform-search.md) -- Search ATS platforms for broader coverage
