Run the ATS API scraper to discover infrastructure roles from curated company career pages, score them, and write qualified positions to the application queue.

The Python script handles all fetching, filtering, scoring, cooldown/ghost job detection, CSV writing, and effectiveness tracking. This workflow runs the script, analyzes the output, attempts to repair any broken slugs detected during the run (auto-disabling rows it can't repair and notifying the user), and reports results.

## Arguments

Optional `$ARGUMENTS` — override the default time filter. Examples:
- `past_day` — only jobs posted in the last 24 hours
- `past_2_days` — jobs posted in the last 48 hours (use to bridge weekend/Friday gaps)
- `past_week` — jobs posted in the last 7 days
- `past_month` — jobs posted in the last 30 days
- _(empty)_ — use the `time_filter` value from `config/config.yml`

## Pre-Execution

1. **Read configuration**:
   - Read `config/config.yml` to determine the default `search_config.time_filter`
   - If `$ARGUMENTS` is provided, use it as the time filter override
   - If empty, use the `time_filter` from config.yml (e.g., `past_day`)

   The scraper itself also consumes `target_roles.primary` + `target_roles.secondary`
   from the same file — the role names there become the title-matching regex used
   during filtering (see `build_target_roles_pattern` in `scripts/ats_scraper/filters.py`).
   To add or remove a role, edit config.yml only; no code change is needed.

## Execution

2. **Run the scraper**:
   ```
   .venv/bin/python -m scripts.ats_scraper.cli --verbose --posted-within {time_filter}
   ```
   Run this via the Bash tool with `run_in_background: true` (this scraper hits many companies/platforms and can take longer than the LinkedIn/Built In scrapers). Do not poll, sleep-loop, or check on it manually — the harness sends an automatic notification when the background command completes, and that notification delivers the full captured stdout/stderr. Continue with other work (or just wait) until that notification arrives, then proceed to step 3 using the captured output. Only fall back to `ScheduleWakeup` if you need to end the current turn before the notification arrives.

   The script will automatically:
   - Fetch jobs from all curated ATS platforms
   - Apply filters: date, title, location/remote, company exclusion, cooldown/ghost detection, description disqualifiers
   - Score all qualified positions using the regex scoring framework
   - Stage scored candidates (with full descriptions) to `results/ats_api_pending_review.json` for LLM review
   - Append per-platform and per-company stats to `results/tracking/data/ats_api_platform_effectiveness.csv` and `ats_api_company_effectiveness.csv`, then refresh the matching HTML dashboards in `results/tracking/`

   **Note:** The scraper does NOT write to `application_queue.csv` directly. That happens in step 6 after LLM review. (Use `--no-llm-review` to bypass LLM review and write directly to the CSV — only useful for testing.)

3. **Check for errors**:
   - If the scraper exits non-zero, read stderr and diagnose:
     - Import errors → fix the relevant `.py` file and re-run
     - HTTP errors (4xx, 5xx) → check URL construction in the platform module
     - JSON parse errors → check API response shape
   - If the same error persists after 2 fix attempts, stop and report to the user

4. **Scan for rate-limit signals** (even on successful exit):
   - Count occurrences of `failed after 3 retries` in stderr, grouped by platform (infer platform from the company name that preceded the error).
   - In `--verbose` output, flag any per-company elapsed time >5s on single-GET platforms (Ashby, Greenhouse, Rippling, Pinpoint, Recruitee) — these should normally complete in <1s, so >5s implies the retry backoff (2s+4s+8s = up to 14s) triggered at least once. Dayforce is a 2-call sequence (GET csrf + POST search) so 1–4s is normal there; flag only at >8s.
   - Workday and SmartRecruiters legitimately take longer (search + detail fan-out), so don't flag them on elapsed time alone — only on `failed after 3 retries`.
   - **Thresholds:**
     - 1 retry-exhaustion on a platform → transient, note but don't act.
     - 2+ retry-exhaustions on the same platform → that platform is rate-limiting. Recommend lowering its concurrency via `--max-workers-per-platform {platform}=N` on the next run (halve the current limit; see `PLATFORM_LIMITS` in `scripts/ats_scraper/cli.py` for current values).
     - 3+ slow single-GET companies on the same platform → soft signal; suggest watching it on subsequent runs.
   - Surface findings in the Rate Limit Signals section of the report.

## Slug Validation & Repair

5. **Detect and repair suspicious slugs.** This step kicks in only when this run produced one or more signals of a broken slug; otherwise skip it entirely.

   **Trigger conditions** (any one is enough to mark a company as suspicious):
   - `failed after 3 retries` in stderr attributed to a specific company (the scraper's `RuntimeError` when an API call exhausts retries — most often a 404 on a dead board).
   - The effectiveness report's `zero_fetched_non_prefiltered` flag for that company (0 fetched on Lever/Greenhouse/Ashby/Rippling/Recruitee/Dayforce across 2+ runs). Run `.venv/bin/python -m scripts.ats_scraper.effectiveness_report` to get this list — but only treat it as a trigger here; the broader effectiveness recommendations still go in the Reporting section.
   - **Do NOT** treat 0 fetched on Workday or SmartRecruiters as a trigger — those platforms title-filter at fetch time, so 0 fetched is the normal idle state, not a slug problem.

   **For each suspicious company**, attempt automatic repair using the slug validator:

   1. Probe with current platform + suggestions on the same platform:
      ```
      .venv/bin/python -m scripts.ats_slug_validator --company "{Company_Name}" --suggest-fixes --json
      ```
      If the validator returns `"status": "fixable"` with a `suggestion` field, you found a same-platform slug fix.

   2. If step 1 finds no fix, run cross-platform discovery using the current slug as the seed:
      ```
      .venv/bin/python -m scripts.ats_slug_validator --discover "{current_slug}" --discover-career-url "{Career_Page_URL}" --json
      ```
      If exactly one platform responds OK (other than the current one), use that as the candidate fix. If multiple respond OK, prefer in this order: Greenhouse, Ashby, Lever, Workday, SmartRecruiters, Rippling, Dayforce — and surface the alternatives in the report so the user can override.

   3. **Apply the fix**. Edit `config/company_targets_ats.csv` for the affected row:
      - For a same-platform slug change: update `ATS_Slug` and `Career_Page_URL` to the canonical hosted URL for the new slug.
      - For a cross-platform migration: update `ATS_Platform`, `ATS_Slug`, and `Career_Page_URL` together. For Workday, the slug is `{tenant}.{dc}` and the board name lives in the trailing path segment of the URL — make sure both align (see `_parse_workday` in `scripts/ats_scraper/config.py`).
      - Append a note to `Extraction_Notes` describing the change (e.g. `Slug corrected from 'X' to 'Y' on {date} via validator`) and update `Last_Validated` to today.
      - Re-probe the new slug to confirm before moving on:
        ```
        .venv/bin/python -m scripts.ats_slug_validator --company "{Company_Name}"
        ```

   4. **If no fix is found** (neither same-platform suggestions nor cross-platform discovery returned a working board), disable the row instead of leaving a broken slug in place:
      - Set `ATS_Platform` to `disabled` (lowercase — the scraper filters on `ats_platform.lower() == "disabled"`).
      - Set `URL_Status` to `broken`.
      - Append a note to `Extraction_Notes` (e.g. `Disabled {date} — no working board found across {N} probed platforms`) and update `Last_Validated` to today.

   5. After all CSV edits, regenerate the companion JSON so duplicate-detection stays in sync:
      ```
      .venv/bin/python -m scripts.curation_appender.rebuild_companion --verbose
      ```

   6. Collect every action taken into a structured list for the Slug Repair section of the report (see Reporting). Each entry should record company, original slug/platform, action taken (`fixed-same-platform` / `migrated-cross-platform` / `disabled`), and the new slug/platform (or `none` for disables).

   **Reusable script reference**: the validator lives at `scripts/ats_slug_validator/` and supports probes for Greenhouse, Ashby, Lever, SmartRecruiters, Rippling, Workday, Eightfold, Dayforce. Its `--discover` mode additionally probes iCIMS, BambooHR, Recruitee, Workable, and Jobvite so cross-platform migrations off-curated platforms can be detected even when we don't currently scrape them — in that case prefer disabling the row with a note about where the company moved to, rather than adding an unscraped platform.

## LLM Fuzzy Review

6. **Invoke the `ats-api-llm-review` agent** to apply fuzzy human-judgment review on staged candidates. The Python scraper handles cheap regex pre-filtering; the agent catches what regex misses (title typos like `lll` for `III`, unmapped non-US locations like `South Korea` or `Calgary`, subtle description signals).

   Skip this step ONLY if:
   - `--no-llm-review` was passed to the scraper (legacy mode, scraper already wrote the CSV)
   - `results/ats_api_pending_review.json` doesn't exist or is empty `[]` (no candidates survived regex filtering)

   Otherwise, invoke the agent:
   ```
   Agent(
     subagent_type: "ats-api-llm-review",
     prompt: "Review the staged ATS candidates at results/ats_api_pending_review.json. Read shared/scoring_framework.md, config/job_preferences.md, and config/exclusions.yml. Apply fuzzy disqualification rules (especially for non-US locations and title typos), re-score qualifying records using the full description text, write verdicts to /tmp/ats_api_review_verdicts.json, then invoke scripts/ats_scraper/queue_writer.py to append qualified rows to application_queue.csv. Return your final JSON summary."
   )
   ```

   The agent returns a JSON object with `qualified`, `disqualified`, and `written_to_queue` counts. Verify `qualified_count + disqualified_count == input_count` so no records were dropped.

   If the agent fails or returns malformed JSON: re-read `results/ats_api_pending_review.json` and retry once. If it fails again, report to the user with the error and recommend running with `--no-llm-review` as a fallback.

## Cooldown and Ghost Job Filters

The script automatically reads `job_search_log/applications.csv` (and `pipeline_events.csv`) to apply:

- **Cooldown filter** — skips positions where the SAME role at the SAME company was applied to within the past 60 days. Same-role scoped: a different role at the same company (DevOps vs SRE vs MLOps vs Platform Engineer) is NOT skipped. SRE ≈ Site Reliability Engineer; seniority modifiers (Sr/Lead/II/III) do not change role identity.
- **Ghost job detection** — skips positions where the same company posted the same role >60 days ago and the application has only the initial `applied + no_response` event (no recruiter contact, no later-stage events). These are suspected evergreen/ghost postings that never lead anywhere.

Use `--no-cooldown` to bypass both checks during testing.

## Scoring

The script applies the boosters, penalties, and hard disqualifiers defined in `shared/scoring_framework.md` (base 5, capped at 10). That document is the **sole source of truth** for scoring rules — refer to it for the full booster/penalty list and disqualifier triggers. The downstream `ats-api-llm-review` agent applies fuzzy versions of the same framework rules on the staged candidates.

Score threshold for CSV write: **≥ 4** (Moderate or better).

## Reporting

7. **Output a summary report** to the user:

```
## ATS API Search Complete — {date}

### Configuration
- Time filter: {time_filter}
- Companies scanned: {total_companies}
- Cooldown pairs active: {count from "Cooldown: N" line}
- Ghost job signals active: {count from "Ghost jobs: N" line}

### Rate Limit Signals
(Omit this section entirely if no retry-exhaustions and no slow single-GET companies.)

- Retry-exhaustions by platform: {platform: count, ...}
- Slow single-GET companies (>5s): {company (platform, elapsed), ...}
- Recommendation: {"none" | "lower {platform} concurrency to N on next run via --max-workers-per-platform {platform}=N" | "watch {platform} on next run"}

### Slug Repair Actions
(Omit this section entirely if no slug validation was triggered or no changes were made.)

Surface every action taken by the Slug Validation & Repair step. The user wants explicit notification on every disable so they can audit.

| Company | Original (Platform / Slug) | Action | New (Platform / Slug) | Notes |
|---------|----------------------------|--------|------------------------|-------|
| ... | ... | fixed-same-platform / migrated-cross-platform / disabled | ... | reason / probed alternatives |

Call out disables explicitly with a one-line summary above the table (e.g. *"Disabled 2 companies; both had no working board on any of the 13 probed platforms."*) so the user notices without scanning the full table.

### Filter Funnel
{paste the full filter funnel from CLI output}

### New Additions to Queue
| Company | Title | Score | Platform | Match Reasons |
|---------|-------|-------|----------|---------------|
| ... | ... | ... | ... | ... |

(or "No new qualified positions found" if none)

### LLM Review Disqualifications
Positions that passed the regex pre-filter but were caught by the LLM fuzzy review. List each with reason.

| Company | Title | URL | Reason |
|---------|-------|-----|--------|
| ... | ... | ... | ... |

(omit section entirely if no LLM disqualifications)

### Positions Needing Description Verification (Rippling)
| Company | Title | URL |
|---------|-------|-----|
| ... | ... | ... |

(or omit section if none)

### Per-Company Breakdown
{paste the per-company filter breakdown from CLI output}

### Effectiveness Signals
Run the effectiveness report script and use its JSON output to populate this section:
```
.venv/bin/python -m scripts.ats_scraper.effectiveness_report
```
Flag from the output:
- `never_qualified_3plus_runs`: companies with 0 qualified across 3+ runs (fetched > 0) — note as trend (removal only after 30+ runs)
- `zero_fetched_non_prefiltered`: companies with 0 fetched on Lever/Greenhouse/Ashby/Rippling/Recruitee across 2+ runs — these should already have been handled in step 5 (Slug Validation & Repair). If any still appear here after step 5, that indicates the validator's automatic repair did not run (e.g. effectiveness report was unavailable) or the company was added to the trigger set after the run; mention them so the user can re-run with explicit triggers.
- `removal_candidates_30plus_runs`: companies at the removal threshold — recommend removing from `config/company_targets_ats.csv`
- Ghost job candidates surfaced this run: recommend adding to `config/exclusions.yml` under # Ghost Jobs

**Important — 0 fetched on Workday and SmartRecruiters is expected.** These two platforms apply title-based filtering at fetch time inside the scraper (see `title_passes()` calls in `scripts/ats_scraper/platforms/workday.py` and `smartrecruiters.py`). The "Fetched" count for these platforms reflects only jobs whose titles already match target roles — so 0 fetched simply means no DevOps/Platform/SRE/Cloud/Infrastructure titles are currently posted, NOT a broken URL. Do not flag Workday/SmartRecruiters companies as structural issues based on 0 fetched alone. To verify a Workday URL is working, hit the API directly (e.g. `curl -X POST https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{board}/jobs -d '{"limit":5,"offset":0,"searchText":"","appliedFacets":{}}'`) and check `total > 0`.

**Important:** The scraper runs approximately once per day. Meaningful removal decisions require ~30 runs (~1 month of data). Do not recommend removing companies until they have 30+ runs with 0 qualified and active job postings. Only flag structural issues (0 fetched on non-pre-filtered platforms, wrong URLs) or note trends without recommending removal before that threshold.

### Recommendations
Based on this run and historical tracking:
1. Companies to consider removing (30+ runs, persistent zero qualification with active postings only)
2. Companies with structural issues that the validator did NOT auto-repair (e.g. validator was skipped or its discovery returned ambiguous results) — these need manual investigation
3. Any cooldown or ghost job patterns worth reviewing
```

## Error Recovery

| Error | Action |
|-------|--------|
| Script import error | Fix the .py file, re-run |
| HTTP 4xx/5xx | Check URL construction in platform module |
| 0 total fetched (any platform) | Check network, API availability |
| 0 fetched for a Workday/SmartRecruiters company | **Expected** — these platforms pre-filter by title. Do not treat as a structural issue. |
| 0 fetched for a Lever/Greenhouse/Ashby/Rippling/Recruitee/Dayforce company | Likely empty board or wrong board token. If `zero_fetched_non_prefiltered` fires (2+ runs at 0), the Slug Validation & Repair step (5) will attempt automatic discovery via `scripts.ats_slug_validator --discover` and either fix or disable the row. For Dayforce, slug is `clientNamespace:jobBoardCode`, e.g. `paradigm:CANDIDATEPORTAL`. |
| `failed after 3 retries` attributed to one company | Treat as a broken-slug signal in step 5 — run `scripts.ats_slug_validator --company "{Name}" --suggest-fixes --json`, then `--discover` if no same-platform fix exists. Fix the CSV or disable the row. |
| 100% title rejection | Verify filter patterns in `scripts/ats_scraper/filters.py` |
| Tracking CSV append error | Inspect `results/tracking/data/ats_api_*.csv`; the appender expects the header row to match `scripts/effectiveness_tracker/totals.py` schemas. Restore from git if corrupted. |
| `failed after 3 retries` on 1 company | Transient; note in Rate Limit Signals but no action needed |
| `failed after 3 retries` on 2+ companies on the same platform | That platform is rate-limiting; recommend halving its concurrency on the next run via `--max-workers-per-platform {platform}=N` |
| Per-company elapsed >5s on Ashby/Greenhouse/Rippling/Pinpoint/Recruitee | Retry backoff likely triggered; if 3+ companies on the same platform show this, flag for watching |
