# ATS Platform Validation Workflow

Validate candidate ATS / job-board domains discovered via Claude Desktop Research
Mode (`claude_desktop/ats_platform_curation/project_instructions.md`) before
adding them to `config/config.yml`. This workflow runs **Python-driven Firecrawl
search** (`scripts.ats_platform_validate.cli`) against each candidate with
hardcoded validation parameters (limit 10, past month) and produces a pass/fail
report.

**This workflow does NOT write to `results/application_queue.csv`.** It is
validation-only. Once a candidate is confirmed and added to `config.yml`, the
next regular `/ats-platform-search` run will surface its qualified positions.

---

## Architecture (Option A — Python-driven search)

Same shape as `/ats-platform-search`: the deterministic half (search + filter +
classify) runs in Python via the **direct Firecrawl `/v2/search` API** — NOT the
MCP server. The raw Firecrawl payload **never enters any LLM context**; Python
writes it straight to disk and the orchestrator reads only a small summary.

```
Orchestrator: run Python validation (one call) → read SMALL summary
    ↓
Python (scripts.ats_platform_validate.cli):
    read candidates.yml → filter vs config.yml already-covered set
    FOR each candidate: Firecrawl /v2/search (site:domain, primary roles, qdr:m, limit 10)
        → write q{NN}_raw.json verbatim   (offload — no LLM ever reads this)
        → POST /v2/search/{id}/feedback   (refund 1 credit)
        → regex pre-filter (qualified-count bonus signal)
        → classify verdict (PASS_STRONG | PASS_WEAK | MARGINAL | FAIL_EMPTY | FAIL_ERROR)
    → write validation_summary.json   (small: counts, verdicts, notes — NO markdown)
    ↓
Orchestrator: read validation_summary.json → write report → emit ready-to-paste config.yml stanza
```

**Why this shape:** the previous version dispatched up to 16 `firecrawl-job-search`
MCP subagents (one per candidate), each re-serializing its raw search payload
into an LLM context. Search is deterministic I/O; only the report wording needs
an LLM. This mirrors the `/ats-platform-search` Python-driven search (see
[docs/llm-deterministic-offload-strategy.md](../../docs/llm-deterministic-offload-strategy.md)
for the pattern in the abstract).

### 🧱 Context discipline

1. **NEVER `Read` `q{NN}_raw.json`** — it holds full job-page markdown. The only
   file you read is `validation_summary.json` (small — counts, verdicts, notes,
   sample URLs; no markdown).
2. **NEVER paste raw JSON into your reply.** Your visible output is the report
   tables and the ready-to-paste `config.yml` stanza only.

---

## Arguments

Optional `$ARGUMENTS` — passed through to the CLI. Useful overrides:
- `--time-window past_day|past_2_days|past_week|past_month|past_year` (default
  `past_month` — the validation sample window).
- `--candidates <path>` — alternate candidates file (default the curation file).
- `--search-limit N` (default 10).

If `$ARGUMENTS` is empty, run with no extra flags.

---

## Stage 1: Run the Python validation

```bash
.venv/bin/python -m scripts.ats_platform_validate.cli [$ARGUMENTS]
```

The script reads `claude_desktop/ats_platform_curation/candidates.yml`, drops
candidates already covered by `config.yml` `job_boards` (primary + watch +
secondary; wildcard-aware, skipping `vendor_variant: true` entries from the drop),
searches each remaining domain via the direct Firecrawl API, refunds a credit per
query, regex-filters for the qualified-count bonus signal, classifies a verdict
per candidate, and writes `results/ats_platform_validation_cache/validation_summary.json`.

**Timing / timeout.** Bundled full-markdown scrapes can take a few minutes. Use a
generous Bash timeout (e.g. 600000 ms). If it times out, re-run with
`--concurrency 8` or run it in the background and wait. Re-running is safe (it
overwrites the cache); refunds are idempotent.

Capture stdout — it prints the per-verdict counts, the refund summary, and the
summary-file path.

**Error handling:**
| CLI output | Action |
|------------|--------|
| `Candidates file missing` (exit 2) | Tell the user to run Claude Desktop Research Mode with `claude_desktop/ats_platform_curation/project_instructions.md`, save the YAML to `claude_desktop/ats_platform_curation/candidates.yml`, then re-run. |
| `All N candidate(s) already covered` | A summary is still written; report the skips and stop. |
| `FIRECRAWL_API_KEY not found` | The key is missing from env and `~/.claude.json` — tell the user. |
| Per-candidate `error` in summary | Marked `FAIL_ERROR` — warn (domain + error), continue. NO retry. |
| All candidates `FAIL_ERROR` | Likely a Firecrawl auth / rate-limit issue. Report the failure pattern; do NOT write a partial recommendation stanza. |

---

## Stage 2: Read the summary

