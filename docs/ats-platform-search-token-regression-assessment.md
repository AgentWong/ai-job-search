# ATS Platform Search — Token-Cost Regression Assessment

**Status:** IMPLEMENTED (Option A, 2026-06-02). Diagnosis below retained for
history. See "Implementation" note directly under the TL;DR.
**Date:** 2026-06-02
**Context:** The `feat/workflow_efficiency` branch added a pre-filter step intended
to cut token cost. It made the workflow *more* expensive. This documents the
root cause, debunks the first proposed fix, records the empirical behavior of the
harness "blob" offload, and lays out the candidate architectures with trade-offs.

Related: [llm-deterministic-offload-strategy.md](llm-deterministic-offload-strategy.md)
(the abstract pattern this is an application of), [workflow-ats-platform-search.md](workflow-ats-platform-search.md).

---

## TL;DR

- The "efficiency" change (commit `09552b9`, Jun 1) added a step ordering each
  search subagent to **Write the entire raw Firecrawl JSON verbatim** to
  `q{N}_raw.json` so a Python pre-filter could read it. That re-serialization +
  the raw payload sitting in subagent context is what regressed cost.
- Measured impact: **$11.16 → $15.18 per run (+36%)**, driven mostly by
  **cache-read tokens doubling (7.06M → 15.97M)**.
- The first proposed fix — "give `firecrawl_search` a static output filename" —
  **is not possible.** The MCP tool has no output-file parameter. The
  "semi-random file" is the Claude Code **harness** offloading an oversized tool
  result, not Firecrawl writing anything.
- The credit economics are real and must be preserved: **search+scrape bundled =
  2 credits / 10 results; individual `firecrawl_scrape` = 1 credit each.** So any
  fix that drops `scrapeOptions` and re-scrapes is a bad trade and is rejected.
- The harness blob is **size-gated** (only ~7 of ~15 non-empty queries produced
  one last run), carries **no query identifier**, but is **clean parseable JSON**.
  This is the key constraint on the "Python consolidates the blobs" idea.
- The cleanest fix that preserves credits **and** removes the LLM from the data
  path: have **Python call Firecrawl `/v2/search` directly with `scrapeOptions`
  preserved** (identical credit cost), write `raw`+`filtered` itself, and let a
  review subagent score only `kept`.

---

## Implementation (Option A — landed 2026-06-02)

Built and verified live. New code:

- **`scripts/ats_platform_search/`** — `firecrawl_client.py` (direct `/v2/search`
  + `/v2/search/{id}/feedback` refund; key read from env or `~/.claude.json`,
  never hard-coded), `query_builder.py` (query queue from `config.yml`, plus the
  deterministic board/role attribution the LLM used to do), and `cli.py` (runs
  one role tier: search → write `q{NN}_raw.json` verbatim → refund → regex
  pre-filter → stage `review_batch_<tier>_*.json` + a small
  `search_summary_<tier>.json`).
- **`.claude/agents/ats-platform-review.agent.md`** — scores one batch from the
  full markdown, returns qualified/disqualified JSON (does not write the queue).
- **`.claude/commands/ats-platform-search.md`** — rewritten orchestrator: run
  Python per tier, read the small summary, dispatch one review subagent per
  batch, write the queue via the existing `scripts.job_queue.cli` path, then the
  unchanged effectiveness trackers + benchmark.
- **`scripts/ats_platform_filter/cli.py`** — normalization now also accepts the
  `data.web` shape (Open Question 5).

Resolved open questions: **(1)** request + feedback bodies pinned down live (see
§8.1 below — both confirmed against the real API); **(2)** search runs in one
Python call per tier with a bounded `ThreadPoolExecutor` (the same house pattern
as `scripts/ats_scraper/cli.py`, not an asyncio reimpl of the agent SDK fan-out);
**(3)** a small pool — one review subagent per `--review-batch-size` batch (default
15) — so `scoring_framework.md` is read a few times, not 20×; **(4)** the
`q{NN}_raw.json` / `q{NN}_filtered.json` contract is preserved, just written by
Python; **(5)** done. **(6)** Verify-the-win: re-run `/ats-platform-search` and
check the per-workflow usage percentage in Claude Code (target: cache_read back
to ~7M, cost under ~$11).

The legacy `firecrawl-job-search` search subagent is retained only for
`ats-platform-validate`.

### Post-launch fixes (first live run, 2026-06-02)

