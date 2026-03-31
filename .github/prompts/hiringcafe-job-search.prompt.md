---
name: hiringcafe-job-search
description: Search Hiring Cafe for infrastructure positions using Chrome DevTools automation
tools:
  ['read/readFile', 'edit/createFile', 'edit/editFiles', 'agent']
---

# Hiring Cafe Job Search Workflow

Search Hiring Cafe for infrastructure roles using browser automation via Chrome DevTools MCP. This workflow leverages Hiring Cafe's structured job metadata (AI-parsed YOE, tech tools, requirements summaries) to efficiently filter and score positions from search result cards.

## Purpose

Hiring Cafe is a job aggregator that enriches job postings with AI-parsed metadata including years of experience, technical tools, and requirements summaries. Unlike other platforms where this data must be extracted from full job descriptions, Hiring Cafe displays all scoring-relevant data directly on search result cards. This enables a single-phase extraction approach.

### Key Advantages over Other Platforms
- **No login required** — public search, no anti-bot concerns
- **Pre-parsed metadata** — YOE, tech tools, salary, and requirements visible on cards
- **Boolean title search** — `jobTitleQuery` parameter enables exact phrase matching on job titles
- **URL-based filters** — all search state encoded in URL, no UI interaction needed
- **Single-phase extraction** — no need for separate detail-fetching phase

---

## Architecture: Orchestrator + Single-Phase Agent

This workflow uses a **single-phase agent** because Hiring Cafe search cards contain all data needed for scoring. No detail page visits are required.

**Pattern:**
```
Orchestrator: Load configs → Build search URL → Track statistics
    ↓
Subagent(hiringcafe-job-search): Navigate to URL → Extract cards → Filter & Score → Return results
    ↓
Orchestrator: Aggregate → Deduplicate → Write CSV → Report
```

> **CRITICAL: SERIAL EXECUTION ONLY**
> All subagent invocations in this workflow MUST be executed **one at a time, in strict sequential order**. You MUST wait for each `runSubagent()` call to fully return its results before invoking the next one. NEVER run multiple subagents in parallel. All subagents share a single Chrome browser tab via Chrome DevTools MCP — parallel execution causes cross-contamination, hallucinations, and navigation conflicts.

**Why Single-Phase?**
- Hiring Cafe search cards display title, company, salary, YOE, tech stack, and requirements summary
- All scoring criteria can be evaluated from card data alone
- No separate detail-fetching phase needed

---

## Prerequisites

### Browser Setup (One-Time)

1. **Start Chrome with remote debugging:**
   ```bash
   ./scripts/start-chrome-debug.sh
   ```

2. **Keep Chrome running** during workflow execution

**Note:** No login is required — Hiring Cafe is a public job search platform.

---

## Configuration

| Parameter | Source | Description |
|-----------|--------|-------------|
| `target_roles` | `config/inclusions.yml` | Roles to search (primary, secondary) — used for `jobTitleQuery` |
| `time_filter` | `config/inclusions.yml` | Time range: `past_day`, `past_week`, or `past_month` |
| `excluded_companies` | `config/exclusions.yml` | Companies to skip |

---

## Pre-Execution: Load Configuration (Orchestrator)

### 1. Load Reference Files

Read these configuration files:
- [Inclusions](../../config/inclusions.yml) - **Roles and time filter**
- [Exclusions](../../config/exclusions.yml) - Check `excluded_companies` list

### 2. Build Job Title Query

From `inclusions.yml`, construct the `jobTitleQuery` using all target roles with quoted phrases:

```
jobTitleQuery = ""
FOR tier IN [primary, secondary]:
    FOR role IN inclusions.target_roles[tier]:
        IF jobTitleQuery is not empty:
            jobTitleQuery += " OR "
        jobTitleQuery += '"' + role.name + '"'

# Example result:
# "DevOps Engineer" OR "Infrastructure Engineer" OR "Cloud Engineer" OR "Platform Engineer" OR "Site Reliability Engineer" OR "Cloud Operations" OR "Cloud Administrator"
```

> **CRITICAL: QUOTED PHRASES**
> Each role name MUST be wrapped in double quotes within the `jobTitleQuery` value. Without quotes, "Cloud Engineer" matches any job with "Cloud" OR "Engineer" in the title, producing 10x+ noise. With quotes, it matches only jobs with the exact phrase "Cloud Engineer" in the title.

### 3. Map Time Filter

Convert the `time_filter` from `inclusions.yml` to the Hiring Cafe `dateFetchedPastNDays` value:

