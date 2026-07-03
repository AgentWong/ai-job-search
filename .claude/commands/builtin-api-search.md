Run the Built In jobs scraper to discover infrastructure roles using builtin.com's public unauthenticated search, score them, and write qualified positions to the application queue.

The Python script handles fetching (with rate limiting + UA rotation), filtering (title/company/location), cooldown checks, scoring, and staging. The `builtin-llm-review` agent applies fuzzy human-judgment review before queue write.

This **replaced** the retired `builtin-job-search` browser workflow (removed 2026-06-20). It is now the sole Built In path, and it is:
- Cheaper on tokens (no LLM driving a browser)
- Faster (~5–8 min for 10 roles)
- Free of browser-session overhead — Built In's public search is fully unauthenticated

## Arguments

Optional `$ARGUMENTS` — override the default time filter. Examples:
- `past_day` — only jobs posted in the last 24 hours
- `past_2_days` — jobs posted in the last 48 hours
- `past_week` — jobs posted in the last 7 days
- `past_month` — jobs posted in the last 30 days
- _(empty)_ — use the `time_filter` value from `config/config.yml`

## Pre-Execution

1. **Read configuration**:
   - Read `config/config.yml` to determine the default `search_config.time_filter`
   - If `$ARGUMENTS` is provided, use it as the time filter override
   - If empty, use the `time_filter` from config.yml

   The scraper consumes `target_roles.primary` + `target_roles.secondary` from the same file. Each role name becomes a quoted keyword search on Built In. To add or remove a role, edit config.yml only.

## Execution

2. **Run the scraper**:
   ```
   .venv/bin/python -m scripts.builtin_scraper.cli --verbose --posted-within {time_filter}
   ```
   Run this via the Bash tool with `run_in_background: true` (the scraper typically takes 5-8 min). Do not poll, sleep-loop, or check on it manually — the harness sends an automatic notification when the background command completes, and that notification delivers the full captured stdout/stderr. Continue with other work (or just wait) until that notification arrives, then proceed to step 3 using the captured output. Only fall back to `ScheduleWakeup` if you need to end the current turn before the notification arrives.

   The script will automatically:
   - Search builtin.com for each target role. Location follows `config/config.yml` `location`: remote mode uses the `/jobs/remote/` path (US); local mode uses the `/jobs/remote/hybrid/office` path plus `city`/`state` query params to constrain to the target metro (a `<city>-<state>` path slug does NOT filter on Built In — it returns nationwide results). Plus entry/junior/mid-level + 51–1000+ company sizes via URL path filters.
   - Parse search-result cards and extract candidate URLs
   - Apply Phase 1 filters: senior titles, wrong role family, excluded companies, and the mode-aware location check (remote mode: non-US + non-remote; local mode: outside the target city/state)
   - Apply cooldown check (deterministic exact-match against `job_search_log/applications.csv`)
   - **Phase 1b: cross-role dedup + spam removal.** Across all roles, group cards by normalized (company, title). If a pair appears 3+ times (e.g. same role spammed across multiple cities), drop every instance — premise: the duplication itself is the bad signal. For pairs appearing 2x (same job legitimately matched two role keywords), keep only the highest-priority match. Runs BEFORE the max_per_role cap so a single spammy company can't burn the cap.
   - Cap each role's survivors to `--max-per-role` (default 15) after dedup
   - Fetch full detail page for each surviving candidate (rate-limited, 3s + jitter between requests)
   - Parse JSON-LD `JobPosting` schema from each detail page (Builtin emits this for SEO — most stable extraction surface). Fall back to CSS selectors if the LD+JSON block is missing.
   - Regex-score each posting using the same scoring framework as the ATS scraper
   - Stage all scored candidates to `results/builtin_pending_review.json` for LLM review

   **Note:** The scraper does NOT write to `application_queue.csv` directly. That happens in step 4 after LLM review. (Use `--no-llm-review` to bypass LLM review and write directly to the CSV — only useful for testing.)

   **Defaults** (overridable via flags):
   - `--max-pages 3` — searches 3 pages per role
   - `--max-per-role 15` — fetches at most 15 detail pages per role after filters + dedup
   - `--search-delay 2.0` — 2s between search-page requests (with ±25% jitter)
   - `--detail-delay 3.0` — 3s between detail-page requests (with ±25% jitter)
   - `--spam-threshold 3` — minimum (company, title) repeat count that triggers spam removal (min: 2)

3. **Check for errors**:
   - If the scraper exits non-zero, read stderr and diagnose:
     - `RateLimitError: Aborted after 3 consecutive 429s` → builtin.com is rate-limiting this IP. Wait 30+ minutes before retrying. Do not retry immediately.
     - Network errors → check connectivity, retry once
     - Import errors → fix the relevant `.py` file and re-run
   - The script handles 429s with exponential backoff (5s → 30s → 120s) before aborting. If it aborts, partial results are still staged.

## LLM Fuzzy Review

4. **Invoke the `builtin-llm-review` agent** to apply fuzzy human-judgment review on staged candidates. The Python scraper handles cheap regex pre-filtering; the agent catches what regex misses (title typos like `lll` for `III`, unmapped non-US locations, subtle description signals).

   Skip this step ONLY if:
   - `--no-llm-review` was passed to the scraper (legacy mode)
   - `results/builtin_pending_review.json` doesn't exist or is empty `[]`

   Otherwise, invoke the agent:
   ```
   Agent(
     subagent_type: "builtin-llm-review",
     prompt: "Review the staged Built In candidates at results/builtin_pending_review.json. Read shared/scoring_framework.md, config/job_preferences.md, and config/exclusions.yml. Apply fuzzy disqualification rules (especially for non-US locations and title typos), re-score qualifying records using the full description text, write verdicts to /tmp/builtin_review_verdicts.json, then invoke scripts/ats_scraper/queue_writer.py to append qualified rows to application_queue.csv. Return your final JSON summary."
   )
   ```

   The agent returns a JSON object with `qualified`, `disqualified`, and `written_to_queue` counts. Verify `qualified_count + disqualified_count == input_count` so no records were dropped.

   If the agent fails or returns malformed JSON: re-read `results/builtin_pending_review.json` and retry once. If it fails again, report to the user with the error and recommend running with `--no-llm-review` as a fallback.

