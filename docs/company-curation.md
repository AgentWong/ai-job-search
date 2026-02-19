# Company Curation Workflow

**Prompt file:** `.github/prompts/company-curation.prompt.md`
**Agent:** `firecrawl-job-search` (via Firecrawl MCP)

## What It Does

Discovers and evaluates companies you might want to monitor directly for job openings, then writes them to `config/company_targets.csv`. This is the starting point for building your company monitoring list.

## When to Use

Run this when you want to build or expand your list of target companies. For example, if you're interested in specific industries or types of companies (SaaS, observability, developer tooling, etc.), this workflow will research and curate a list of candidates.

## How to Run

1. Open VS Code with Copilot enabled
2. Run the `/company-curation` prompt

The workflow will use Firecrawl to research companies, evaluate them against your criteria in `shared/company_evaluation_rules.md`, and output a CSV of candidates.

## Customization

The included configuration targets tech companies (GitLab, Splunk, Elastic, etc.) relevant to Cloud Infrastructure / DevOps roles. Adjust for your own interests:

- **`shared/company_evaluation_rules.md`** -- Defines what makes a company worth monitoring (size, business model, industry, remote policy)
- **`config/exclusions.yml`** -- Companies already applied to or explicitly skipped

## Tips

- **ATS duplicates:** If you notice a company's career portal URL points to an ATS platform (e.g., `boards.greenhouse.io/companyname`), consider deleting it from your targets CSV. The `/ats-platform-search` workflow already searches ATS platforms, so monitoring the same company through both workflows is redundant.
- **Start broad, then prune:** Aim for around 40 companies in your initial curation. You can always exclude companies later after running the monitoring workflow a few times.
- **Industry focus:** The evaluation rules are the main lever for controlling which companies appear. If you're targeting a different industry (fintech, healthcare, etc.), update those rules first.

## Related

- [Company Monitoring](company-monitoring.md) -- The next step after curation
- [Company Targets Maintenance](company_targets_maintenance.md) -- How to maintain the CSV over time
