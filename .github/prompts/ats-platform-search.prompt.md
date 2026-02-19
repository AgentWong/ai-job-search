---
name: ats-platform-search
description: Search ATS platforms for infrastructure roles using Firecrawl search
tools:
  ['read/readFile', 'edit/createFile', 'edit/editFiles', 'agent']
---

# Job Board Search Workflow

Search approved job boards for infrastructure roles using Firecrawl search with integrated content analysis. Job boards and roles are defined in `config/inclusions.yml` for easy expansion.

## Purpose

This workflow uses `firecrawl_search` to discover positions on job board platforms. It complements the company-monitoring workflow by focusing on third-party ATS platforms.

---

## Architecture: Orchestrator + Subagents

This workflow uses **subagents to prevent context degradation**. Each search query can return 25+ results with full job descriptions, consuming significant context. By delegating per-query execution to isolated subagents, the orchestrator maintains a clean context throughout.

**Pattern:**
```
Orchestrator: Load inclusions.yml → Build query queue (role × job_board) → Track statistics
    ↓
BATCH DISPATCH all primary-tier queries simultaneously (one subagent per query)
    ↓
Collect all primary results → Aggregate → Check if target reached
    ↓ (if target not reached)
BATCH DISPATCH all secondary-tier queries simultaneously
    ↓
Orchestrator: Aggregate all results → Calculate effectiveness stats → Write CSV → Report
```

---

## Configuration

| Parameter | Source | Description |
|-----------|--------|-------------|
| `job_boards` | `config/inclusions.yml` | Job boards in priority order |
| `target_roles.primary` | `config/inclusions.yml` | Primary roles to search |
| `target_roles.secondary` | `config/inclusions.yml` | Secondary roles (if needed) |
| `search_config.target_positions` | `config/inclusions.yml` | Min qualified positions before stopping |
| `search_config.search_limit` | `config/inclusions.yml` | Results per query |
| `search_config.google_time_filter` | `config/inclusions.yml` | Time filter for search (e.g., `qdr:w`, `qdr:m`) |

---

## Pre-Execution: Load Reference Files (Orchestrator)

Read these configuration files:
- [Inclusions](../../config/inclusions.yml) - **Job boards and roles in priority order**
- [Exclusions](../../config/exclusions.yml) - Check `excluded_companies` list and skip any matching companies

**Note:** The subagent will reference scoring framework and job preferences internally.

---

## Query Queue Generation

> **⚠️ MANDATORY: QUOTED SEARCH TERMS**
> When passing role terms to subagents, the `firecrawl-job-search` agent MUST wrap role names in double quotes (`"DevOps Engineer"`) in the search query for exact phrase matching. Unquoted searches match individual words separately (e.g., "Platform" OR "Engineer"), producing hundreds of irrelevant results. The agent enforces this, but if you observe unquoted search queries in subagent results, flag it as an error.

**Build the query queue dynamically from `inclusions.yml`:**

```
# Extract search config
time_filter = inclusions.search_config.google_time_filter  # e.g., "qdr:w" or "qdr:m"
search_limit = inclusions.search_config.search_limit        # e.g., 25, 50

query_queue = []
FOR EACH role_tier IN [primary, secondary]:
    FOR EACH role IN inclusions.target_roles[role_tier] (sorted by priority):
        FOR EACH board IN inclusions.job_boards (in order):
            query_queue.append({
                role: role.name,
                board: board.domain,
                tier: role_tier
            })
```

**Example generated queue (from default inclusions.yml):**

| Query | Tier | Role | Job Board |
|-------|------|------|-----------|
| 1 | primary | DevOps Engineer | jobs.ashbyhq.com |
| 2 | primary | DevOps Engineer | boards.greenhouse.io |
| 3 | primary | DevOps Engineer | jobs.lever.co |
| 4 | primary | DevOps Engineer | careers.kula.ai |
| 5 | primary | DevOps Engineer | builtin.com |
| 6 | primary | DevOps Engineer | weworkremotely.com |
| 7 | primary | Infrastructure Engineer | jobs.ashbyhq.com |
| ... | ... | ... | ... |

**Execution rules:**
1. Execute all `primary` tier queries first
2. If `total_qualified < target_positions`, continue to `secondary` tier
3. Stop early if `target_positions` reached

---

## Stage 1: Query Execution (Subagents)

For **each query** in the queue, invoke the `firecrawl-job-search` agent.

### Parallel Batch Dispatch with Statistics Tracking

> **⚠️ PARALLEL EXECUTION REQUIRED**
> All queries within each tier MUST be dispatched simultaneously as parallel subagents — not one at a time. Launch all primary-tier subagents in a single parallel batch, wait for all to complete, then (if needed) launch all secondary-tier subagents in a second parallel batch.

