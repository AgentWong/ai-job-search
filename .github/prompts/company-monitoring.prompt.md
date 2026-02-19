---
name: company-monitoring
description: Monitor curated companies for infrastructure positions using Firecrawl
tools:
  ['read/readFile', 'edit/createFile', 'edit/editFiles', 'agent']
---

# Company Monitoring Workflow

Monitor curated companies for infrastructure positions by scraping their career pages. This workflow runs against a stable list of pre-validated companies, ensuring consistent monitoring over time. Roles to search for are defined in `config/inclusions.yml`.

## Purpose

This workflow processes the curated company list and discovers relevant job positions. Running monthly against the same CSV ensures you monitor the same set of companies consistently.

---

## Architecture: Orchestrator + Subagents

This workflow uses **subagents to prevent context degradation**. Scraping career pages and parsing job descriptions consumes significant context. By delegating per-company scraping and analysis to isolated subagents, the orchestrator maintains a clean context throughout.

**Pattern:**
```
Orchestrator: Load company list + inclusions.yml → Prepare company queue → Track statistics
    ↓
BATCH DISPATCH all company scrapes simultaneously (one subagent per company)
    ↓
Orchestrator: Collect all results → Aggregate → Calculate effectiveness stats → Write CSV → Report
```

---

## Configuration

| Parameter | Source | Description |
|-----------|--------|-------------|
| `companies_file` | `config/company_targets.csv` | Curated company list (manually reviewed from company-curation results) |
| `target_roles` | `config/inclusions.yml` | Roles to search for (primary + secondary) |

---

## Pre-Execution: Load Configuration (Orchestrator)

### 1. Load Reference Files

Read these configuration files:
- [Inclusions](../../config/inclusions.yml) - **Roles to search for in priority order**
- [Exclusions](../../config/exclusions.yml) - Check `excluded_companies` list and skip any matching companies
- `config/company_targets.csv` - Manually reviewed and curated company list

**Note:** The subagent will reference scoring framework and job preferences internally.

### 2. Build Role List from Inclusions

From `inclusions.yml`, extract the target roles:
```
target_roles = []
FOR tier IN [primary, secondary]:
    FOR role IN inclusions.target_roles[tier]:
        target_roles.append(role.name)
```

**Example (from default inclusions.yml):**
- DevOps Engineer
- Infrastructure Engineer
- Cloud Engineer
- Platform Engineer
- Cloud Infrastructure Engineer

### 3. Parse Company List

From `config/company_targets.csv`:
1. **Skip** rows where `Page_Quality_Grade` is explicitly `D` or `F` (empty/missing grades are allowed — treat as included)
2. **Skip** rows where `URL_Status` is explicitly `invalid` (empty/missing status or any other value like `active` are allowed — treat as included)
3. Extract: `Company_Name`, `Career_Page_URL`
4. Skip companies in exclusions.yml `excluded_companies` list
5. Create company queue for subagent processing

---

## Stage 1: Position Discovery (Subagents)

For **each company** in the queue, invoke the `firecrawl-job-search` agent.

### Parallel Batch Dispatch with Statistics Tracking

> **⚠️ PARALLEL EXECUTION REQUIRED**
> All company scrapes MUST be dispatched simultaneously as parallel subagents — not one at a time. Launch all subagents in a single parallel batch and wait for all to complete before aggregating.

```
stats = {
    by_role: {},      # { "DevOps Engineer": { found: 50, qualified: 5, rate: 0.10 } }
    by_company: {},   # { "Vercel": { found: 10, qualified: 2, rate: 0.20 } }
}

# Dispatch ALL company scrapes simultaneously
all_results = PARALLEL_DISPATCH [
    runSubagent(
        agent: "firecrawl-job-search",
        prompt: "Execute Company Career Page Scrape Task Type 2:
            - Company Name: [company.name]
            - Career URL: [company.career_url]
            - Target Roles: [target_roles_list]"
    )
    FOR each company in company_queue
]

# Aggregate after all subagents complete
FOR each (company, result) in zip(company_queue, all_results):
    aggregate qualified_positions
    aggregate excluded_positions
    aggregate scrape_issues

    # Track statistics by role
    FOR each position IN result.qualified_positions + result.excluded_positions:
        role = match_role(position.title, target_roles)  # Map title to role category
        stats.by_role[role].found += 1
        IF position IN qualified_positions:
            stats.by_role[role].qualified += 1

    # Track by company
    stats.by_company[company].found = result.total_positions_found
    stats.by_company[company].qualified = len(result.qualified_positions)

# Calculate effectiveness rates
FOR each role IN stats.by_role:
    stats.by_role[role].rate = qualified / found (or 0 if found=0)
```

---

## Stage 2: Output Processing (Orchestrator)

After all subagents complete:

### 2.1 Aggregate Results

Collect from all subagent responses:
- All `qualified_positions` arrays
- All `excluded_positions` arrays
- All scrape failures

### 2.2 Check for Existing Results

