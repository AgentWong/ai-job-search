# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-assisted job search automation using Claude Code workflows. The system discovers, evaluates, and tracks cloud infrastructure engineering positions through structured workflows executed as command and agent files.

## Architecture: Orchestrator + Dedicated Agents

All workflows use an **orchestrator + dedicated agent pattern** to prevent context degradation:

```
Orchestrator (.claude/commands/*.md): Load configs → Build task queue → Track progress
    ↓
FOR EACH task:
    Agent (.claude/agents/*.agent.md): Execute isolated task → Return structured JSON
    ↓
Orchestrator: Aggregate results → Write outputs → Report
```

This pattern is critical because:
- Search results and job descriptions consume significant context
- Each agent gets clean context for accurate analysis
- The orchestrator maintains state across many iterations
- Agents are reusable across multiple orchestrator workflows

### Agent Files (`.claude/agents/`)

| Agent | Purpose | Used By |
|-------|---------|---------|
| `firecrawl-job-search.agent.md` | Search/scrape with Firecrawl, filter & score positions | _(deprecated — both ats-platform-search and ats-platform-validate now use the Python `/v2/search` path)_ |
| `ats-platform-review.agent.md` | Fuzzy LLM review of Python-staged Firecrawl platform-search candidates (scores from full markdown, fuzzy disqualification); returns qualified rows for the orchestrator to queue | ats-platform-search |
| `browser-fetch.agent.md` | Fetch job detail pages, extract descriptions, score positions | hiringcafe-job-search |
| `hiringcafe-job-search.agent.md` | Search Hiring Cafe, extract & score from search cards (Phase 1) | hiringcafe-job-search |
| `ats-api-llm-review.agent.md` | Fuzzy LLM review of ATS-scraped candidates (catches title typos, unmapped non-US locations, subtle description signals); writes confirmed-qualified rows to application_queue.csv | ats-api-search |
| `resume-tailoring.agent.md` | Generate tailored single-page resume for a job posting | tailor-resume, tailor-resume-full |
| `resume-tailoring-2page.agent.md` | Generate tailored 2-page resume for a job posting | tailor-resume-full |
| `cover-letter.agent.md` | Generate point-by-point cover letter | process-clippings |
| `cover-letter-pitch.agent.md` | Generate 3-paragraph elevator pitch cover letter | process-clippings |

### Orchestrator-Agent Relationship

Orchestrators (`.claude/commands/*.md`) handle:
- Loading configuration files
- Building task queues
- Invoking agents via `Agent(subagent_type: "agent-name", prompt: "...")`
- Aggregating results and writing outputs

Agents (`.claude/agents/*.agent.md`) handle:
- Single isolated task execution
- Tool usage (Firecrawl, Chrome DevTools)
- Filtering and scoring logic
- Returning structured JSON

### Hybrid Pattern (Hiring Cafe)

Hiring Cafe uses a **two-phase approach** with an intermediate URL resolution step:

**Phase 1 (hiringcafe-job-search):** Search cards display AI-parsed metadata (title, company, salary, YOE, tech tools, requirements summary). Initial filter and score from card data. Returns Hiring Cafe viewjob URLs.

**URL Resolution (orchestrator):** Each Hiring Cafe viewjob page is visited to extract the outbound destination URL (ATS or company career page). The destination URL replaces the Hiring Cafe URL for all output.

**Phase 2 (browser-fetch):** Destination URLs are fetched to verify remote status and re-score from the full job description. Remote status confirmed against authoritative source to prevent false positives from Hiring Cafe's AI-parsed metadata.

## Workflow Commands

Located in `.claude/commands/`:

| Command | Purpose | Agent Used |
|---------|---------|------------|
| `ats-platform-search` | Search ATS platforms (Greenhouse, Lever, etc.) | `scripts/ats_platform_search/cli.py` → ats-platform-review |
| `hiringcafe-job-search` | Search Hiring Cafe with structured metadata | hiringcafe-job-search → browser-fetch |
| `tailor-resume` | Generate a tailored resume for a single job posting | resume-tailoring |
| `tailor-resume-full` | Batch-generate resumes for all clipped job postings | resume-tailoring, resume-tailoring-2page |
| `process-clippings` | Process new job clippings and generate cover letters | cover-letter, cover-letter-pitch |

