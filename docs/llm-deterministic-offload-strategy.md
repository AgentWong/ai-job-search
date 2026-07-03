# Offloading Deterministic Compute from LLMs to Python Scripts

A strategy for keeping LLM-driven workflows fast, predictable, and token-efficient
as the data they touch grows.

This document describes the pattern in the abstract so it can be applied to other
LLM-based projects. The job-hunt repo is the reference implementation.

---

## TL;DR

> **Determinism out, judgment in.**
> Move every step that has one correct output per input into a Python script.
> Keep prose-reading and rubric-application in the LLM. The LLM authors the
> scripts; the LLM runs the scripts at workflow time and only ever sees small
> JSON inputs/outputs — never the full dataset.

The result is workflows that are **deterministic where they should be** and
**probabilistic only where judgment is required**.

---

## The problem this solves

Early versions of the workflows in this repo used CSV files as both inputs and
outputs of LLM steps. The LLM would read the existing CSV, decide which rows to
add or modify, and rewrite the file. Three problems emerged as the dataset grew:

1. **N+1 scaling.** A workflow that took ~10 seconds on a 50-row CSV took
   30+ seconds on a 600-row CSV. The LLM had to load and reason about every
   prior row to compute a single append. The `browser_role_effectiveness.md`
   tracker eventually grew to 603 lines that the LLM rewrote end-to-end on
   every run, recomputing rolling totals each time.
2. **Token cost.** Long CSVs consume context. A workflow that fit in cache on a
   small dataset blew out of cache when the dataset grew, multiplying cost per
   run.
3. **Non-determinism.** A well-tuned LLM workflow runs correctly maybe 85–95% of
   the time. CSV edits are exactly the kind of mechanical operation where the
   ~10% failure mode (duplicated row, stale rolling total, lost URL during
   summarization of long context) is most painful and hardest to detect.

CSV-as-input-and-output is the worst case: the LLM not only reads a large file,
it has to *modify* it correctly. Single-character drift breaks downstream
consumers.

---

## The pattern: split the workflow along the determinism boundary

Every step in a workflow falls into one of two categories:

| Category | Example | Belongs in |
|---|---|---|
| **Deterministic** — one correct output per input | CSV dedup, rolling totals, file-move from `Clippings/`, regex filtering, schema validation, JSON → CSV row append | **Python script** |
| **Judgment** — reads prose and applies a rubric | Score a job description against a 0–10 scoring framework, write a tailored cover letter, decide if a posting is a "ghost job" from subtle wording cues | **LLM** |

Once you draw this line, the workflow takes a consistent shape:

```
LLM (design time)        ─►  Writes Python scripts based on a description
                              of the deterministic step. Vibe-coded, then
                              tested with fixtures.

User (runtime)           ─►  Triggers a pre-defined workflow via slash
                              command. Does not edit prompts or scripts.

LLM (runtime, orchestrator) ─►  Loads small configs, dispatches subagents
                              for judgment-grade work, calls Python
                              scripts for deterministic work. Sees only
                              JSON inputs/outputs — never the full CSV.

Python scripts (runtime) ─►  Read large CSVs, do dedup/aggregation/IO,
                              write large CSVs. Print one-line summaries
                              the LLM relays to the user.

LLM subagents (runtime)  ─►  Read individual job descriptions, apply
                              scoring rubric, return small JSON.
```

The LLM never directly reads or writes the large CSV. It hands the script a
small JSON of new rows and the script handles the file. The script's stdout —
typically one line like
`Added: 4 | Duplicates skipped: 11 | Path: results/application_queue.csv` —
is what the LLM relays to the user.

---

## The decision rule

Move a step to Python if **all** of these are true:

- It has one correct output per input (no judgment required).
- The input or output is large relative to a reasonable context budget, **or**
  it will grow that way.
- The LLM has previously gotten it wrong, slow, or expensive.

Keep a step in the LLM if **any** of these are true:

- It requires reading prose and weighing it against a rubric.
- The "right answer" depends on context the LLM already has loaded for an
  adjacent step.
- The input is small and unlikely to grow.

Don't write a script for a one-off transformation. Don't write a script for
something the LLM does well in two seconds.

---

## Worked example: appending qualified jobs to the queue

**Before (CSV-as-input-and-output):**

The orchestrator workflow ended with a step like:

> Read `results/application_queue.csv`. For each new qualified position from
> this run, check if a row already exists with the same company and title. If
> not, append a new row with the appropriate columns. Then summarize the new
> additions.

This required loading the full queue (now ~200+ rows) into context every run,
and the LLM occasionally added duplicates when it summarized the existing rows
incorrectly mid-run.

**After (offloaded):**

The orchestrator writes a small JSON of just the candidate rows from this run:

```bash
.venv/bin/python -m scripts.job_queue.cli append \
    --positions /tmp/ats-batch-3-1714521234.json \
    --source-track "ats-platform"
```

The Python module ([scripts/job_queue/cli.py](../scripts/job_queue/cli.py))
handles dedup against the existing queue, applies default columns
(`discovered_date`, `source_track`), checks against the applications log to
skip already-applied roles, and prints:

```
Added: 4 | Already applied skipped: 2 | Duplicates skipped: 11 | Path: results/application_queue.csv
```

The LLM relays that line. It never sees the queue.

---