```
total_qualified = 0
stats = {
    by_role: {},      # { "DevOps Engineer": { found: 100, qualified: 5, rate: 0.05 } }
    by_board: {},     # { "jobs.ashbyhq.com": { found: 50, qualified: 3, rate: 0.06 } }
    by_role_board: {} # { "DevOps Engineer|jobs.ashbyhq.com": { found: 25, qualified: 2 } }
}

# PHASE 1: Dispatch ALL primary-tier queries simultaneously
primary_queries = [q for q in query_queue if q.tier == "primary"]
primary_results = PARALLEL_DISPATCH [
    runSubagent(
        agent: "firecrawl-job-search",
        prompt: "Execute Job Board Search Task Type 1:
            - Query Number: [QUERY_NUMBER]
            - Role Term: [query.role]
            - Job Board: [query.board]
            - Time Filter: [time_filter]
            - Search Limit: [search_limit]"
    )
    FOR each query in primary_queries
]

# Aggregate primary results
FOR each result in primary_results:
    aggregate qualified_positions
    aggregate excluded_positions
    total_qualified += len(result.qualified_positions)
    update stats.by_role, stats.by_board, stats.by_role_board

# PHASE 2: If target not reached, dispatch ALL secondary-tier queries simultaneously
IF total_qualified < target_positions:
    secondary_queries = [q for q in query_queue if q.tier == "secondary"]
    secondary_results = PARALLEL_DISPATCH [
        runSubagent(
            agent: "firecrawl-job-search",
            prompt: "Execute Job Board Search Task Type 1:
                - Query Number: [QUERY_NUMBER]
                - Role Term: [query.role]
                - Job Board: [query.board]
                - Time Filter: [time_filter]
                - Search Limit: [search_limit]"
        )
        FOR each query in secondary_queries
    ]

    # Aggregate secondary results
    FOR each result in secondary_results:
        aggregate qualified_positions
        aggregate excluded_positions
        total_qualified += len(result.qualified_positions)
        update stats.by_role, stats.by_board, stats.by_role_board

# Calculate effectiveness rates
FOR each role IN stats.by_role:
    stats.by_role[role].rate = qualified / found (or 0 if found=0)
FOR each board IN stats.by_board:
    stats.by_board[board].rate = qualified / found (or 0 if found=0)
```

---

## Stage 2: Output Processing (Orchestrator)

After subagents complete (or target reached):

### 2.1 Aggregate Results

Collect from all subagent responses:
- All `qualified_positions` arrays
- All `excluded_positions` arrays
- Query success/failure tracking

### 2.2 Check Existing Results

Read `results/application_queue.csv` if it exists.

### 2.3 Deduplicate

Compare new positions against existing by company+title. Skip duplicates.

### 2.4 Write Results

If CSV doesn't exist, create with headers:
```csv
company,title,url,source_track,discovered_date,quality_score,iac_tools,cloud_platform,remote_status,match_reasons,disqualifiers
```

Append new positions with `source_track` = "job_board".

---

## Stage 3: Final Report (Orchestrator)

```
## Job Board Search Complete

### Search Summary
- Queries executed: X of Y total
- Total results scanned: A
- Qualified positions: B
- **Overall qualification rate: B/A (X.X%)**
- Application-ready (score 6+): C
- Review needed (score 4-5): D

### Effectiveness by Role
| Role | Found | Qualified | Rate | Status |
|------|-------|-----------|------|--------|
| DevOps Engineer | 100 | 8 | 8.0% | ✅ Effective |
| Infrastructure Engineer | 80 | 5 | 6.3% | ✅ Effective |
| Cloud Engineer | 75 | 2 | 2.7% | ⚠️ Below threshold |
| Platform Engineer | 50 | 0 | 0.0% | ❌ Consider removing |

**⚠️ Roles with <5% qualification rate may indicate:**
1. Role term doesn't match your criteria well
2. Scoring/filter criteria may be too strict for this role
3. Role should be removed from `config/inclusions.yml`

### Effectiveness by Job Board
| Job Board | Found | Qualified | Rate | Status |
|-----------|-------|-----------|------|--------|
| jobs.ashbyhq.com | 50 | 5 | 10.0% | ✅ High yield |
| boards.greenhouse.io | 80 | 4 | 5.0% | ✅ Effective |
| jobs.lever.co | 60 | 2 | 3.3% | ⚠️ Below threshold |
| builtin.com | 40 | 1 | 2.5% | ⚠️ Consider deprioritizing |

**⚠️ Job boards with <3% qualification rate may not be worth searching.**

### Cross-Analysis: Role × Job Board
| Role | Best Board | Worst Board | Recommendation |
|------|------------|-------------|----------------|
| DevOps Engineer | Ashby (12%) | Lever (2%) | Prioritize Ashby |
| Infrastructure Engineer | Greenhouse (8%) | WWR (1%) | Skip WWR for this role |

### New Additions to Queue
| Company | Title | Score | Job Board | Key Matches |
|---------|-------|-------|-----------|-------------|
| ... | ... | ... | ... | ... |

### Exclusions Summary
- Senior titles: X
- Non-US/Non-remote: Y
- Wrong industry: Z
- Technical mismatch: W

### Technical Match Summary
- Terraform: X positions
- Ansible: Y positions
- AWS-primary: Z positions

### Duplicates Skipped: X

### Quality Metrics
- IaC tool mention rate: X%
- AWS focus rate: Y%
- Average quality score: Z

### 🔧 Optimization Recommendations
Based on this search run:
1. **High-performing combinations:** [list role+board with >10% rate]
2. **Underperforming roles to review:** [list roles with <5% rate]
3. **Job boards to deprioritize:** [list boards with <3% rate]
4. **Suggested inclusions.yml changes:** [specific edits]
```

---

## Error Handling

| Error | Action |
|-------|--------|
| Single query returns 0 | Expected - continue to next query |
| Subagent fails | Log issue, continue to next query |
| All queries return 0 | ABORT with diagnostic report |
| < 5 qualified positions | Report as partial success |

---

## Usage

```
/ats-platform-search
```

---

## Related Workflows

- **company-curation** - Curates companies with direct career pages
- **company-monitoring** - Monitors curated companies (avoids job boards)