The first real `/ats-platform-search` run cut token usage but surfaced three
issues, all now fixed (regression tests in `tests/test_ats_platform_search.py`):

1. **Cooldown miss — company-name spacing.** "Blue Cross Blue Shield of
   Tennessee" (rediscovered) didn't match the logged "BlueCross BlueShield of
   Tennessee" applied a week earlier, so it was re-queued. `normalize_company`
   (shared by every workflow's cooldown/dedup) now collapses internal whitespace,
   so compound-word variants share one key. The deterministic `append` cooldown
   now catches it even if the LLM fuzzy-check doesn't.
2. **Junk row — Workday board listing page.** `bcbst.wd1.myworkdayjobs.com/External`
   (title "Search for Jobs", 15KB of listing markdown, no JD) was scored and
   queued at 4 with a fabricated "HIPAA -1". The regex pre-filter now drops
   Workday URLs with no `/job/` segment (`listing_page`), and the review agent's
   no-description fallback is forbidden from inventing description-based penalties.
3. **Orchestrator context bloat / JSON leaking to chat.** Review subagents now
   WRITE their verdict to `review_verdict_<tier>_*.json` and return only a counts
   summary; the orchestrator reads those small (markdown-free) files, and the
   command now hard-bans reading `q*_raw.json` / `review_batch_*.json` and pasting
   raw JSON into the reply. (The review agent gained the `Write` tool for this.)

---

## 1. The symptom

Measured from the per-session token/cost benchmark in use at the time (since
retired in favor of Claude Code's built-in per-workflow usage percentage),
`ats-platform-search` rows. Columns: `…,input_tokens,output_tokens,cache_write_5m,cache_write_1h,cache_read,est_cost_usd`.

| Run | Relative to change | output | cache_read | **cost** |
|---|---|---|---|---|
| 2026-05-30 | before | 103,160 | 10,534,522 | $13.28 |
| 2026-06-01 12:16 | before | 102,873 | 7,062,762 | **$11.16** |
| 2026-06-02 12:15 | **after** | 137,256 | 15,972,812 | **$15.18** |

Commit `09552b9` ("pre-filtering and cache management") landed Jun 1 20:08 — between
the 06-01 run (before) and the 06-02 run (after).

Cost decomposition of the regressed run (Sonnet pricing):

| Component | Tokens | $ | Share |
|---|---|---|---|
| cache_write_5m | 1,678,555 | $6.29 | 41% |
| cache_read | 15,972,812 | $4.79 | 32% |
| output | 137,256 | $2.06 | 14% |
| cache_write_1h | 330,780 | $1.98 | 13% |
| input | 17,078 | $0.05 | <1% |

The delta vs the prior run is **+$4.02**, of which **+$2.67 is cache_read alone**
(7.06M → 15.97M tokens, +126%). Cache-read cost = the size of the context that
gets re-read from cache on every subsequent tool call within each subagent. A
firecrawl-job-search subagent makes ~10–22 tool calls per the run logs, so any
large blob held in its context is paid for ~10–22 times over.

---

## 2. Root cause

The pre-filter change added Steps 1–4 to
[.claude/agents/firecrawl-job-search.agent.md](../.claude/agents/firecrawl-job-search.agent.md)
(lines ~113–143):

> **Step 1 — Save raw results.** Use the Write tool to save the complete search
> response to `results/ats_platform_cache/q{N}_raw.json` … verbatim.

So the per-query subagent now:

1. Calls `firecrawl_search` (with `scrapeOptions: {formats:["markdown"], onlyMainContent:true}`, `limit: 100`) → returns full page markdown for every result.
2. If large, the harness offloads that result to a blob file and hands the
   subagent a reference.
3. **Step 1 forces the subagent to reproduce that entire JSON as the content of a
   Write call** → to do that it must pull the blob back into its own context, then
   emit it as output tokens.
4. Bash runs the Python pre-filter over `q{N}_raw.json`.
5. Subagent reads `q{N}_filtered.json` (kept only) and scores.

The intent was right — the LLM should score only `kept`, not all results. But the
implementation **added a verbatim re-serialization of all raw results** (output
tokens) and **kept the full raw payload resident in the subagent's context**
(cache-read tokens × every later tool call). The savings on the scoring side were
swamped by the new serialization + context cost.

This is a textbook violation of the project's own
[offload strategy](llm-deterministic-offload-strategy.md): the LLM is reading a
large dataset and rewriting it. The data path should never go through the LLM.

---

## 3. Why "give `firecrawl_search` an output filename" can't work

Verified against the live MCP tool schema. `firecrawl_search` accepts:
`query`, `limit`, `tbs`, `location`, `scrapeOptions`, `sources`,
`includeDomains`/`excludeDomains`, and scrape-tuning fields. **There is no
`outputFile` / `output` / `outputPath` parameter.** You cannot instruct the tool
to write to disk.

The file at
`~/.claude/projects/<proj>/<session>/tool-results/mcp-firecrawl-firecrawl_search-<ts>.txt`
is created by the **Claude Code harness**, which offloads oversized tool results
to disk and gives the model a reference instead of inlining the bytes. Firecrawl
is not choosing that path and has no knowledge of it. So the proposed mechanism
targets the wrong layer.

The *instinct* behind the proposal — "the search result should land on disk
without the LLM re-serializing it" — is correct. It just has to be achieved a
different way (Section 6).

---

## 4. The credit constraint (why we keep search+scrape bundled)

Firecrawl billing:

- **Bundled search+scrape:** `firecrawl_search` with `scrapeOptions` ≈ **2 credits
  per 10 results** (search base + scrape per result; observed `creditsUsed: 6` on
  a 4-result call, with per-result `creditsUsed: 1`).
- **Individual scrape:** `firecrawl_scrape` = **1 credit per call**.

So "drop `scrapeOptions`, then re-scrape the kept results individually" costs
*more* Firecrawl credits whenever a query keeps more than a couple results. That
approach (an earlier suggestion) is **rejected.** Whatever we do must keep the
full-markdown scrape bundled into the search call.

**Key point that resolves the apparent conflict:** the credit cost is a property
of the API request parameters, **not of who issues the request.** A Python script
calling `/v2/search` with `scrapeOptions` preserved costs the identical 2cr/10 —
it is the same request the MCP server sends. Moving the call to Python does *not*
change credit economics; it only removes the bytes from the LLM's context.

---

## 5. Empirical behavior of the harness blob (the constraint on consolidation)

Inspected the regressed run's session dir
(`556bf528-980e-4b2f-b61e-1613e048588a`).

**5.1 The blob is size-gated, not universal.**

| Metric | Value |
|---|---|
| Queries returning ≥1 result | ~15 |
| Blobs actually written | **7** |
| Blob sizes | 83KB – 274KB |
| Smallest result count that still offloaded | 2 (those pages had very long markdown) |

The harness offloads only when the serialized result crosses a size threshold
(empirically tens of KB; driven by total bytes = result count × per-result
markdown length, not result count). **~8 non-empty queries stayed inline with no
blob.** A pure "Python reads the blobs" pass would silently miss those queries —
a correctness gap, not just a cost gap.

**5.2 The blob carries no query identifier.**

Top-level keys: `success`, `data`, `creditsUsed`, `id`. `data.web[]` holds the
results (`url`, `title`, `description`, `markdown`). There is **no echo of the
query string, query number, board, or role.** Only a Firecrawl `search id` (UUID).
To map a blob back to its query (needed for per-board / per-role effectiveness
stats), a Phase-1 subagent would have to report its `id` and Python would join on
it. (Board/role are partly re-derivable from result URL host + title — which the
existing filter already does — so the query number is mainly needed for cache-file
naming and role-tier grouping.)

**5.3 The blob is clean, directly-parseable JSON.**

`{"success":true,"data":{"web":[{url,title,description,markdown},…]},"creditsUsed":N,"id":"…"}`.
Python can consume it as-is. Note the existing pre-filter normalizes
`raw.get("results", raw.get("data", []))` — it would need a small tweak to read
`data.web` (the offloaded shape) vs the MCP-returned shape.

**5.4 Offloaded subagent blobs are hoisted to the parent session's
`tool-results/` dir** (not per-subagent). Subagent transcripts live as
`subagents/agent-<id>.jsonl`. So there is a single central directory to scan, but
it commingles blobs from all 20 subagents with no query labeling.

---

## 6. Candidate architectures

### Option A — Python-driven search (recommended)

The orchestrator loops the query queue and, per query, runs a Python script that
calls Firecrawl `/v2/search` **with `scrapeOptions` preserved** (same 2cr/10),
writes `q{N}_raw.json` and `q{N}_filtered.json` itself, and prints a one-line
summary. A review subagent (or a small pool of them) then scores only the
consolidated `kept` set.

- **Credits:** unchanged (bundled scrape preserved).
- **LLM data path:** eliminated. The LLM never sees raw results; no blob, no
  offload, no verbatim Write.
- **Coverage gap:** none — Python always writes `raw.json` deterministically
  regardless of size.
- **Mapping problem:** none — Python controls the loop and knows the query.
- **Cost to build:** replicate query construction + `scrapeOptions` + `tbs` +
  `location` in code (currently assembled in the agent prompt), plus the
  `firecrawl_search_feedback` refund call (one extra endpoint — confirmed REST,
  see "Refund endpoint" note below). Uses the existing `FIRECRAWL_API_KEY`
  (confirmed present in `~/.claude.json`).
- **Fit:** matches [[feedback-prefer-deterministic-over-prompt-patches]] and the
  repo's own offload strategy exactly. Search is deterministic I/O; only scoring
  is judgment.

**Refund endpoint (confirmed 2026-06-02).** The 1-credit refund is reproducible
from Python — it resolves former open question §8.1. The MCP
`firecrawl_search_feedback` tool is itself just a raw HTTP call (no SDK method
wraps it), verified against the official
[firecrawl-mcp-server](https://github.com/firecrawl/firecrawl-mcp-server) source:

```
POST {apiBase}/v2/search/{searchId}/feedback     # apiBase = https://api.firecrawl.dev
Authorization: Bearer <FIRECRAWL_API_KEY>
body: { rating, origin, valuableSources?, missingContent?, querySuggestions? }
```

`searchId` is the `id` field already returned by the `/v2/search` response (§5.2).
Behaviors to preserve in the Python port:
- **Idempotent per `searchId`** — first feedback refunds 1 credit; repeat calls for
  the same id do not double-refund. Call exactly once per query.
- **Daily cap** — response sets `dailyCapReached: true` once the team hits its
  `dailyRefundCap` (default ~100 credits/UTC-day); stop submitting for the rest of
  the day when seen.
- Body needs at least `rating` + `origin`.

**Caveat — this endpoint is NOT in the public api-reference docs** (verified: the
[search endpoint docs](https://docs.firecrawl.dev/api-reference/endpoint/search)
list no feedback path). It exists only inside the MCP server's source, so Firecrawl
can change the path/body without a docs-level deprecation, and a hand-rolled Python
call would **fail silently** (refunds quietly stop — a cost leak, not a crash). This
is the one argument for the Option A′ hybrid below.

### Option A′ — Python search, MCP feedback (hybrid; lowest endpoint-drift risk)

Identical to A for the heavy path (Python owns `/v2/search` + `scrapeOptions` +
writes `q{N}_raw.json`), but the orchestrator keeps calling the maintained
`mcp__firecrawl__firecrawl_search_feedback` tool with the `id` Python captured,
instead of Python hand-rolling the POST.

- **Credits / coverage / mapping:** same as A.
- **Endpoint-drift risk:** eliminated — if Firecrawl moves the feedback path,
  *they* update the MCP server, not us.
- **Cost:** the feedback tool call passes only a UUID + small feedback object (no
  markdown), so it does not reintroduce the cache-read/output regression.
- **Trade:** one cheap LLM tool call per query vs. owning an undocumented endpoint.

### Option B — Blob-consolidation (the original inclination)

Keep parallel search subagents making the MCP call. They report their search `id`
and **skip the verbatim Write**. The orchestrator then runs a Python script that
reads + consolidates the blobs from `tool-results/`, joining by `id`. A review
subagent scores `kept`.

- **Credits:** unchanged.
- **Wrinkle 1 — size-gating gap (§5.1):** inline (small) queries produce no blob,
  so Python would miss them. Requires a fallback: the subagent must emit its small
  inline results some other way when no blob exists — i.e., conditional logic
  ("did my result get offloaded?") that the LLM must judge per call. That
  conditional is fragile and is exactly the kind of LLM-judgment-on-mechanics the
  offload strategy warns against.
- **Wrinkle 2 — mapping (§5.2):** needs the `id` handshake from every subagent;
  blobs are otherwise unlabeled and commingled in one dir.
- **Net:** works, captures most of the savings (the expensive queries are the
  offloaded ones), but more moving parts and a correctness gap to paper over.

### Option C — Just delete the verbatim Write (smallest, partial)

Remove Step 1 from the agent so the subagent stops re-serializing the blob.

- **Pro:** one-edit, reversible, kills the output-token re-serialization.
- **Con:** leaves the offload round-trip and the per-tool-call cache-read bloat
  largely in place (the raw result is still pulled into subagent context to do
  anything with it). Partial win; doesn't address the dominant cache-read cost.
- **Blocker:** without the Write, the Python pre-filter has nothing on disk to
  read for the inline queries, and the blob path for offloaded queries is
  non-deterministic/unlabeled — so this can't stand alone; it only makes sense
  folded into A or B.

---

## 7. Recommendation

**Option A.** It's the only one that preserves the credit economics *and* removes
the LLM from the data path *and* has no coverage gap or mapping problem. It also
aligns the workflow with the repo's documented determinism boundary: Firecrawl
search + regex pre-filter are deterministic (Python); job scoring against the
rubric is judgment (LLM subagent).

Option B is viable if there's a strong reason to keep the search inside subagents,
but the size-gating fallback is a real correctness liability for marginal benefit
over A.

---

## 8. Open questions to resolve before implementing (Option A)

1. **Firecrawl API surface.** Confirm the exact `/v2/search` request body that
   reproduces the current MCP call (`query`, `limit`, `tbs`, `location`,
   `scrapeOptions.formats=["markdown"]`, `onlyMainContent=true`) and the response
   shape (`data.web[]`). ~~Confirm the feedback/refund endpoint
   (`firecrawl_search_feedback` equivalent) for the 1-credit refund.~~
   **RESOLVED 2026-06-02 (both, verified against the live API):**
   - `POST {apiBase}/v2/search` body `{query, limit, tbs, location, scrapeOptions:
     {formats:["markdown"], onlyMainContent:true}}` → response `{success, data:
     {web: [{url, title, description, position, markdown}]}, creditsUsed, id}`.
   - `POST {apiBase}/v2/search/{searchId}/feedback` body `{rating, origin,
     valuableSources?, missingContent?}` where `rating ∈ {good, bad, partial}`
     (NOT a boolean/number): **`good`** requires ≥1 `valuableSources`
     (`[{url, reason?}]`); **`bad`** requires ≥1 `missingContent`
     (`[{topic, description?}]`) or `querySuggestions`; **`partial`** requires
     either. Response: `{success, feedbackId, creditsRefunded, creditsRefundedToday,
     dailyRefundCap}`. Implemented in `scripts/ats_platform_search/firecrawl_client.py`.
2. **Parallelism.** The current workflow leans on the harness to run up to 16
   search subagents in parallel. If Python owns the search, decide whether to (a)
   run queries sequentially in one script call, (b) thread/async within the script
   (the offload strategy explicitly warns against reimplementing the agent SDK's
   fan-out in `asyncio`), or (c) keep a thin per-query Bash dispatch. Likely (a) or
   (c) — search latency is network-bound and 20 queries is small.
3. **Scoring subagent shape.** Decide whether one review subagent scores the
   union of all `kept` (one big context, one scoring-framework read) or a pool
   scores per-query/per-batch. The former cuts the repeated ~532-line
   `scoring_framework.md` read currently paid 20× — a separate, additive saving
   worth quantifying.
4. **Cache-file contract.** Keep `q{N}_raw.json` / `q{N}_filtered.json` so the
   existing pre-filter and the `--no-llm-review`-style debugging still work; just
   change *who* writes them.
5. **Pre-filter input shape.** Tweak `scripts/ats_platform_filter/cli.py`
   normalization to accept `data.web` (the raw Firecrawl shape) in addition to the
   current `results`/`data` handling.
6. **Verify the win.** Re-run and check the per-workflow usage percentage in
   Claude Code. Success criterion: cache_read back to or below the ~7M
   pre-regression level and cost back under ~$11, ideally lower since the raw
   payload never enters any LLM
   context.

---

## 9. What NOT to do (carried from prior decisions)

- Don't drop `scrapeOptions` and re-scrape kept results individually — worse
  credit cost (§4).
- Don't move job *scoring* into Python — it's rubric-against-prose judgment and
  belongs in the LLM ([offload strategy](llm-deterministic-offload-strategy.md)
  "Anti-patterns").
- Don't reimplement parallel dispatch in `asyncio` inside the search script — let
  the harness fan out subagents, or keep search sequential.
