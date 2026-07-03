# Hiring Cafe Job Search Workflow

Search Hiring Cafe for infrastructure roles using browser automation via Chrome DevTools MCP. Hiring Cafe provides AI-parsed metadata (YOE, tech tools, requirements summaries) on search cards. No login required.

---

## Architecture: Two-Phase Sequential

**CRITICAL: SERIAL EXECUTION ONLY.** All subagent invocations MUST be one at a time. Never run subagents in parallel or in the background. All agents share a single Chrome tab — parallel execution causes cross-contamination and navigation conflicts.

```
Orchestrator: Load configs → Build search URL
    ↓
Agent (hiringcafe-job-search): Navigate → Extract cards → Filter & Score → Return viewjob URLs
    ↓  (wait for completion)
Agent (browser-fetch, batches of 15): Resolve destination URL → Fetch → Verify remote → Re-score
    ↓
Orchestrator: Aggregate → Deduplicate → Write CSV → Report → Update tracking
```

---

## Prerequisites

Chrome must be running with remote debugging:
```bash
./scripts/start-chrome-debug.sh
```

---

## Pre-Execution: Load Configuration

### 1. Read Config Files

- `config/config.yml` — roles and time filter
- *(Exclusions are read by subagents directly)*

### 2. Build Job Title Query

```
jobTitleQuery = ""
# `local_only` roles (high-noise generalist titles, e.g. Systems Administrator)
# run ONLY in local mode; skip them when remote.
tiers = [primary, secondary]
IF inclusions.location.remote == false: tiers += [local_only]
FOR tier IN tiers:
    FOR role IN inclusions.target_roles[tier]:
        IF jobTitleQuery not empty: jobTitleQuery += " OR "
        jobTitleQuery += '"' + role.name + '"'
```

Each role name MUST be wrapped in double quotes (e.g. `"DevOps Engineer" OR "Platform Engineer"`). Without quotes, results expand 10x+ by matching individual words.

### 3. Map Time Filter

| config.yml | dateFetchedPastNDays |
|---------------|---------------------|
| `past_day` | `2` |
| `past_2_days` | `3` |
| `past_week` | `14` |
| `past_month` | `61` |

Hiring Cafe's `dateFetchedPastNDays` reflects when the post was *scraped*, not
when it was *posted*, so each window is padded by ~1 day to cover scrape lag
(`past_day` → 2 scraped days; `past_2_days` → 3 scraped days).

### 4. Construct Search URL

**First read `config/config.yml` `location`** to set `locations` and `workplaceTypes`
(everything else is mode-independent). The JSON below is the **remote-mode** default;
see the local-mode override directly after it.

Build the searchState JSON and URL-encode it:

```json
{
  "locations": [{"formatted_address": "United States", "types": ["country"], "geometry": {"location": {"lat": "46.4201", "lon": "-117.0146"}}, "id": "user_country", "address_components": [{"long_name": "United States", "short_name": "US", "types": ["country"]}], "options": {"flexible_regions": ["anywhere_in_continent", "anywhere_in_world"]}}],
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

```
search_url = "https://hiring.cafe/?searchState=" + URL_ENCODE(JSON_STRINGIFY(searchState))
```

**Local-mode override (`config.yml` `location.remote: false`, target `{city}, {state}`):**
replace only `locations` and `workplaceTypes`. Set `workplaceTypes` to
`["Onsite", "Hybrid"]`, adding `"Remote"` when `location.accept_remote_in_local_mode: true`.
Set `locations` to a city object for the target metro with a search radius in
`options` (driven by `location.distance_miles`) — example for Portland, OR at 25 miles
(verified live shape):
```json
"locations": [{"id": "xhk1yZQBoEtHp_8Uv_KY", "types": ["locality"], "address_components": [{"long_name": "Portland", "short_name": "Portland", "types": ["locality"]}, {"long_name": "Oregon", "short_name": "ID", "types": ["administrative_area_level_1"]}, {"long_name": "United States", "short_name": "US", "types": ["country"]}], "geometry": {"location": {"lat": 46.41655, "lon": -117.01766}}, "formatted_address": "Portland, OR, US", "options": {"radius": [DISTANCE_MILES], "radius_unit": "miles", "ignore_radius": false}}],
"workplaceTypes": ["Onsite", "Hybrid", "Remote"],
```
`options.radius` is the Hiring Cafe radius control (verified honored). Set it from
`location.distance_miles`; `radius_unit` is always `"miles"` and `ignore_radius` is
`false` (true would widen to the whole region and defeat the local search).

If the target city's `id`/lat/lon are unknown, type the city into Hiring Cafe's
location box in the browser, set the distance, and read the resolved `searchState`
back from the URL bar (the `locations[0].id` is an opaque Hiring Cafe place token).

### 5. Verify Browser Connection

Verify Chrome is reachable before spawning any agents. If connection fails, ABORT:
```
ERROR: Cannot connect to Chrome remote debugging port.
Start Chrome: ./scripts/start-chrome-debug.sh
```

---

## Stage 1: Search & Extract

Invoke the `hiringcafe-job-search` agent with the constructed search URL:

```
phase1_result = Agent(
    subagent_type: "hiringcafe-job-search",
    prompt: "Search Hiring Cafe for infrastructure positions.
        Search URL: [constructed_search_url]"
)
# WAIT for full completion
```

---

## Stage 1.5: Pre-Fetch Cooldown Filter

Before spending browser-fetch + LLM-scoring tokens on every Phase 1 candidate, classify them against the recent applications log. The script does exact-match cooldown deterministically (no LLM); the orchestrator only invokes LLM judgment on the fuzzy candidates where the company matches but the role differs.

```
A. Use the **Write tool** to write phase1_result.qualified_positions
   (each item with at least company, title, url) to:
       /tmp/hiringcafe-phase1-<ts>.json