## Reporting

5. **Output a summary report** to the user:

```
## Built In API Search Complete — {date}

### Configuration
- Time filter: {time_filter}
- Roles searched: {count from CLI summary}
- Cooldown pairs active: {count from "Cooldown: N" line}

### Search Funnel
- Total cards found: {total_cards_found}
- After Phase 1 filters: {total_after_filters}
- After cooldown: {derived: filters - cooldown skips}
- Detail-fetched: {total_fetched}
- Staged for LLM review: {len(pending_records)}

### Rejection Breakdown
{table from rejection_breakdown dict — Senior title, Wrong role family, Excluded company, Non-US location, Non-remote, Cooldown, Spam (3+ identical postings), Cross-role duplicate, max_per_role cap}

### Spam Removal
{If `Spam (3+ identical postings)` > 0 in rejection_breakdown, list each spam pair the scraper printed. Pull from the "Spam removal" stdout block. Omit section if 0.}

| Company | Title | Postings Dropped |
|---------|-------|------------------|
| ... | ... | ... |

### Per-Role Results
| Role | Cards Found | After Filters | Detail-Fetched |
|------|-------------|---------------|----------------|
| ... | ... | ... | ... |

### New Additions to Queue
| Company | Title | Score | Match Reasons |
|---------|-------|-------|---------------|
| ... | ... | ... | ... |

(or "No new qualified positions found" if none)

### LLM Review Disqualifications
Positions that passed the regex pre-filter but were caught by the LLM fuzzy review. List each with reason.

| Company | Title | URL | Reason |
|---------|-------|-----|--------|
| ... | ... | ... | ... |

(omit section if no LLM disqualifications)

### Rate Limit / Fetch Errors
{paste fetch_errors list — usually empty if the run completed cleanly}

### Effectiveness Tracker
{paste the "Tracking: appended N rows to ..." one-line summary from the scraper's stdout. The CLI writes per-role found/qualified to `results/tracking/data/builtin_api_role_effectiveness.csv` and refreshes `results/tracking/builtin_api_role_effectiveness.html`.}
```

## Long-Term Performance Tracking

The scraper writes one row per role per run to a **dedicated** `builtin_api_role` tracker (parallel to the LinkedIn and ATS API scrapers' dedicated trackers). Isolated from the shared `browser_role` tracker so trend data for this workflow doesn't average with browser linkedin / builtin / hiringcafe.

What gets tracked per row:
- `date` — run date
- `role` — role searched (e.g. "DevOps Engineer")
- `found` — total cards Built In returned for that role this run
- `qualified` — count of records where the regex score is ≥ 4

The HTML dashboard computes rolling totals per role:
- Runs (number of times we've searched this role)
- Total found across all runs
- Total qualified
- Avg qualification rate (%)
- Latest-run rate trend (`>>>` above avg, `===` near avg, `<<<` below avg)
- Zero-result run count

Dashboard: `results/tracking/builtin_api_role_effectiveness.html`
Raw CSV: `results/tracking/data/builtin_api_role_effectiveness.csv`

**Note on the qualified count:** Same threshold (score ≥ 4) the browser workflow uses, so the two are directly comparable run-by-run. The downstream LLM review may further reject some, so actual queue additions are typically slightly lower than this number — but the tracker captures pre-LLM regex-qualified to stay deterministic across runs (mirrors the `linkedin-api-search` and `ats-api-search` tracker semantics).

## Error Recovery

| Error | Action |
|-------|--------|
| `RateLimitError: Aborted after 3 consecutive 429s` | builtin.com is rate-limiting this IP. Wait 30+ minutes before retrying. Do not retry immediately. |
| `RateLimitError: 429 backoff exhausted` | Same as above — wait, then retry. |
| Network error | Check connectivity, retry once |
| Empty card list across all roles | Possible Builtin HTML structure change. Compare a manual cURL against the parser in `scripts/builtin_scraper/search.py` (it tries `[data-id="job-card"]` then falls back to `a[href*="/job/"]`). |
| Empty description for all postings | Possible LD+JSON shape change OR detail selector drift. Inspect one detail-page response and update `_extract_ld_json` or `DESCRIPTION_SELECTORS` in `scripts/builtin_scraper/detail.py`. |
| 0 staged candidates after Phase 1 | Filters may be too aggressive. Re-run with `--verbose --no-cooldown` to see per-role breakdown. |
| LLM agent returns malformed JSON | Re-read `results/builtin_pending_review.json` and retry once. If it fails again, run with `--no-llm-review` to write directly to the CSV (skipping fuzzy review). |

## History: Replaced the Browser Workflow

This workflow **replaced** the retired `builtin-job-search` browser workflow, removed 2026-06-20 along with its `browser-job-search` agent. That workflow drove Built In through a Chrome DevTools session and parsed descriptions from drift-prone CSS selectors. The script-driven flow here is now the sole Built In path: it hits the public API directly and parses descriptions from stable JSON-LD.
