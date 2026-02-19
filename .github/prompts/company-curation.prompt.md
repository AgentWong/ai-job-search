---
name: company-curation
description: Curate and validate companies with direct career page URLs for job monitoring
tools:
  ['read/readFile', 'edit/createFile', 'edit/editFiles', 'firecrawl/firecrawl-mcp-server/firecrawl_scrape', 'firecrawl/firecrawl-mcp-server/firecrawl_search', 'agent']
---

# Company Curation Workflow

Curate a list of candidate companies with URLs linking to their job postings. This workflow validates career page URLs and assesses their scrapability, excluding companies that redirect to third-party ATS platforms.

## Purpose

This workflow runs periodically to discover and validate new companies for the job monitoring workflow. The output is a curated CSV that serves as input to the `company-monitoring` workflow.

---

## Architecture: Orchestrator + Subagents

This workflow uses **subagents to prevent context degradation**. Scraping and evaluating career pages consumes significant context. By delegating per-company evaluation to isolated subagents, the orchestrator maintains a clean context throughout the workflow.

**Pattern:**
```
Orchestrator: Discovery search (all queries per round in parallel) → Extract company URLs (lightweight)
    ↓
BATCH DISPATCH all company evaluations simultaneously (one subagent per company)
    ↓
Orchestrator: Aggregate summaries → Write CSV → Report
```

---

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `output_file` | `results/curated_companies.csv` | Output CSV with curated companies |
| `search_limit` | 25 | Results per search query |

---

## Pre-Execution: Load Reference Files

Before starting, read these configuration files:
- [Exclusions](../../config/exclusions.yml) - Check `excluded_companies` list and skip any matching companies
- `config/company_targets.csv` - **Existing curated companies**

**Note:** The subagent will reference company evaluation rules internally.

### Calculate Target Shortfall

**Minimum total target: 50 companies**.

```
existing_firecrawl = count_rows(config/company_targets.csv) - 1  # Subtract header
total_existing = existing_firecrawl

IF total_existing >= 50:
    target_new_companies = 5  # Maintenance mode: find a few new candidates
ELSE:
    target_new_companies = 50 - total_existing + 10  # Overshoot to account for exclusions
```

Extract company names from the CSV to build an `existing_companies` set for deduplication.

---

## Stage 1: Initial Discovery (Orchestrator)

Use `firecrawl_search` to discover companies hiring for infrastructure roles.

**⚠️ AGGRESSIVE ITERATION:** This workflow should run multiple search rounds until `target_new_companies` qualified candidates are found. If the first round of searches doesn't yield enough candidates, continue with additional search variations.

### Search Strategy

```
qualified_candidates = []
search_round = 1

WHILE len(qualified_candidates) < target_new_companies AND search_round <= 5:
    Execute search queries for round
    Evaluate discovered companies via subagents
    Add passing companies to qualified_candidates
    search_round += 1

    IF search_round > 1:
        Use alternative search terms (see Additional Search Queries below)
```

### Search Queries (Round 1)

> **⚠️ PARALLEL EXECUTION REQUIRED**
> All search queries within a round MUST be dispatched simultaneously using parallel `firecrawl_search` calls — not sequentially.

Execute these searches to build a candidate list:

**Query 1: DevOps Engineer Hiring**
```json
{
  "query": "\"DevOps Engineer\" \"careers\" \"remote\" \"united states\" -site:boards.greenhouse.io -site:jobs.lever.co -site:builtin.com -site:linkedin.com -site:indeed.com -site:glassdoor.com",
  "limit": 25,
  "tbs": "qdr:m",
  "scrapeOptions": {
    "formats": ["markdown"],
    "onlyMainContent": true
  }
}
```

**Query 2: Infrastructure Engineer Hiring**
```json
{
  "query": "\"Infrastructure Engineer\" \"careers\" \"remote\" \"united states\" -site:boards.greenhouse.io -site:jobs.lever.co -site:builtin.com -site:linkedin.com -site:indeed.com -site:glassdoor.com",
  "limit": 25,
  "tbs": "qdr:m",
  "scrapeOptions": {
    "formats": ["markdown"],
    "onlyMainContent": true
  }
}
```

**Query 3: Cloud Engineer Hiring**
```json
{
  "query": "\"Cloud Engineer\" \"careers\" \"remote\" \"united states\" -site:boards.greenhouse.io -site:jobs.lever.co -site:builtin.com -site:linkedin.com -site:indeed.com -site:glassdoor.com",
  "limit": 25,
  "tbs": "qdr:m",
  "scrapeOptions": {
    "formats": ["markdown"],
    "onlyMainContent": true
  }
}
```

### Additional Search Queries (Rounds 2-5)

If Round 1 doesn't yield enough candidates, use these alternative queries:

**Round 2: Platform-focused**
- `"Platform Engineer" "careers" "remote" "united states" -site:...`
- `"Site Reliability" "careers" "remote" "hiring" -site:...` (evaluate carefully for on-call)
- `"Systems Engineer" "cloud" "careers" "remote" -site:...`