B. Run:
   .venv/bin/python -m scripts.job_queue.cli fuzzy-check \
       --positions /tmp/hiringcafe-phase1-<ts>.json \
       --output /tmp/hiringcafe-cooldown-<ts>.json

   stdout: "Exact matches: E | Fuzzy candidates: F | Path: ..."

C. Read /tmp/hiringcafe-cooldown-<ts>.json. Build a `cooldown_skip_urls`
   set (URLs to drop from Stage 2 input):

   - For every entry in `exact_matches`: add `position.url` to the set
     and record {company, title, matched_prior_role, matched_prior_date}
     for the Stage 4 report.

   - For every entry in `fuzzy_candidates`: judge whether `position.title`
     is the SAME role function as any role in `company_recent_applications`,
     using these rules:
       * SRE = Site Reliability Engineer; SWE = Software Engineer
       * Specialization suffixes match base role: "SRE - Infra" ≈ "Site
         Reliability Engineer"
       * Strip seniority modifiers before comparing
       * Close synonyms collapse: "Platform Engineer" ≈ "Infrastructure
         Engineer"; "Cloud Engineer" ≈ "Cloud Infrastructure Engineer"
       * Genuinely different role families do NOT match: "DevOps Engineer"
         ≠ "Data Engineer"; "SRE" ≠ "Security Engineer"
     If SAME role → add `position.url` to `cooldown_skip_urls` and
     record the match for the report. If DIFFERENT role → leave it alone;
     it proceeds to Stage 2.

D. Filter phase1_result.qualified_positions to drop any item whose `url`
   is in `cooldown_skip_urls`. The filtered list is the Stage 2 input.

If `exact_matches` AND `fuzzy_candidates` are both empty, skip steps C–D
and go straight to Stage 2 with the original Phase 1 list.
```

---

## Stage 2: Destination URL Resolution + Full Verification

Process the **filtered** Phase 1 list (post-cooldown) in **batches of up to 15**. For each batch, invoke the `browser-fetch` agent. Wait for each batch to fully complete before starting the next.

**CRITICAL — DESTINATION URL:** The `hiring.cafe/viewjob/[id]` URL is a staging page and is NEVER written to the CSV. The agent resolves the destination URL (e.g. `https://jobs.lever.co/...`) and that is the canonical URL for all output.

```
all_qualified = []
all_disqualified = []

FOR each batch IN chunk(filtered_phase1_positions, size=15):
    batch_result = Agent(
        subagent_type: "browser-fetch",
        prompt: "Verify remote status and score these job postings from Hiring Cafe.
            Platform: other
            URLs: [batch positions as JSON — url field is a hiring.cafe/viewjob/... page]

            For each URL:
            1. Navigate to the hiring.cafe/viewjob/... page, wait 3-5 seconds
            2. Find the outbound Apply/Apply Now/View Job link to an external domain
            3. Extract that destination URL
            4. Navigate to the destination URL
            5. Score from the full job description
            6. Record the DESTINATION URL in output — NOT the hiring.cafe URL"
    )
    # WAIT for full completion

    all_qualified += batch_result.qualified_positions
    all_disqualified += batch_result.disqualified_positions
```

---

## Stage 3: Append to Queue (Script-Driven)

All deduplication, CSV header handling, and merging are performed by `scripts/job_queue/cli.py`. The orchestrator does NOT read or parse `results/application_queue.csv` directly. The `url` field for each position MUST contain the resolved destination URL (NOT the hiring.cafe/viewjob/... URL).