### Script-Driven Workflows

These workflows call Python scripts directly rather than using LLM-based agents, making them cheaper to run:

| Command | Purpose | Script |
|---------|---------|--------|
| `ats-api-search` | Fetch jobs from ATS APIs for curated companies, filter, merge to queue | `scripts/ats_scraper/cli.py` |
| `ats-api-test` | Development/testing loop for the ATS API scraper | `scripts/ats_scraper/cli.py` |
| `linkedin-api-search` | Fetch jobs from LinkedIn's guest API, filter, score, stage for `linkedin-llm-review`, merge to queue | `scripts/linkedin_scraper/cli.py` |
| `builtin-api-search` | Fetch jobs from Built In's public API, filter, score, stage for `builtin-llm-review`, merge to queue | `scripts/builtin_scraper/cli.py` |
| `append-curation-results` | Merge the ATS Claude Desktop curation report into the target CSV | `scripts/curation_appender/cli.py` |
| `data-analysis` | Monthly: aggregate effectiveness CSVs + applications log into a JSON report; LLM reads the small JSON and recommends `config.yml` actions | `scripts/data_analysis/cli.py` |

The ATS API scraper hits public ATS APIs directly (Ashby, Greenhouse, Lever, SmartRecruiters, Rippling, Workday, Dayforce, iSolvedHire/ApplicantPro) for companies listed in `config/company_targets_ats.csv`. Initial filtering and regex-based scoring happen in Python (`scripts/ats_scraper/filters.py`, `scorer.py`); pre-filtered candidates are then staged to `results/ats_api_pending_review.json` for the `ats-api-llm-review` agent, which applies fuzzy disqualification using the full description and writes confirmed-qualified rows to `application_queue.csv`. Pass `--no-llm-review` to bypass the LLM step (legacy mode, regex-only). Supports `--posted-within past_day|past_week|past_month` for date filtering. Effectiveness tracking is written to `results/tracking/ats_api_effectiveness.md`.

