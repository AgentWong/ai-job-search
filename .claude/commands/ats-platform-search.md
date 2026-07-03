# ATS Platform Search Workflow

Search approved ATS job boards for infrastructure roles using **Python-driven
Firecrawl search** (`scripts.ats_platform_search.cli`). Job boards, roles, and
location mode are defined in `config/config.yml`.

---

## Architecture (Option A — Python-driven search)

The deterministic half of the workflow runs in Python; only judgment (scoring)
runs in an LLM subagent. The raw Firecrawl payload **never enters any LLM
context** — Python writes it straight to disk.

```
Orchestrator: clean cache → run Python search (one role tier) → read SMALL summary
    ↓
Python (scripts.ats_platform_search.cli --tier <t>):
    FOR each query: Firecrawl /v2/search (scrapeOptions preserved, ~2cr/10)
        → write q{NN}_raw.json verbatim   (offload — no LLM ever reads this)
        → POST /v2/search/{id}/feedback   (refund 1 credit; visible success/fail)
        → regex pre-filter (scripts.ats_platform_filter.filters) — incl. non-US
          (title/URL/snippet) + dead/expired/no-JD listing health
        → stage kept (full markdown + board/role attribution) into ONE review_batch_<tier>_01.json
    → write search_summary_<tier>.json  (small: counts, attribution, batch paths — NO markdown)
    ↓
Orchestrator: dispatch a SINGLE ats-platform-review subagent for the tier's batch
    → it scores every kept candidate from the full description (reads scoring
      configs once), returns a small counts summary; rows go to its verdict file
    ↓
Orchestrator: aggregate qualified → fuzzy-check → scripts.job_queue.cli append → progress log
    ↓
If total_qualified < target: repeat for the secondary role tier
    ↓
Orchestrator: final report → effectiveness trackers (ats_role, ats_board)
```

**Why this shape:** search is deterministic I/O (Python); scoring is
rubric-against-prose judgment (LLM). See
[docs/ats-platform-search-token-regression-assessment.md](../../docs/ats-platform-search-token-regression-assessment.md)
§6 "Option A" for the full rationale (it replaced an LLM search subagent that
re-serialized the entire raw payload, doubling cache-read cost).

### 🧱 Context discipline (read this — it is the whole point)

The orchestrator's context must stay small. Enforce ALL of these:

1. **NEVER `Read` a markdown-bearing file:** `q{NN}_raw.json` and
   `review_batch_*.json` hold full job-page markdown. Reading even one can add
   tens of thousands of tokens. The only files you read are
   `search_summary_<tier>.json` and `review_verdict_<tier>_*.json` (both small —
   counts and scored rows, no markdown).
2. **Review subagents return ONLY a counts summary** (`{verdict_file, batch_file,
   input_count, qualified_count, disqualified_count}`). The scored rows are
   written by each subagent to its `verdict_file`. Do not ask them to return rows.
3. **NEVER paste raw JSON into your reply to the user.** Not subagent output, not
   summary files, not positions files. Your visible output is the report tables
   and short status lines only. Build tables by reading the small verdict files,
   not by echoing JSON.
4. Hand large data between steps via **files + paths**, never via your own
   context. When you must transform rows, do it with the Write tool to a temp
   file, then hand the path to the next CLI.

---

## Arguments

Optional `$ARGUMENTS` — override the time filter window. One of:
`past_day | past_2_days | past_week | past_month | past_year`. If empty, the
Python script uses `search_config.time_filter` from `config/config.yml`.

---

## Pre-Run: Clean Cache Directory

Delete leftover artifacts from the previous run (pre-run, so the last run's
debug artifacts survive for inspection):

```bash
.venv/bin/python scripts/clear_ats_cache.py
```

---

## Pre-Execution: Load Configuration

Read `config/config.yml` for the two values the **orchestrator** needs:
- `search_config.target_positions` — early-exit threshold (default 40).
- `location` mode — only to label the progress/report header. The Python script
  reads boards, roles, location, and the time filter itself; you do not rebuild
  the query queue.