Read `results/ats_platform_validation_cache/validation_summary.json`. It contains:
- `loaded`, `validated_count`, `skipped_already_covered[]` (`{domain, vendor, matched_entry}`).
- `verdict_counts` — `{PASS_STRONG, PASS_WEAK, MARGINAL, FAIL_EMPTY, FAIL_ERROR}`.
- `role_terms`, `time_filter`, `search_limit`, `location_mode`.
- `feedback` — `{refunded, failed, credits_refunded, daily_cap_reached}`.
- `candidates[]` — per candidate: `domain`, `vendor`, `vendor_variant`,
  `scrapability`, `notes`, `results_found`, `qualified_count`, `by_reason`,
  `sample_qualified_urls`, `verdict`, `error`.

### Verdict reference

| Verdict | Criteria | Recommendation |
|---------|----------|----------------|
| `PASS_STRONG` | `results_found >= 5` AND `qualified_count >= 1` | Add to `config.yml` |
| `PASS_WEAK` | `results_found >= 5` AND `qualified_count == 0` | Add — past-month sample missed infra roles, but platform is reachable |
| `MARGINAL` | `1 <= results_found < 5` | Manual review — small platform or wrong URL pattern |
| `FAIL_EMPTY` | `results_found == 0` AND no error | Skip — not Google-indexable for these roles or URL pattern wrong |
| `FAIL_ERROR` | Firecrawl call errored | Investigate — rate-limit or malformed domain |

**Why `results_found` is the primary signal, not `qualified_count`:** a domain
that returns 8 raw results but 0 qualified roles still proves the platform is
Google-indexable and reachable via Firecrawl — the next regular
`/ats-platform-search` run with `qdr:d` and the wider role list will catch real
matches when they post. A domain that returns 0 raw results is broken.

---

## Stage 3: Write Validation Report

Write to `results/ats-platform-validation-<YYYY-MM-DD>.md`:

```markdown
# ATS Platform Validation — [DATE]

## Configuration
- Candidates file: [candidates_file]
- Time filter: [time_filter] ([time_window])
- Search limit per candidate: [search_limit]
- Role terms: [role_terms]
- Location mode: [location_mode]

## Summary
- Candidates loaded: [loaded]
- Skipped (already in config.yml): [len(skipped_already_covered)]
- Validated: [validated_count]
- PASS_STRONG: A
- PASS_WEAK: B
- MARGINAL: C
- FAIL_EMPTY: D
- FAIL_ERROR: E

## Skipped — Already in config.yml
| Domain | Vendor | Reason |
|--------|--------|--------|
| ...    | ...    | already covered: matches `<matched_entry>` |

## Per-Candidate Results
| Verdict | Domain | Vendor | Raw Hits | Qualified | Exclusion Summary | Sample URL |
|---------|--------|--------|----------|-----------|-------------------|------------|
| PASS_STRONG | jobs.dayforcehcm.com | Dayforce | 8 | 2 | 3x senior, 1x non-US | https://... |

*Exclusion Summary renders the candidate's `by_reason` map (e.g. `3x senior_title, 1x non_us_snippet`). Sample URL is the first of `sample_qualified_urls`.*

## Errors
[Only show if FAIL_ERROR > 0. List each candidate with its error message.]

## Recommended `config.yml` additions

Append the following entries to `config/config.yml`. Only PASS_STRONG and
PASS_WEAK candidates are included.

**Tier placement: ALL new entries go into `job_boards.secondary`** — they are
unproven and must earn promotion through 10+ runs of tracked yield. The
validation snapshot (one search of past_month) is not a substitute for sustained
tracking. See the `config.yml` header comment for promotion criteria. Do NOT
pre-promote PASS_STRONG candidates into primary based on a single validation pass.

```yaml
  - domain: jobs.dayforcehcm.com
    name: Dayforce
    scrapable: true
    notes: "Validated YYYY-MM-DD: 8 raw / 2 qualified in past month. [vendor/scrapability note]."
```

## Manual review queue
[List MARGINAL candidates with their domain, vendor, raw hit count, and notes from the summary.]
```

---

## Stage 4: User-Facing Summary

Emit to chat (in addition to the file write):

```
## ATS Platform Validation Complete

### Candidates evaluated: [validated_count]
- PASS_STRONG (recommend add): A
- PASS_WEAK (recommend add): B
- MARGINAL (manual review): C
- FAIL_EMPTY (skip): D
- FAIL_ERROR (investigate): E
- Skipped (already covered): K
- Credits refunded: R (failed: F)

### Recommended additions to `config/config.yml`
[Inline the YAML stanza from the report — same fenced codeblock, ready to paste.]

### Full report
Written to: results/ats-platform-validation-YYYY-MM-DD.md
```

---

## What This Workflow Does NOT Do

- **Does NOT write to `results/application_queue.csv`** — qualified positions
  discovered during validation are listed in the report only.
- **Does NOT update effectiveness trackers** — validation is a one-shot probe.
- **Does NOT modify `config/config.yml`** — the user reviews the report and
  manually adds entries (the workflow emits ready-to-paste YAML to make this easy).
- **Does NOT search secondary roles** — primary roles are sufficient signal for
  whether a platform is worth adding.
- **Does NOT use the Firecrawl MCP server** — all search goes through the direct
  `/v2/search` API in `scripts.ats_platform_validate.cli`, like `/ats-platform-search`.