`ats-platform-search` follows the **same Python-stages → LLM-reviews shape** (Option A; see `docs/ats-platform-search-token-regression-assessment.md`). `scripts/ats_platform_search/cli.py` builds the query queue from `config/config.yml` (board tiers + role tiers + `location`), calls Firecrawl `/v2/search` directly with `scrapeOptions` preserved (identical ~2cr/10 credit cost), writes the raw response to `results/ats_platform_cache/q{NN}_raw.json` (it never enters an LLM context — this is the regression fix), refunds 1 credit per query via `/v2/search/{id}/feedback`, **backfills Workday descriptions** (Workday is a JS SPA, so Firecrawl scrapes only nav chrome — its sole `no_description` source; `scripts/ats_platform_filter/workday_enrich.py` reconstructs the public **CXS JSON detail API** URL from the result URL — `/{locale}/{board}/job/...` → `/wday/cxs/{tenant}/{board}/job/...` — and injects the fetched JD into `markdown` **before** filtering, so Workday items reach the review agent like any server-rendered board; no new search, no Firecrawl credits; conservative — a failed/thin fetch falls through to the `no_description` gate; disable with `--no-workday-enrich`), runs the regex pre-filter (`scripts/ats_platform_filter/filters.py` — senior/wrong-role/crypto titles, excluded companies, non-US via title **+ Workday `/job/<loc>/` URL segment + US-guarded snippet scan**, and a `listing_health` gate that drops dead/expired/un-rendered pages carrying no scoreable JD), and stages kept candidates (full markdown + deterministic board/role attribution) into a **single** `review_batch_<tier>_01.json` (default `--review-batch-size 0`) plus a small `search_summary_<tier>.json`. The orchestrator reads only the small summary, dispatches a **single** `ats-platform-review` subagent for the tier (it reads the scoring configs once — parallel-per-batch would re-read them per subagent, since subagent contexts don't share a cache), then writes qualified rows via `scripts/job_queue/cli.py`. A large pool can be split across parallel subagents with `--review-batch-size N` (N>0). Run a tier with `.venv/bin/python -m scripts.ats_platform_search.cli --tier primary|secondary [--time-window …]`.

`ats-platform-validate` (the `/ats-platform-validate` command) is a reachability probe for candidate ATS/job-board domains discovered via Claude Desktop Research Mode (`claude_desktop/ats_platform_curation/`), run before a domain is added to `config.yml`. It uses the **same direct `/v2/search` API path** (no MCP server): `scripts/ats_platform_validate/cli.py` reads `claude_desktop/ats_platform_curation/candidates.yml`, drops candidates already covered by `config.yml` `job_boards` (wildcard-aware), searches each remaining domain (one `site:domain` query, primary roles only, hardcoded limit 10 / past month), refunds a credit per query, regex-filters for a qualified-count bonus signal, classifies a verdict (`PASS_STRONG`/`PASS_WEAK`/`MARGINAL`/`FAIL_EMPTY`/`FAIL_ERROR`), and writes the small `results/ats_platform_validation_cache/validation_summary.json` the orchestrator reads to compose the report. It does **not** write to `application_queue.csv`, update trackers, or modify `config.yml` — it emits a ready-to-paste `job_boards.secondary` stanza for the user to add manually. Run with `.venv/bin/python -m scripts.ats_platform_validate.cli [--time-window …]`. The legacy `firecrawl-job-search` MCP search subagent is now unused.

**LLM-review rejection auditing:** The Python pre-filters log their rejections to `results/tracking/data/ats_api_company_rejections.csv`, but the four LLM review agents (`ats-api-llm-review`, `builtin-llm-review`, `linkedin-llm-review`, `ats-platform-review`) previously only printed their disqualifications into the session summary, so there was no durable record of which scoring-framework categories the *fuzzy* review was rejecting on. Each review agent now appends its `disqualified` array to `results/tracking/data/llm_rejections.csv` via `scripts/llm_rejections/cli.py` (one row per position: `date,source_agent,company,title,url,category,reason`). The CLI parses the cited `Category N` prefix out of each `disqualification_reason` into its own column (reasons without a citation — cooldown, score-threshold — bucket as `Uncited`), so you can audit which categories cost the most volume before deciding what to loosen: `.venv/bin/python -m scripts.llm_rejections.cli rollup [--since YYYY-MM-DD]`.

The curation appender parses `.ai_references/company_curation_ats/report.md` (CSVs wrapped in triple-backtick codeblocks) and deduplicates against `config/company_targets_ats.csv` using case-insensitive `Company_Name` matching. The LLM never parses the CSV content itself — it only runs the script and relays the summary.

After every real append, the script regenerates `config/company_targets_ats.json` — a lean companion file with only `name`, `company_url`, `career_page_url`, and `ats_platform`. This is what the user pastes into Claude Desktop research mode for duplicate detection, replacing the full CSV which bloats context with research notes. The CSV remains the source of truth; the JSON is a generated mirror. Regenerate manually via `.venv/bin/python -m scripts.curation_appender.rebuild_companion` if it drifts out of sync.

## Configuration Hierarchy

### Core Configuration (`config/`)
- `config.yml` - Job boards, target roles, search config, and the **`location`** block (formerly `inclusions.yml`)
- `job_preferences.md` - Work arrangement, technical requirements, salary

#### Location mode (`config.yml` → `location`)
Every search workflow honors a single location toggle:
- `remote: true` (default) — search fully-remote US jobs. `state`/`state_abbr` are the candidate's residence and drive the state-restriction eligibility check (replaces the formerly hard-coded "Oregon" logic).
- `remote: false` — search local jobs in `city, state`. Hybrid/on-site are accepted; fully-remote US jobs are kept too unless `accept_remote_in_local_mode: false`.

The deterministic gate lives in `scripts/ats_scraper/location.py` (`LocationConfig`, `location_verdict`, `location_matches_metro`), shared by all three Python scrapers; the LLM/browser agents read the same block as the fuzzy catch. Search-URL handling per platform: ATS filters post-fetch (no geo URL); LinkedIn uses a free-text `location` param; Built In keeps work-arrangement path segments (`/jobs/remote/hybrid/office`) and constrains the metro via `city`/`state` query params — a `<city>-<state_abbr>` path slug does NOT filter on Built In (it returns nationwide results). See the commented Austin example in `config.yml`.

#### Role tiers (`config.yml` → `target_roles`)
Three buckets, each entry keyed by `name` + `priority`:
- `primary` / `secondary` — always searched. In the bundled Firecrawl workflow these drive query PHASE (primary queries run first; secondary only if the target is unmet).
- `local_only` — high-noise generalist titles (e.g. Systems Administrator, Systems Engineer) that flood remote searches with non-remote / non-matching results. Searched **only** when `location.remote: false`; **skipped entirely** in remote mode. In bundled-query workflows they fold into the `secondary` OR-group (no extra Firecrawl credits / query slots) rather than getting a dedicated slot. The mode gate is `scripts/ats_scraper/roles.py` (`active_role_buckets`), shared by the per-role scrapers (ATS API, Built In, LinkedIn); the Firecrawl `query_builder.build_queue` applies the secondary-fold; the browser/LLM workflows read the same `location.remote` toggle. data_analysis classifies these as `keep_local_only` (never auto-promoted/removed).
- `exclusions.yml` - Companies and patterns to skip
- `cv_full.md` - Complete work history for resume generation
- `company_targets_ats.csv` - Curated companies for ATS API scraper (platform, board token, career URL)
- `company_targets_ats.json` - Lean companion (name, URLs, platform) for Claude Desktop dedup; regenerated from the CSV by `scripts/curation_appender/rebuild_companion.py`

### Shared Rules (`shared/`)
- `scoring_framework.md` - Position scoring (0-10 scale) with boosters, penalties, and disqualifiers
- `company_evaluation_rules.md` - Company filtering by size, business model, industry
- `technical_requirements.md` - Technical skill matching criteria

## Output Files

### Main Output
- `results/application_queue.csv` - Qualified positions (company, title, URL, score)

### Generated Resumes
`resumes/generated/<company>_<role_slug>_resume.md` - Tailored resumes for specific job postings

## Resume Generation Workflow

The resume generation workflow uses a manual curation approach:
1. Review `results/application_queue.csv` for promising job postings
2. Use Obsidian clipper to extract clean markdown of job postings
3. Run `generate-resume` prompt which spawns isolated subagents per job posting
4. Each subagent produces a tailored resume optimizing for that specific posting's keywords

## MCP Tools

The workflows rely on MCP (Model Context Protocol) servers:

1. **Firecrawl MCP** - Web scraping and search (`firecrawl_search`, `firecrawl_scrape`)
   - Configured via VS Code settings or environment variables
   - Requires `FIRECRAWL_API_KEY`
   - Used by: ats-platform-search

2. **Chrome DevTools MCP** - Browser automation for job boards requiring JavaScript
   - Requires Chrome running with remote debugging: `./scripts/start-chrome-debug.sh`
   - Connects to `http://127.0.0.1:9222`
   - Used by: hiringcafe-job-search workflow

## Resume Generation Rules

When modifying resume templates or generation logic:

1. **Date format**: Use short month abbreviations only (`Jan`, `Sept`, not `January`, `September`)
2. **Word count**: Match reference resume (~450 words for single page)
3. **Projects section**: Compact single-line format, no tables or URLs
4. **No Summary section**: Omit to maximize space for achievements
5. **Template structure**: Follow `resumes/reference/template.docx` formatting

## Scoring Quick Reference

| Score | Classification | Action |
|-------|----------------|--------|
| 8-10 | Exceptional | Apply immediately |
| 6-7 | Strong | Apply |
| 4-5 | Moderate | Manual review |
| 0-3 | Disqualified | Skip |

Key boosters: Terraform (+2), Ansible (+2), AWS-focused (+2)
Key disqualifiers: Senior/Staff/Lead titles, GCP-only, non-remote, 24/7 on-call, Crypto/Blockchain/Web3, AI startups (<10K employees), "software development experience" requirements
