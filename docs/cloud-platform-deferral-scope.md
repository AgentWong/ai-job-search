# Scope: Defer Cloud-Platform Disqualification to the Deterministic Scorer

**Status:** Proposed — not implemented. Captured 2026-05-28 on branch
`feat/linkedin_api_scraper` as a follow-up to remove LLM false-disqualification
of Azure roles.

**Companion change already made (separate, landed this session):** the
"Azure is NOT a disqualifier" negation language was removed from
[shared/scoring_framework.md](../shared/scoring_framework.md) and the seven
agent files that enumerated it. That was prompt-hygiene. This document is the
deeper structural fix, which is what actually closes the hole.

**Update (2026-06-20):** The `linkedin-job-search` / `builtin-job-search` browser
workflows and their `browser-job-search` agent referenced below have since been
retired (replaced by the script-driven `linkedin-api-search` / `builtin-api-search`).
The Phase-1 Category-2 deferral pattern this doc credits to `browser-job-search` now
applies only to `hiringcafe-job-search`; `browser-fetch` (Step 3/4) remains as Hiring
Cafe's Phase 2. The analysis below is preserved as captured.

---

## Why

A `hiringcafe` run wrongly disqualified three Azure-primary roles (InvoiceCloud,
Dayforce ×2), each citing a non-existent *"Category 2 — Azure-primary"* trigger.
Two controlled A/B/C experiments (42 runs, Haiku + Sonnet, clean and
dense-under-load) **could not reproduce** the failure under any framework
wording — see Appendix. The decision (disqualify y/n) was identical across all
prompt variants. Conclusion: the bug is not fixable by wording. It is a
property of asking a weak model, under heavy load, to make a mechanical
cloud-platform classification call that the framework treats as a hard gate.

The robust fix is to stop asking the LLM that question at all.

---

## Where cloud-platform DQ happens today

| Path | Who decides cloud-platform DQ | Deterministic scorer in pipeline? |
|------|-------------------------------|-----------------------------------|
| `hiringcafe` Phase 1 (Haiku, cards) | **LLM judgment** on `tech_tools` card field | Phase 2 `browser-fetch` runs `score_cli` on full desc |
| `browser-job-search` Phase 1 (linkedin/builtin) | **already deferred** to Phase 2 ✓ | Phase 2 `score_cli` |
| `browser-fetch` Phase 2, Step 3 | **LLM judgment**, *before* the scorer runs in Step 4 | Step 4 `score_cli` |
| ATS API (`ats-api-llm-review`) | **LLM reviewer** | `filters.py` Stage 5 calls `score_posting` but only acts on `description_disqualified` |
| builtin / linkedin scrapers (`*-llm-review`) | **LLM reviewer** | same scraper → regex → LLM-review shape |
| firecrawl (`ats-platform-search`) | **LLM judgment**, single-phase | **none** — pure LLM scoring |

### Root cause