| time_filter | dateFetchedPastNDays | Hiring Cafe Label |
|-------------|---------------------|-------------------|
| `past_day` | `2` | Past 24 hours |
| `past_week` | `14` | 1 week |
| `past_month` | `61` | 1 month |

**Note:** Hiring Cafe's `dateFetchedPastNDays` values are approximately 2x the calendar days. This is because the parameter refers to when the listing was fetched/crawled, not when the job was posted. Using the exact values above ensures the time filter button displays correctly.

### 4. Construct Search URL

Build the Hiring Cafe search URL with the `searchState` parameter:

```json
{
  "locations": [{
    "formatted_address": "United States",
    "types": ["country"],
    "geometry": {"location": {"lat": "46.4201", "lon": "-117.0146"}},
    "id": "user_country",
    "address_components": [{"long_name": "United States", "short_name": "US", "types": ["country"]}],
    "options": {"flexible_regions": ["anywhere_in_continent", "anywhere_in_world"]}
  }],
  "searchQuery": "",
  "workplaceTypes": ["Remote"],
  "dateFetchedPastNDays": [MAPPED_VALUE],
  "currency": {"label": "usd", "value": "usd"},
  "restrictJobsToTransparentSalaries": false,
  "roleYoeRange": [0, 10],
  "roleTypes": ["Individual Contributor"],
  "companySizeRanges": [[51,200],[201,500],[501,1000],[1001,2000],[2001,5000],[5001,10000],[10001,null]],
  "seniorityLevel": ["No Prior Experience Required", "Entry Level", "Mid Level"],
  "securityClearances": ["None", "Confidential", "Secret", "Public Trust", "Interim Clearances", "Other"],
  "airTravelRequirement": ["None"],
  "landTravelRequirement": ["None"],
  "jobTitleQuery": "[CONSTRUCTED_TITLE_QUERY]",
  "technologyKeywordsQuery": "AWS OR Terraform OR Ansible"
}
```

**Filter rationale:**
- `searchQuery` is empty — the main search bar does full-text body search (not title search), producing irrelevant results. `jobTitleQuery` handles title matching.
- `restrictJobsToTransparentSalaries: false` — salary transparency filter removes ~60% of results. Salary is visible on cards when available; the agent handles salary-less jobs.
- No `maxCompensationLowEnd` — the salary cap removes ~34% of transparent-salary results. The agent can flag salary concerns during scoring.
- No education filters — education filters remove ~95% of results. Education requirements are evaluated by the agent from the requirements summary.
- `technologyKeywordsQuery: "AWS OR Terraform OR Ansible"` — broadens results to include jobs mentioning these technologies even with slightly variant titles.
- `companySizeRanges` excludes 1-10 and 11-50 employee ranges — small startups often expect one person to cover too many roles.
- `securityClearances` excludes Top Secret/SCI only.

URL construction:
```
search_url = "https://hiring.cafe/?searchState=" + URL_ENCODE(JSON_STRINGIFY(searchState))
```

### 5. Initialize Browser Session

Connect to Chrome DevTools at `http://127.0.0.1:9222`.

If connection fails:
```
ERROR: Cannot connect to Chrome remote debugging port.

Action required:
1. Start Chrome with debugging: ./scripts/start-chrome-debug.sh
2. Ensure port 9222 is not blocked
3. Verify Chrome is running

ABORT workflow - browser connection required
```

---

## Stage 1: Search & Extract (hiringcafe-job-search)

Invoke the `hiringcafe-job-search` agent with the constructed search URL.

### Search Execution

```
all_qualified = []
all_disqualified = []

# Extract excluded companies list
excluded_companies = exclusions.excluded_companies

result = runSubagent(
    agent: "hiringcafe-job-search",
    prompt: "Search Hiring Cafe for infrastructure positions:
        - Search URL: [constructed_search_url]
        - Excluded Companies: [excluded_companies as comma-separated list]"
)

all_qualified += result.qualified_positions
all_disqualified += result.disqualified_positions

stats = {
    total_results: result.total_results_shown,
    jobs_processed: result.jobs_processed,
    qualified: result.qualified_count,
    disqualified: result.disqualified_count
}
```

**Note:** If results exceed 100 jobs (unlikely with daily runs), invoke additional subagents with pagination if the platform supports it. For typical daily runs with `past_day` filter, a single invocation is sufficient.

---

## Stage 2: Output Processing (Orchestrator)

### 2.1 Check Existing Results

Read `results/application_queue.csv` if it exists.

### 2.2 Deduplicate

Compare new positions against existing by company+title. Skip duplicates.

