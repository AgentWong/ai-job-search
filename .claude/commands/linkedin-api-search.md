Run the LinkedIn jobs-guest API scraper to discover infrastructure roles using LinkedIn's public unauthenticated search endpoint, score them, and write qualified positions to the application queue.

The Python script handles fetching (with rate limiting + UA rotation), filtering (title/company/location), cooldown checks, scoring, and staging. The `linkedin-llm-review` agent applies fuzzy human-judgment review before queue write.

This **replaced** the retired `linkedin-job-search` browser workflow (removed 2026-06-20). It is now the sole LinkedIn path, and it is:
- Cheaper on tokens (no LLM driving a browser)
- Faster (~5–8 min for 10 roles)
- Free of personal LinkedIn account risk (the guest API is unauthenticated)

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

   The scraper consumes `target_roles.primary` + `target_roles.secondary` from the same file. Each role name becomes a quoted keyword search on LinkedIn's guest API. To add or remove a role, edit config.yml only.

## Execution

2. **Run the scraper**:
   ```
   .venv/bin/python -m scripts.linkedin_scraper.cli --verbose --posted-within {time_filter}
   ```
   Run this via the Bash tool with `run_in_background: true` (the scraper typically takes 5-8 min). Do not poll, sleep-loop, or check on it manually — the harness sends an automatic notification when the background command completes, and that notification delivers the full captured stdout/stderr. Continue with other work (or just wait) until that notification arrives, then proceed to step 3 using the captured output. Only fall back to `ScheduleWakeup` if you need to end the current turn before the notification arrives.

   The script will automatically:
   - Search LinkedIn jobs-guest API for each target role (Full-time + sortBy=Date). Location follows `config/config.yml` `location`: remote mode uses the US geoId + `f_WT=2` (Remote); local mode uses `geoId=<linkedin_geo_id>` when set (else a free-text `location`, e.g. "Portland, Oregon") + `f_WT=1,2,3` (on-site/remote/hybrid) + `distance=<location.distance_miles>` (search radius in miles, verified honored).
   - Parse search-result cards and extract candidate URLs
   - Apply Phase 1 filters: senior titles, wrong role family, excluded companies, and the mode-aware location check (remote mode: non-US + non-remote; local mode: non-US + remote-handling, then a metro check). **The local metro check is radius-aware:** when `distance_miles` is set the geo-constrained search is trusted and any in-US, non-remote card is kept — so in-radius neighbors (e.g. Clarkston WA / Pullman around Portland, OR) survive instead of being dropped for not literally naming the configured city; the LLM-review pass prunes true outliers. With `distance_miles` unset/0 it falls back to a strict city/state-name match.
   - Apply cooldown check (deterministic exact-match against `job_search_log/applications.csv`)
   - **Phase 1b: cross-role dedup + spam removal.** Across all roles, group cards by normalized (company, title). If a pair appears 3+ times (e.g. same role spammed across multiple cities), drop every instance — premise: the duplication itself is the bad signal. For pairs appearing 2x (same job legitimately matched two role keywords), keep only the highest-priority match. Runs BEFORE the max_per_role cap so a single spammy company can't burn the cap.
   - Cap each role's survivors to `--max-per-role` (default 15) after dedup
   - Fetch full detail page for each surviving candidate (rate-limited, 5s + jitter between requests)
   - **Drop LinkedIn Easy Apply postings post-fetch.** Easy Apply is detected from the detail-page CTA button structure (no `offsite-apply-icon`, tracking name ends in `onsite`). The LLM review treats Easy Apply as a hard disqualifier (mass-applicant funnel / ghost-job signal), so dropping at the script tier avoids wasting review tokens.
   - Regex-score each posting using the same scoring framework as the ATS scraper
   - Stage all scored candidates to `results/linkedin_pending_review.json` for LLM review

   **Note:** The scraper does NOT write to `application_queue.csv` directly. That happens in step 4 after LLM review. (Use `--no-llm-review` to bypass LLM review and write directly to the CSV — only useful for testing.)

   **Defaults** (overridable via flags):
   - `--max-pages 3` — searches 3 pages per role (~30 cards)
   - `--max-per-role 15` — fetches at most 15 detail pages per role after filters + dedup
   - `--search-delay 3.0` — 3s between search-page requests (with ±25% jitter)
   - `--detail-delay 5.0` — 5s between detail-page requests (with ±25% jitter)
   - `--spam-threshold 3` — minimum (company, title) repeat count that triggers spam removal (min: 2)

3. **Check for errors**:
   - If the scraper exits non-zero, read stderr and diagnose:
     - `RateLimitError: Aborted after 3 consecutive 429s` → LinkedIn is rate-limiting this IP. Wait 30+ minutes before retrying. Do not retry immediately.
     - Network errors → check connectivity, retry once
     - Import errors → fix the relevant `.py` file and re-run
   - The script handles 429s with exponential backoff (5s → 30s → 120s) before aborting. If it aborts, partial results are still staged.