The regex scorer was deliberately built **not** to hard-disqualify on cloud
platform. [scorer.py](../scripts/ats_scraper/scorer.py) only applies a `-1`
penalty to GCP (see the branch commented *"GCP-only should have been caught by
filters, but penalize anyway"*) and has **no OCI/Oracle pattern at all**.
[filters.py](../scripts/ats_scraper/filters.py) never checks cloud platform.

So a GCP-only DevOps role with Terraform scores `5 + 2 − 1 = 6` and passes the
entire Python pipeline. **The LLM is the only thing enforcing the GCP/OCI
disqualifier** in five of six paths — and that same LLM call is what mis-killed
Azure. `browser-job-search` is the one path that already does the right thing:
it defers Category 2 to Phase 2 (see its Disqualification Filters table).

---

## Recommended fix: make the regex scorer the single source of truth for cloud platform

### 1. Core change — [scorer.py](../scripts/ats_scraper/scorer.py)

- Add an OCI / Oracle Cloud mention pattern (`oci`, `oracle cloud`,
  `oraclecloud`).
- Make **GCP-primary/only** and **OCI-primary/only** set
  `description_disqualified=True` (currently GCP is only a `-1` penalty; OCI is
  invisible). Keep **Azure at `-1`** and **AWS at `+2`**.
- Use a **conservative dominance threshold** so a legitimate multi-cloud role
  is not hard-killed. The current GCP branch fires on
  `gcp_count >= aws_count and gcp_count > 0`, which is too loose for a hard gate
  (a 50/50 AWS+GCP role would be disqualified). The hard-DQ should require the
  rejected cloud to clearly dominate **and** AWS to be essentially absent —
  mirroring the framework's "GCP as **only** cloud / GCP as **primary** cloud".
  Suggested rule: DQ only when `gcp_count > 0 and aws_count == 0` (only-cloud),
  or `gcp_count / total_cloud >= 0.8` (primary). Same shape for OCI.

This propagates for free:

- **ATS path:** [filters.py](../scripts/ats_scraper/filters.py) Stage 5 already
  rejects on `description_disqualified`, so GCP/OCI-only get hard-filtered in
  Python *before* staging to `pending_review.json`.
- **browser-fetch:** Step 4 `score_cli` → Step 5 classify already disqualifies
  on `description_disqualified`.

### 2. Strip cloud-platform DQ out of the LLM phases (they defer to the scorer)

| File | Change |
|------|--------|
| [.claude/agents/hiringcafe-job-search.agent.md](../.claude/agents/hiringcafe-job-search.agent.md) | Replace the "apply Categories 1–8 to each card" model with `browser-job-search`'s deferral table: **Category 2 → defer to Phase 2.** Keep Cat 1 (title), Cat 3 (location/work_type), Cat 5 (salary floor), excluded-companies, and cooldown at Phase 1. |
| [.claude/agents/browser-fetch.agent.md](../.claude/agents/browser-fetch.agent.md) | Step 3: exclude cloud-platform from the agent-judgment DQ list; let Step 4 `score_cli` decide cloud. |
| [.claude/agents/ats-api-llm-review.agent.md](../.claude/agents/ats-api-llm-review.agent.md) | Step 1: state that cloud-platform DQ is owned by the upstream regex scorer (now enforced in `filters.py` Stage 5); the reviewer must not disqualify on cloud-platform grounds. |
| [.claude/agents/builtin-llm-review.agent.md](../.claude/agents/builtin-llm-review.agent.md) | Same as `ats-api-llm-review`. |
| [.claude/agents/linkedin-llm-review.agent.md](../.claude/agents/linkedin-llm-review.agent.md) | Same as `ats-api-llm-review`. |
| [.claude/agents/firecrawl-job-search.agent.md](../.claude/agents/firecrawl-job-search.agent.md) | See "Open decision" below — single-phase, no scorer in the pipeline. |

The LLM keeps everything it is actually good at: title typos (`lll` → `III`),
non-US locations not in the regex (`South Korea`, `Calgary`), software-dev-vs-
scripting nuance, subtle on-call/culture cues. It just stops counting cloud
mentions.

---

## The one real risk: the GCP/OCI hard-DQ threshold

Promoting GCP/OCI from a `-1` penalty to a hard gate raises the cost of a
misclassification: a multi-cloud-with-AWS role that mentions GCP a few times
must **not** be killed. Mitigation:

- Conservative dominance rule (above).
- Lock behavior with fixtures in [tests/](../tests/) covering: GCP-only (DQ),
  OCI-only (DQ), AWS-primary + incidental GCP mention (keep), 50/50 AWS+GCP
  (keep — multi-cloud, no booster), Azure-primary (keep, `-1`).
- Optionally validate the new threshold against a handful of real descriptions
  before flipping the agents to defer.

---

## Tension with the offload strategy's anti-pattern

[llm-deterministic-offload-strategy.md](./llm-deterministic-offload-strategy.md)
warns: *"Don't move judgment to Python — a regex that approximates the scoring
rubric will drift."* This change is on the **deterministic** side of that line,
not in violation of it:

- The scorer **already** classifies cloud platform and already applies the
  AWS `+2` / Azure `-1` / GCP `-1` rule. This change only aligns the existing
  classifier's GCP/OCI case with the rubric's stated hard-DQ — it does not add
  new prose-judgment to Python.
- "Which cloud does this posting use" is mention-counting, not rubric judgment.
  It is exactly the kind of one-correct-output-per-input step the strategy says
  belongs in Python.
- The genuinely judgment-grade Category-2 calls (software-dev-as-primary-duty,
  hypervisor/bare-metal focus) **stay in the LLM**. Only cloud-platform moves.

If this proves to drift, the fallback is the "minimal" option below, which
moves nothing into Python.

---

## Alternative: minimal (hiringcafe only)

Make only `hiringcafe-job-search` defer Category 2 to Phase 2 (adopt the
`browser-job-search` table). No scorer change, no OCI pattern, GCP enforcement
stays in the LLM elsewhere.

- **Pro:** smallest possible change; directly fixes the workflow that broke;
  touches one file; no Python/test work; no anti-pattern tension.
- **Con:** leaves the same LLM cloud-DQ risk in `browser-fetch` Step 3, the
  three `*-llm-review` agents, and `firecrawl`. Azure can still be mis-killed
  on those paths.

---

## Open decision: firecrawl

`firecrawl-job-search` is single-phase (search → scrape → score in one agent)
and does not run `score_cli`. Two options:

1. **Route survivors through `score_cli`** for the cloud/scoring determination —
   consistent with every other path, more work.
2. **Restrict its LLM cloud-DQ to explicit GCP/OCI-only** and accept residual
   Azure risk on this one path.

Decide as part of implementation.

---

## Appendix: experiment evidence

Two workflow A/B/C tests varied only the Azure framing (`original` = one
"NOT a disqualifier" bullet; `current` = three negation mentions; `removed` =
Azure appears only as a `-1` penalty).

| Test | Azure false-DQ (all variants) | Controls |
|------|-------------------------------|----------|
| v1 — clean, 6 cards, Haiku + Sonnet | 0/30 | GCP DQ 1.0, AWS DQ 0.0 |
| v2 — dense framework, 24-card load, Haiku ×6/variant | 0/54 | real-DQ recall 1.0, clean-bait false-DQ 0/36, accuracy 1.0 |

The only metric that moved was reason-attribution on a *Senior* Azure role
(correctly disqualified either way): `current` blamed Azure 3/6 vs `original`
1/6 — weakly consistent with an ironic-process ("pink elephant") effect from
piling on negations, but within noise at n=6. The production failure itself
never reproduced, which is what points the fix at the architecture rather than
the wording.