**Deduplication Rules:**
1. **Within new results:** Use URL as primary key
2. **Against existing CSV:** Use company+title as primary key
   - If position exists with different source (e.g., `linkedin`), keep both entries
   - Hiring Cafe positions get source track: `hiringcafe`

### 2.3 Write Results

If CSV doesn't exist, create with headers:
```csv
company,title,url,source_track,discovered_date,quality_score,iac_tools,cloud_platform,remote_status,match_reasons,disqualifiers
```

Append new positions with `source_track` = `hiringcafe`.

### 2.4 Close Browser Session

Disconnect from Chrome DevTools (leave Chrome running for next workflow execution).

---

## Stage 3: Final Report (Orchestrator)

```
## Hiring Cafe Job Search Complete

### Search Summary
- Time filter: [time_filter] (dateFetchedPastNDays: [value])
- Total results on page: X
- Jobs processed: Y
- **Qualified positions: Z (passed scoring)**
- Disqualified positions: W
- **Qualification rate: Z/Y (X.X%)**
- Application-ready (score 6+): A
- Review needed (score 4-5): B

### Search URL Configuration
- Job Title Query: "DevOps Engineer" OR "Infrastructure Engineer" OR ...
- Technology Keywords: AWS OR Terraform OR Ansible
- Filters: Remote, US, IC, Entry-Mid Level, No Travel, No TS/SCI

### New Additions to Queue
| Company | Title | Score | Salary | YOE | Tech Tools | Key Matches |
|---------|-------|-------|--------|-----|------------|-------------|
| ... | ... | ... | ... | ... | ... | ... |

### Disqualification Summary
| Reason | Count |
|--------|-------|
| Senior/Staff/Lead title | X |
| Excluded company | Y |
| Wrong role type (Software Eng, Data Eng, etc.) | Z |
| GCP-only | W |
| High YOE (7+) | V |
| Score below threshold | U |

### Technical Match Summary (Qualified Positions)
- Terraform mentioned: X positions
- Ansible mentioned: Y positions
- AWS-primary: Z positions
- Kubernetes mentioned: W positions

### Quality Metrics
- Average quality score: X.X
- IaC tool mention rate: X%
- AWS focus rate: Y%

### Duplicates Skipped
- Already in queue: X

### Platform Observations
- Salary transparency rate: X% (of processed jobs had salary listed)
- Average YOE requirement: X years
- Most common tech tools: [top 5]
```

---

## Error Handling

| Error | Action |
|-------|--------|
| Cannot connect to Chrome | ABORT - user must start Chrome with debugging |
| Page load timeout | Retry navigation once, then abort |
| Zero results returned | Report as complete with diagnostic info |
| Subagent fails | Log issue, report partial results |

---

## Hiring Cafe-Specific Considerations

### Platform Characteristics
- **No login required** — reduces complexity and eliminates session management
- **No anti-bot detection** — public search API, no rate limiting observed
- **AI-enriched data** — pre-parsed YOE, tech tools, and requirements summary
- **URL-deterministic** — identical URL always produces identical results (good for reproducibility)

### Filter Discovery Notes
These filter impact metrics were measured during workflow development (30-day window):

| Filter | Impact |
|--------|--------|
| Quoted `jobTitleQuery` phrases | 990 → 83 results (92% noise reduction) |
| Education filters (Bachelor's=Preferred) | 83 → 4 results (95% loss — do NOT use) |
| Salary transparency ON | 302 → 127 results (58% loss) |
| $115k salary cap | 127 → 83 results (34% loss) |
| Technology keywords (AWS/Terraform/Ansible) | 84 → 127 results (broadens pool by ~50%) |

---

## Usage

```
/hiringcafe-job-search
```

**Prerequisites:**
1. Chrome must be running with remote debugging: `./scripts/start-chrome-debug.sh`

---

## Troubleshooting

### "Cannot connect to Chrome"
```bash
# Check if Chrome is running with debugging
lsof -i :9222

# If not, start it
./scripts/start-chrome-debug.sh
```

### "0 results returned"
1. Check if Hiring Cafe is up (navigate manually to https://hiring.cafe)
2. Verify the time filter — `past_day` with very specific title queries may yield 0-5 results on quiet days
3. Try widening to `past_week` temporarily to verify filters work

### "Page loads slowly or times out"
1. Hiring Cafe can be slow with complex filter combinations
2. The agent waits 5-10 seconds for initial load (longer than other platforms)
3. If persistent, check internet connectivity

---

## Related Workflows

- **ats-platform-search** - Search ATS platforms (Greenhouse, Lever, etc.)
- **company-monitoring** - Monitor curated company career pages
- **company-curation** - Curate companies for monitoring