Read `results/application_queue.csv` if it exists.

### 2.3 Deduplicate

Compare new positions against existing CSV entries by company+title.
Skip duplicates.

### 2.4 Write Results

If CSV doesn't exist, create with headers:
```csv
company,title,url,source_track,discovered_date,quality_score,iac_tools,cloud_platform,remote_status,match_reasons,disqualifiers
```

Append new positions with `source_track` = "company_direct".

### 2.5 Update Company Metadata

Update `config/company_targets.csv` with:
- `Last_Validated`: Current date
- `Current_Remote_Roles`: Count of infrastructure roles found
- `Engineering_Jobs_Visible`: Count of engineering roles seen

---

## Stage 3: Final Report (Orchestrator)

```
## Company Monitoring Complete

### Discovery Results
- Companies monitored: X
- Companies skipped (D/F quality): Y
- Companies skipped (exclusions): Z
- Total positions scanned: A
- Infrastructure positions found: B
- After disqualification filtering: C
- **Overall qualification rate: C/B (X.X%)**
- Application-ready (score 6+): D
- Review needed (score 4-5): E

### Effectiveness by Role
| Role | Found | Qualified | Rate | Status |
|------|-------|-----------|------|--------|
| DevOps Engineer | 25 | 5 | 20.0% | ✅ Effective |
| Infrastructure Engineer | 15 | 3 | 20.0% | ✅ Effective |
| Cloud Engineer | 10 | 1 | 10.0% | ✅ Effective |
| Platform Engineer | 20 | 0 | 0.0% | ❌ Consider removing |
| Cloud Infrastructure Engineer | 5 | 0 | 0.0% | ⚠️ Low sample size |

**⚠️ Roles with 0% qualification rate across multiple runs should be reviewed:**
1. Role may not align with your criteria in `job_preferences.md`
2. Scoring criteria in `scoring_framework.md` may be too strict for this role
3. Consider removing from `config/inclusions.yml`

### Company Yield Analysis
| Company | Positions Found | Qualified | Rate | Action |
|---------|-----------------|-----------|------|--------|
| Vercel | 32 | 5 | 15.6% | ✅ Keep monitoring |
| LangChain | 13 | 2 | 15.4% | ✅ Keep monitoring |
| Voltage Park | 9 | 0 | 0.0% | ⚠️ Review next month |
| TRM Labs | 42 | 0 | 0.0% | ⚠️ Review next month |

### 🚩 Job Quality Red Flags

Companies flagged for potential removal based on job distribution analysis:

| Company | Total Jobs | Offshore % | India % | On-site % | Red Flags | Recommendation |
|---------|------------|------------|---------|-----------|-----------|----------------|
| ExampleCorp | 100 | 60% | 40% | 15% | Heavy offshoring | ❌ Remove |
| OfficeCorp | 50 | 10% | 5% | 85% | RTO culture | ❌ Remove |
| HealthyCorp | 75 | 20% | 15% | 30% | None | ✅ Keep |

### 🗑️ Companies Recommended for Removal

Add these companies to the `excluded_companies` list in `config/exclusions.yml`:

```yaml
excluded_companies:
  # ... existing entries ...

  # Removed from monitoring (add under this comment)
  - ExampleCorp
  - OfficeCorp
```

**Action Required:** Review flagged companies and manually add confirmed removals to `config/exclusions.yml`.

### New Additions to Queue
| Company | Title | Score | Key Matches |
|---------|-------|-------|-------------|
| ... | ... | ... | ... |

### Exclusions Summary
- Senior titles: X
- Non-US/Non-remote: Y
- Wrong industry: Z
- Technical mismatch: W

### Scrape Issues
| Company | Career URL | Issue |
|---------|------------|-------|
| ... | ... | Timeout |
| ... | ... | 404 |

### Technical Match Summary
- Terraform: X positions
- Ansible: Y positions
- AWS-primary: Z positions

### Duplicates Skipped: X

### 🔧 Optimization Recommendations
Based on this monitoring run:
1. **High-yield roles:** [list roles with >15% qualification rate]
2. **Underperforming roles to review:** [list roles with <5% rate]
3. **Companies yielding 0 qualified for 3+ months:** [list for removal consideration]
4. **Suggested inclusions.yml changes:** [specific edits]
```

---

## Error Handling

| Error | Action |
|-------|--------|
| Companies file not found | ABORT - ensure config/company_targets.csv exists and is populated |
| Subagent fails | Log issue, continue to next company |
| All subagents fail | ABORT with diagnostic report |
| No positions found | Report as valid result (no openings) |

---

## Usage

```
/company-monitoring
```

---

## Scheduling Recommendation

Run monthly against the same `config/company_targets.csv` for consistent monitoring. Same 50 companies last month = same 50 companies this month. Update the targets file by reviewing and copying qualified companies from `results/curated_companies.csv` after running the company-curation workflow.

---

## Related Workflows

- **company-curation** - Curates companies for this workflow