## LLM Fuzzy Review

4. **Invoke the `linkedin-llm-review` agent** to apply fuzzy human-judgment review on staged candidates. The Python scraper handles cheap regex pre-filtering; the agent catches what regex misses (title typos like `lll` for `III`, unmapped non-US locations, subtle description signals).

   Skip this step ONLY if:
   - `--no-llm-review` was passed to the scraper (legacy mode)
   - `results/linkedin_pending_review.json` doesn't exist or is empty `[]`

   Otherwise, invoke the agent:
   ```
   Agent(
     subagent_type: "linkedin-llm-review",
     prompt: "Review the staged LinkedIn candidates at results/linkedin_pending_review.json. Read shared/scoring_framework.md, config/job_preferences.md, and config/exclusions.yml. Apply fuzzy disqualification rules (especially for non-US locations and title typos), re-score qualifying records using the full description text, write verdicts to /tmp/linkedin_review_verdicts.json, then invoke scripts/ats_scraper/queue_writer.py to append qualified rows to application_queue.csv. Return your final JSON summary."
   )
   ```

   The agent returns a JSON object with `qualified`, `disqualified`, and `written_to_queue` counts. Verify `qualified_count + disqualified_count == input_count` so no records were dropped.

   If the agent fails or returns malformed JSON: re-read `results/linkedin_pending_review.json` and retry once. If it fails again, report to the user with the error and recommend running with `--no-llm-review` as a fallback.

## Reporting

5. **Output a summary report** to the user:

```
## LinkedIn API Search Complete — {date}

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
{table from rejection_breakdown dict — Senior title, Wrong role family, Excluded company, Non-US location, Non-remote, Cooldown, Spam (3+ identical postings), Cross-role duplicate, max_per_role cap, Easy Apply (LinkedIn)}

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
{paste the "Tracking: appended N rows to ..." one-line summary from the scraper's stdout. The CLI writes per-role found/qualified to `results/tracking/data/linkedin_api_role_effectiveness.csv` and refreshes `results/tracking/linkedin_api_role_effectiveness.html`.}
```

## Long-Term Performance Tracking

The scraper writes one row per role per run to a **dedicated** `linkedin_api_role` tracker (parallel to the ATS API scraper's dedicated trackers). Isolated from the shared `browser_role` tracker so trend data for this workflow doesn't average with browser linkedin / builtin / hiringcafe.

What gets tracked per row:
- `date` — run date
- `role` — role searched (e.g. "DevOps Engineer")
- `found` — total cards LinkedIn returned for that role this run
- `qualified` — count of records where the regex score is ≥ 4

The HTML dashboard computes rolling totals per role:
- Runs (number of times we've searched this role)
- Total found across all runs
- Total qualified
- Avg qualification rate (%)
- Latest-run rate trend (`>>>` above avg, `===` near avg, `<<<` below avg)
- Zero-result run count

Dashboard: `results/tracking/linkedin_api_role_effectiveness.html`
Raw CSV: `results/tracking/data/linkedin_api_role_effectiveness.csv`

**Note on the qualified count:** Same threshold (score ≥ 4) the browser workflow uses, so the two are directly comparable run-by-run. The downstream LLM review may further reject some, so actual queue additions are typically slightly lower than this number — but the tracker captures pre-LLM regex-qualified to stay deterministic across runs (mirrors the `ats-api-search` tracker semantics).

## Error Recovery

| Error | Action |
|-------|--------|
| `RateLimitError: Aborted after 3 consecutive 429s` | LinkedIn is rate-limiting this IP. Wait 30+ minutes before retrying. Do not retry immediately. |
| `RateLimitError: 429 backoff exhausted` | Same as above — wait, then retry. |
| Network error | Check connectivity, retry once |
| Empty card list across all roles | Possible LinkedIn HTML structure change. Compare a manual cURL against the parser in `scripts/linkedin_scraper/search.py`. |
| Empty description for all postings | Possible detail-page selector drift. Update `DESCRIPTION_SELECTORS` in `scripts/linkedin_scraper/detail.py`. |
| 0 staged candidates after Phase 1 | Filters may be too aggressive. Re-run with `--verbose --no-cooldown` to see per-role breakdown. |
| LLM agent returns malformed JSON | Re-read `results/linkedin_pending_review.json` and retry once. If it fails again, run with `--no-llm-review` to write directly to the CSV (skipping fuzzy review). |

## History: Replaced the Browser Workflow

This workflow **replaced** the retired `linkedin-job-search` browser workflow, removed 2026-06-20 along with its `browser-job-search` agent. That workflow drove a logged-in Chrome session via Chrome DevTools — high token cost, ~30+ min for 10 roles, and personal-account ban risk. The script-driven guest-API flow here is now the sole LinkedIn path: no auth, no browser, with IP-level 429 the only failure mode.