Initialize the progress file `results/ats-search-progress.md`:
```
# ATS Search Progress — [DATE]

## Configuration
- Time window: [$ARGUMENTS or config time_filter]
- Target positions: [target_positions]
- Location mode: [remote-US | local <city,state>]

## Phase Log
```

---

## Stage 1: Search + Review (per role tier)

Run this block first for `--tier primary`. Then, **only if**
`total_qualified < target_positions`, run it again for `--tier secondary`.

In local mode (`location.remote: false`) the `--tier secondary` run also covers the
`local_only` roles (Systems Administrator, Systems Engineer, ...) — the query
builder folds them into the secondary OR-group automatically, so no extra step or
tier is needed. In remote mode they're skipped entirely.

### 1.1 Run the Python search (one tier)

```bash
.venv/bin/python -m scripts.ats_platform_search.cli --tier <primary|secondary> \
    [--time-window $ARGUMENTS]
```

Pass `--time-window` only if `$ARGUMENTS` is non-empty. The script searches every
board for that role tier, writes per-query raw/filtered files, refunds a credit
per query, and stages kept candidates into `review_batch_<tier>_*.json`.

**Timing / timeout.** Bundled full-markdown scrapes can take a few minutes. Use a
generous Bash timeout (e.g. 600000 ms). If the call times out, re-run the same
command with `--concurrency 8`, or run it in the background and wait for it. The
script is safe to re-run (it overwrites the tier's files); credits already
refunded are idempotent.

Capture stdout. It prints: found→kept/discarded counts, refund summary, batch
count. If it prints `DAILY CAP REACHED`, note it in the report (refunds paused
for the UTC day — not an error).

### 1.2 Read the small summary

Read `results/ats_platform_cache/search_summary_<tier>.json`. It contains:
- `queries[]` — per-query `search_id`, `credits_used`, `results_found`, `kept`,
  `discarded`, `by_reason`, `refund` status, `error`.
- `totals`, `by_board` (`{queries, found, kept}`), `by_role` (`{found, kept}`).
- `review_batches` — list of batch file paths to score.
- `feedback` — `{refunded, failed, credits_refunded, daily_cap_reached}`.

If a query has a non-null `error`, warn the user (query number + board + error)
and continue — do NOT retry.

**Carry `by_board.found` / `by_role.found` forward** — these are the
deterministic `found` counts for effectiveness tracking (Stage 3). You will only
get `qualified` counts from the review subagents.

### 1.3 Dispatch the review subagent (single)

The Python search stages ALL kept candidates into ONE batch file
(`review_batch_<tier>_01.json`) by default, so dispatch **exactly one**
`ats-platform-review` subagent for the tier.

> **Why one, not parallel-per-batch.** A single subagent reads the four scoring
> configs (`scoring_framework.md` ~532 lines, `exclusions.yml`,
> `job_preferences.md`, `config.yml`) **once**. N parallel subagents would each
> re-read all four — and prompt caching does NOT rescue this, since every
> subagent has its own context, so those config reads are paid per subagent, not
> shared. On a `past_2_days` run that often stages only a handful of items, that
> redundant config-reading dominates the token cost. One subagent is the
> efficient default; the marginal wall-clock from sequential scoring is small at
> this volume.

`summary.review_batches` normally has ONE path. Derive its verdict sibling by
replacing `review_batch_` → `review_verdict_` (e.g.
`…/review_verdict_primary_01.json`). Dispatch a single subagent:

```
batch_path   = review_batches[0]
verdict_path = batch_path with "review_batch_" → "review_verdict_"
result = Agent(subagent_type: "ats-platform-review",
    prompt: "Score the staged ATS platform-search candidates in <batch_path>.
        Write your full verdict (qualified + disqualified) to <verdict_path>.
        Read shared/scoring_framework.md (full), config/exclusions.yml,
        config/job_preferences.md, and config/config.yml location. Apply fuzzy
        disqualifiers (cite a Category + trigger), re-score qualifying records
        from description_full, threshold >= 4. Pass job_board, source_domain,
        and matched_role through UNCHANGED on every qualified entry. Return ONLY
        your small counts summary — NOT the rows.")
```

The subagent returns ONLY `{verdict_file, batch_file, input_count,
qualified_count, disqualified_count}` (the rows are in its verdict file). Verify
`qualified_count + disqualified_count == input_count`; if it returns malformed
JSON or never wrote its verdict file, re-dispatch it once, then skip it (note in
report). Do NOT ask the subagent to return the rows inline.

> **Large-run exception (rare).** `review_batches` has more than one path only
> when the search was run with `--review-batch-size N` (N>0) to split an
> unusually large pool. In that case dispatch one subagent PER batch in parallel
> (up to 16) and wait for all — Stages 1.4–1.5 already aggregate across multiple
> verdict files, so no other step changes.

### 1.4 Write qualified to the queue

The qualified rows live in `review_verdict_<tier>_*.json` (small — scored rows,
**no markdown**; safe to read). Build ONE positions file from them WITHOUT
echoing anything to the user:

- Read each `review_verdict_<tier>_*.json` this tier produced.
- Concatenate their `qualified` arrays.
- Use `scripts/write_json.py` to create `/tmp/ats-<tier>-<unix-ts>.json` as
  `{ "positions": [ ...all qualified entries... ] }` (extra keys like
  `job_board` / `source_domain` / `matched_role` are harmless — the queue writer
  keeps only its own columns):

```bash
.venv/bin/python scripts/write_json.py /tmp/ats-<tier>-<ts>.json '<json-string>'
```

**Cooldown pre-check**, then **append**:
```bash
.venv/bin/python -m scripts.job_queue.cli fuzzy-check \
    --positions /tmp/ats-<tier>-<ts>.json \
    --output    /tmp/ats-<tier>-cooldown-<ts>.json
```
Read that small output. `append` auto-skips `exact_matches` deterministically
(now robust to company-name spacing variants like "BlueCross"/"Blue Cross" — the
shared `normalize_company` collapses internal whitespace). Your only job is the
`fuzzy_candidates` list — for each, judge whether `position.title` is the SAME
role function as any role in `company_recent_applications` (SRE ≈ Site
Reliability Engineer; strip seniority; Platform ≈ Infrastructure Engineer; do
NOT collapse different families like DevOps ≠ Data Engineer). For SAME-role
candidates, remove them from the positions file (rewrite with Write) and record
the skip.

```bash
.venv/bin/python -m scripts.job_queue.cli append \
    --positions /tmp/ats-<tier>-<ts>.json \
    --source-track "ats-platform"
```
The script dedups against `results/application_queue.csv` and prints:
`Added: N | Already applied skipped: K | Duplicates skipped: M | Path: ...`

### 1.5 Update running stats + progress

- `total_qualified += sum(qualified_count across batches)` (from the 1.3 summaries).
- For per-board/per-role `qualified`: group this tier's qualified rows (from the
  verdict files) by `source_domain` and `matched_role` and count each. Merge into
  your running `stats.by_board[domain].qualified` / `stats.by_role[role].qualified`.