**Round 3: Tool-specific**
- `"Terraform" "engineer" "careers" "remote" -site:...`
- `"Kubernetes" "engineer" "careers" "remote" -site:...`
- `"AWS" "infrastructure" "careers" "remote" -site:...`

**Round 4: Industry verticals**
- `"DevOps" "SaaS" company careers -site:...`
- `"Infrastructure" "fintech" careers remote -site:...` (evaluate carefully)
- `"Cloud" "observability" company hiring -site:...`

**Round 5: Geographic variations**
- `"DevOps Engineer" "fully remote" "USA" careers -site:...`
- `"Infrastructure Engineer" "work from home" "United States" -site:...`

### Parse Search Results

From search results, extract a **lightweight candidate list** (do not process full content):
```json
[
  {"company": "Company A", "career_url": "https://companyA.com/careers"},
  {"company": "Company B", "career_url": "https://companyB.com/jobs"},
  ...
]
```

- Skip duplicates (same company from different queries)
- Skip companies in the `excluded_companies` list from exclusions.yml
- **Skip companies already in `existing_companies` set** (from company_targets*.csv files)

---

## Stage 2: Company Evaluation (Subagents)

For **each company** in the candidate list, invoke the `company-evaluator` agent.

### Parallel Batch Dispatch

> **⚠️ PARALLEL EXECUTION REQUIRED**
> All company evaluations MUST be dispatched simultaneously as parallel subagents — not one at a time. Launch all subagents in a single parallel batch and wait for all to complete before aggregating.

```
all_results = PARALLEL_DISPATCH [
    runSubagent(
        agent: "company-evaluator",
        prompt: "Evaluate this company for inclusion:
            - Company Name: [company.name]
            - Career URL: [company.career_url]"
    )
    FOR each company in candidate_list
]

# Aggregate after all subagents complete
FOR each result in all_results:
    store result in aggregated_results
```

---

## Stage 3: Result Aggregation (Orchestrator)

After all subagents complete:

### 3.1 Filter Results

From subagent responses:
- Collect companies where `include_in_curated_list == true`
- **Discard companies where `requires_playwright == true`** (these companies have problematic JavaScript that makes successful navigation difficult)
- **Discard companies that appear in the `excluded_companies` list from `exclusions.yml`** (these were already rejected in prior workflows and must not reappear in curated output)
- Route remaining companies to `results/curated_companies.csv`
- Track excluded companies for the final report

### 3.2 Write Curated Companies CSV (Firecrawl-compatible)

Create/update `results/curated_companies.csv` with companies that DO NOT require Playwright:

**IMPORTANT: Format the CSV with a space after each comma for better readability and URL clickability.**

```csv
Company_Name, Company_URL, Career_Page_URL, Employee_Count_Estimate, Company_Focus, Remote_Culture_Score, Page_Structure_Notes, Current_Remote_Roles, Overall_Fit_Score, Research_Notes, Source_References, Extraction_Method, URL_Status, Page_Quality_Grade, Total_Jobs_Visible, Engineering_Jobs_Visible, Extraction_Notes, Last_Validated
```

---

## Stage 4: Final Report (Orchestrator)

```
## Company Curation Complete

### Target Progress
- **Existing companies:** X
- **Target minimum:** 50
- **New companies added this run:** Z
- **New total:** X + Z
- **Target status:** ✅ Met / ⚠️ Shortfall of N

### Search Iterations
- Search rounds executed: N/5
- Queries per round: 3
- Stopped early: Yes/No (reason: target met / max rounds reached)

### Discovery Summary
- Companies discovered: X
- Companies deduplicated: Y
- Companies already in targets: W (skipped)
- Companies evaluated by subagents: Z

### Validation Results
- Companies added: A
- Companies discarded (problematic JavaScript): B
- Companies excluded: C

### Companies Discarded (Problematic JavaScript)
| Company | Pagination Type | Reason |
|---------|-----------------|--------|
| ... | algolia | 378 jobs claimed, only 10 visible - discarded |

### Quality Distribution
| Grade | Count |
|-------|-------|
| A | X |
| B | Y |
| C | Z |
| D/F | W |

### New Companies Added
| Company | Career URL | Quality | Engineering Roles |
|---------|------------|---------|-------------------|
| ... | ... | ... | ... |

### Companies Excluded
| Company | Reason |
|---------|--------|
| ... | Redirects to boards.greenhouse.io |
| ... | Industry: Healthcare IT |

### Next Steps
- Run /company-monitoring against curated_companies.csv
```

---

## Error Handling

| Error | Action |
|-------|--------|
| Search returns 0 results | Continue to next query |
| Subagent fails | Log failure, continue to next company |
| All searches fail | ABORT with diagnostic report |

---

## Usage

```
/company-curation
```

---

## Related Workflows

- **company-monitoring** - Monitors curated companies for positions