```
1. Use the **Write tool** (not Bash heredoc) to create
   /tmp/hiringcafe-positions-<unix-ts>.json

   Pick `<unix-ts>` yourself (e.g. `date +%s` output from a prior Bash call,
   or just a unique integer) and pass the same path to both Write and the CLI.

   Format: a plain JSON list of dicts, or {"positions": [...]}. Each
   dict should carry the full position fields from browser-fetch
   (company, title, url=destination URL, quality_score, iac_tools,
   cloud_platform, remote_status, match_reasons, disqualifiers).
   source_track is added by the script from --source-track.

2. Run:
   .venv/bin/python -m scripts.job_queue.cli append \
       --positions /tmp/hiringcafe-positions-<ts>.json \
       --source-track "hiringcafe"

3. Capture stdout. It looks like:
   Added: N | Duplicates skipped: M | Path: results/application_queue.csv

   Relay this one-line summary verbatim into Stage 4.
```

---

## Stage 4: Final Report

```
## Hiring Cafe Job Search Complete

### Search Summary
- Time filter: [time_filter] (dateFetchedPastNDays: [value])
- Total results on page: X
- Jobs processed: Y
- Phase 1 qualified (card scoring): Z
- Pre-fetch cooldown skips (exact + fuzzy LLM): K
- Phase 2 verified (destination fetch): V
- Phase 2 disqualified (remote/description mismatch): M
- Final qualified positions: V
- Qualification rate: V/Y (X.X%)
- Application-ready (score 6+): A
- Review needed (score 4-5): B

### Queue Append
<one-line stdout from scripts.job_queue.cli append>

### Search URL Configuration
- Job Title Query: [constructed query]
- Technology Keywords: AWS OR Terraform OR Ansible
- Filters: work-arrangement per `config.yml` `location` (Remote/US, or local `city, state` with on-site/hybrid), IC, Entry-Mid Level, No Travel, No TS/SCI

### New Additions to Queue
| Company | Title | Score | Salary | YOE | Tech Tools | Key Matches |
|---------|-------|-------|--------|-----|------------|-------------|

### Cooldown Skips (Pre-Fetch)
*Omit this section if no cooldown skips occurred.*
| Company | New Title | Matched Prior Role | Date Applied | Match Type |
|---------|-----------|--------------------|--------------|------------|
*Match Type is `exact` (script-deterministic) or `fuzzy-llm` (LLM judged same role).*

### Disqualification Summary
| Reason | Count |
|--------|-------|
| Senior/Staff/Lead title | X |
| Excluded company | Y |
| Wrong role type | Z |
| GCP-only | W |
| High YOE (7+) | V |
| Not remote (destination mismatch) | T |
| Could not resolve destination URL | S |

### Technical Match Summary (Qualified Positions)
- Terraform mentioned: X positions
- Ansible mentioned: Y positions
- AWS-primary: Z positions
- Kubernetes mentioned: W positions

### Effectiveness Tracker
<one-line stdout from scripts.effectiveness_tracker.cli append>
```

---

## Stage 5: Update Role Effectiveness Tracking (Script-Driven)

Rolling totals and trend markers are recomputed by `scripts/effectiveness_tracker/cli.py`. The orchestrator no longer reads, parses, or rewrites any markdown tracker.

Hiring Cafe is a single aggregated search (no per-role `stats.by_role`), so attribution is done by matching each qualified position's title to the closest role in `config/config.yml`.

```
1. For ALL roles in config.yml (even those with 0 attributed results):
       found_attributed = count of phase1_result.qualified_positions attributed to role
       qualified_attributed = count of all_qualified attributed to role
       rows.append({
           "role": role.name,
           "found": found_attributed,
           "qualified": qualified_attributed,
       })

   Use the **Write tool** (not Bash heredoc) to create
   /tmp/hiringcafe-tracker-<unix-ts>.json
   (plain list, or {"rows": [...]})

2. Run:
   .venv/bin/python -m scripts.effectiveness_tracker.cli append \
       --tracker browser_role \
       --source hiringcafe \
       --rows /tmp/hiringcafe-tracker-<ts>.json

3. Capture stdout:
   Logged N rows | Rolling totals recomputed for X roles | Path: results/tracking/data/browser_role_effectiveness.csv

   Relay this one-line summary into the Stage 4 "Effectiveness Tracker" slot.
```

## Error Handling

| Error | Action |
|-------|--------|
| Cannot connect to Chrome | ABORT — run `./scripts/start-chrome-debug.sh` |
| Page load timeout | Retry once, then abort |
| Zero results returned | Report as complete with diagnostic info |
| Subagent fails | Log issue, report partial results |
| Cannot resolve destination URL | Skip position, log as disqualified |
| Destination URL 404 | Skip position, log in fetch_errors |