- Merge `found` and `queries` from the summary's `by_board`/`by_role`.

Append a phase summary to `results/ats-search-progress.md`:
```
### Phase <tier> — <N> queries
- Found: X, Kept (pre-filter): Y, Qualified (score>=4): Z, Written: <Added>, Dupes: <Duplicates>
- Refunds: <refunded> ok / <failed> failed
- Running total: [total_qualified] qualified
```

**Then decide Phase 2:** if `tier == primary` and `total_qualified <
target_positions`, repeat Stage 1 with `--tier secondary`. Otherwise stop
searching.

**Dedup:** handled by `scripts.job_queue.cli append`. The orchestrator keeps no
dedup set of its own.

---

## Stage 2: Final Report

Append to `results/ats-search-progress.md`:
```
## Final Summary
- Tiers run: [primary | primary+secondary]
- Total results scanned: X         (sum of by_board.found)
- Total kept (pre-filter): K
- Total qualified (score>=4): Y
- Written to CSV: Z                 (sum of Added)
- Duplicates skipped: W             (sum of Duplicates skipped)
- Cooldown-skipped (exact + fuzzy): C
- Credits refunded: R
- Status: COMPLETE / PARTIAL
```

Output to user:

```
## ATS Platform Search Complete — [DATE]

### Search Summary
- Tiers run: X
- Total results scanned: A
- Pre-filter kept: K (regex dropped A−K: senior/wrong-role/crypto/non-US/excluded)
- Qualified positions (score ≥ 4): B
- Application-ready (score 6+): C  |  Review needed (score 4-5): D
- Credits refunded this run: R (failed refunds: F)

### Effectiveness by Role
| Role | Found | Qualified | Rate |
...

### Effectiveness by Job Board
| Job Board | Queries | Found | Qualified | Rate |
...

### New Additions to Queue
| Company | Title | Score | Job Board | Key Matches |
...

### Cooldown Skips
*Omit if none.*
| Company | New Title | Matched Prior Role | Date Applied | Match Type |
*Match Type is `exact` (append's Already-applied skip) or `fuzzy-llm`.*

### LLM Review Disqualifications
*Positions that passed the regex pre-filter but the review subagent rejected.*
*Build this from the `disqualified` arrays in the `review_verdict_<tier>_*.json`
files (small, no markdown) — not from any subagent reply.*
| Company | Title | URL | Reason (Category + trigger) |
...

### Exclusions Summary (regex pre-filter)
{the summary's totals.by_reason — senior_title, wrong_role_title, non_us_title, listing_page, crypto_*, excluded_company, ... — as a short line, NOT raw JSON}

### Duplicates Skipped: X
```