## Reference examples from this repo

| Step that was offloaded | Script | What the LLM does now |
|---|---|---|
| CSV dedup + append to application queue | [scripts/job_queue/cli.py](../scripts/job_queue/cli.py) | Builds JSON of new rows, calls script, relays summary |
| Rolling totals + trend symbols across tracking CSVs | [scripts/effectiveness_tracker/cli.py](../scripts/effectiveness_tracker/cli.py) | Builds JSON of per-role/per-board stats, calls script |
| 30-day analysis of effectiveness CSVs + applications log | [scripts/data_analysis/cli.py](../scripts/data_analysis/cli.py) | Reads the small JSON output, recommends config changes |
| Curation report → target CSVs (with dedup, exclusions, ATS migration) | [scripts/curation_appender/cli.py](../scripts/curation_appender/cli.py) | Triggers the script, relays the summary |
| `Clippings/` → per-month folder organization | [scripts/process_clippings/organize.py](../scripts/process_clippings/) | Triggers `--dry-run`, then runs for real |
| Sankey funnel classification across all monthly logs | [scripts/extract_sankey_data.py](../scripts/extract_sankey_data.py) → [scripts/sankey_d3.py](../scripts/sankey_d3.py) | Triggers the pipeline, doesn't classify rows |
| HTML dashboard generation from tracker CSVs | [scripts/tracking_dashboard/cli.py](../scripts/tracking_dashboard/cli.py) | Doesn't render HTML; the script does |

What stayed in the LLM:

| Step that stayed | Why |
|---|---|
| Read job description, apply scoring rubric, return score 0–10 | Judgment against `shared/scoring_framework.md` |
| Fuzzy-disqualify candidates (title typos, unmapped non-US locations) | Pattern-matching prose with edge cases |
| Tailor a resume / write a cover letter for a specific posting | Generative judgment work |
| Compute "Match %" between a posting and a resume | Cross-domain keyword weighting |
| Synthesize the data-analysis JSON into recommendations | Reading the script's output and producing prioritized actions |

The split lines up cleanly with the determinism rule. None of the LLM steps
need to load a large CSV; none of the Python steps need to read prose.

---

## How to apply this to a new workflow

1. **Inventory the workflow's steps.** For each, ask: *one correct output per
   input?*
2. **Draw the boundary.** Mark every deterministic step as a future script;
   mark every judgment step as LLM-resident.
3. **Author the scripts with the LLM.** Describe what you want in plain
   language. Test against a fixture (`tests/fixtures/`) — five rows is enough
   to lock behavior. Treat the script as a black box from the workflow's
   perspective: standardized JSON in, one-line summary out.
4. **Refactor the workflow file.** Each deterministic step becomes a single
   bash invocation. The LLM's job in that step is reduced to constructing the
   JSON input, calling the script, and relaying the summary.
5. **Verify with `--dry-run` first.** Every script that writes data should
   support `--dry-run`. Use it the first time the workflow runs the new path.
6. **Stop condition.** If token usage doesn't drop materially after the
   refactor, the boundary is in the wrong place. Re-examine which steps you
   moved.

---

## Anti-patterns

**Don't move judgment to Python.** A regex that approximates the scoring
rubric will drift from the real rubric. The qualification-rate funnel will
slowly fill with false positives and false negatives that no one notices for
weeks. Keep scoring in the LLM where it's transparent.

**Don't keep two writers for the same file.** If a tracker CSV is now
written by a script, the LLM workflow must never also write to it directly.
Two writers means drift; pick one.

**Don't script the orchestrator's parallel dispatch.** The harness already
runs N subagents in parallel. Reimplementing that in `asyncio.gather` is a
worse version of what the agent SDK does for free. The Python scripts handle
data; the LLM orchestrates agents.

**Don't collapse files just because both are CSV-shaped.** Pick a file format
from the data shape, not from symmetry — when values can contain the delimiter
(e.g. URLs with commas), a CSV is the wrong container and a separate
YAML/JSON output is correct even if a sibling dataset is a CSV.

**Don't move human-edited ledgers to CSV.** The per-month `job_search_log.md`
files are human-edited frequently — markdown is correct there. Only the
*aggregation* moves to Python; the source-of-truth file stays in the format
its primary editor uses.

**Don't write a script for a transformation that runs once.** Vibe-coding
amortizes when the workflow runs repeatedly. A migration that runs once and
never again is fine to do directly in the LLM.

---

## Why this works

Three properties compound:

1. **Determinism.** Once a step is a Python script with a fixture-tested CLI,
   it produces the same output every time. The 5–15% failure rate of the LLM
   on mechanical steps disappears for those steps.
2. **Speed.** A script that dedups 200 rows runs in milliseconds. The LLM
   "thinking" about the same operation took 30+ seconds and grew linearly
   with the dataset.
3. **Token efficiency.** The LLM's context now contains a one-line summary
   instead of 600 rows. This compounds across a workflow with several
   deterministic steps — each one that previously consumed a large CSV now
   consumes nothing.

The composite workflow stays *probabilistic in shape* (the LLM still
orchestrates) but is *deterministic in execution* (every step that needs to be
correct, is). When something does go wrong, the failure is in the LLM's
judgment about *which* deterministic step to run, not in the deterministic
step itself — and that's a much narrower surface to debug.