> Reminder: render these as tables/lines. Do NOT paste the verdict files,
> summary files, or positions files verbatim into your reply.

---

## Stage 3: Update Effectiveness Tracking

Unchanged mechanics — the orchestrator writes two JSON payloads and invokes the
tracker CLI twice. `found` comes from the Python summary's `by_board`/`by_role`;
`qualified` comes from your aggregation of the review subagents' output.

### 3.1 Role stats
Aggregate into a list of `{"role": "...", "found": N, "qualified": M}`. Write
via `scripts/write_json.py` (avoids heredoc prompts):
```bash
.venv/bin/python scripts/write_json.py /tmp/ats-role-stats-<ts>.json '{"rows": [...]}'
.venv/bin/python -m scripts.effectiveness_tracker.cli append \
    --tracker ats_role --rows /tmp/ats-role-stats-<ts>.json \
    --progress-log results/ats-search-progress.md
```

### 3.2 Board stats
Aggregate into `{"board": "...", "queries": Q, "found": N, "qualified": M}`
(one row per source domain — bundled-secondary contributes a row per domain).
Write via `scripts/write_json.py`:
```bash
.venv/bin/python scripts/write_json.py /tmp/ats-board-stats-<ts>.json '{"rows": [...]}'
.venv/bin/python -m scripts.effectiveness_tracker.cli append \
    --tracker ats_board --rows /tmp/ats-board-stats-<ts>.json \
    --progress-log results/ats-search-progress.md
```

Relay each script's one-line stdout. `--progress-log` is accepted but a no-op —
keep it plumbed for future use.

---

## Error Handling

| Error | Action |
|-------|--------|
| Python search exits non-zero | Read stderr. Import error → fix the .py and re-run. Auth error (`FIRECRAWL_API_KEY not found`) → tell the user the key is missing from env and `~/.claude.json`. |
| Single query has `error` in summary | Expected occasionally — warn (query# + board + error), continue. NO retry. |
| `feedback.failed` > 0 | Refund(s) failed — note in report. If ALL refunds fail run-over-run, the undocumented feedback endpoint likely drifted; switch to MCP `firecrawl_search_feedback` (Option A′) by calling it from the orchestrator with each query's `search_id`. |
| All queries return 0 results | ABORT with a diagnostic report (check network / Firecrawl status). |
| Review subagent returns malformed JSON | Re-dispatch that one batch once; then skip it (note in report). |
| `< 5` qualified after both tiers | Report as partial success. |
| `scripts.job_queue.cli append` non-zero | Log stderr, keep the temp JSON, continue. |
| `scripts.effectiveness_tracker.cli append` non-zero | Log stderr, keep the temp JSON, skip that tracker. |
| Search call times out | Re-run with `--concurrency 8`, or run in background and wait. |
