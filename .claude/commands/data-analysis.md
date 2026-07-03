# Data Analysis Workflow

Aggregate the last N days of effectiveness tracking data + actually-submitted applications into a compact JSON report, then read it and recommend actions on `config/config.yml`.

Intended cadence: monthly (every ~30 days). The script does the heavy CSV math; the LLM only reads the small JSON output and produces recommendations.

---

## Arguments

Optional `$ARGUMENTS` overrides the role/board window (default 30 days).
Examples:
- _(empty)_ — 30-day window for roles/boards/applications
- `60` — 60-day window for roles/boards/applications

---

## Execution

### 1. Run the analyzer

```
.venv/bin/python -m scripts.data_analysis.cli --pretty
```

(or pass `--days N` from `$ARGUMENTS`).

The script writes `results/tracking/data_analysis_<date>.json` and prints two stdout lines:
- `Wrote: <path>`
- A one-line summary with classification counts.

If the script exits non-zero: read stderr and stop. Do not attempt to hand-aggregate the CSVs as a fallback.

### 2. Read the JSON report

Read the path printed on the `Wrote:` line. The JSON has three top-level analytical sections:
- `roles` — per-role aggregates with `classification` and `high_volume_low_yield` flag
- `boards` — Firecrawl ATS boards + ATS API platforms
- `applications` — apps you actually submitted, grouped by source, with response rates

The script does the math; you do the synthesis. Don't re-derive numbers — read what's there.

---

## Reporting

Produce a markdown report with the structure below. Lead each section with the script-supplied numbers, then add interpretation.

```
## Data Analysis — {generated_at}

Window: roles/boards/apps = {role_board_days}d
Applications submitted in window: {total_applications_in_window}

---

### Role Effectiveness

Highlight the rows the user most likely wants to act on:

| Role | Tier | Found | Qualified | Apps | Rate | Classification | Notes |
|------|------|------:|----------:|-----:|-----:|----------------|-------|
| ... | ... | ... | ... | ... | ...% | ... | flag `high_volume_low_yield` if true |

Then a "Recommendations" subsection naming each role with a non-`keep_*` classification:
- **{role}** ({tier} → {classification}): {one-line reasoning citing the numbers}

When `high_volume_low_yield` is true even on a "promote" or "keep" classification,
call it out — that's the user's "Systems Engineer noisy" signal. The script flags
the data point; you weigh it against API/Firecrawl cost vs. the qualified yield.

A `local_only`-tier role classifies as `keep_local_only` — an intentionally
high-noise generalist title searched only in local mode (`location.remote: false`),
so it's exempt from the promote/demote/removal heuristics. Don't recommend
promoting or removing it; if it's noisy even locally, just note the numbers.

If `applications_unattributed_to_role` > 0 or `untracked_role_strings_in_csvs`
is non-empty, mention them so the user can investigate role-name drift.

---

### Board / Platform Effectiveness

Two tables — Firecrawl boards (with current tier from config.yml) and ATS API platforms.

| Board | Tier | Runs | Found | Qualified | Rate | Recommendation |
|-------|------|-----:|------:|----------:|-----:|----------------|

Recommendations subsection naming each board with a non-`keep_*` recommendation
(omit the section if everything is `keep_*` or `no_data`).

If `silent_boards_in_config` is non-empty, list them — these are configured
boards that produced no rows in the window (likely stopped getting hit at all).

For ATS API platforms, also surface the `rejection_breakdown` for any
platform with a low qualification rate. Distinguish **informational** rejections
(expected high-volume noise from filtering) from **actionable** ones (signals
that the input company list itself is wrong):

| Reason | Class | Meaning |
|--------|-------|---------|
| `too_old` | informational | Date filter; high counts are expected |
| `no_target_role` | informational | Wrong job entirely; expected |
| `seniority_keyword` | informational | Senior/Staff/Lead; expected |
| `wrong_role_type` | informational | Backend/SWE/Fullstack; expected |
| `recently_applied_cooldown` | informational | Cooldown working as intended |
| `suspected_ghost_job` | informational | Ghost detection; expected |
| **`no_remote_signal`** | **actionable** | Company posts non-remote roles — review the company list |
| **`non_us_geography`** | **actionable** | Company posts outside US — review the company list |
| **`hybrid_or_onsite`** | **actionable** | Company explicitly hybrid/onsite (remote mode) — review the company list |
| **`state_restriction`** | **actionable** | Remote carve-out excluding the candidate's state (`config.yml` `location.state`); uncommon. Legacy rows: `idaho_restriction` |
| **`wrong_metro`** / **`remote_not_local`** | **actionable** | Local mode (`location.remote: false`): posting outside the target city/state, or a remote role dropped under strict-local |
| **`*_disqualifier`** (description) | **actionable** | Hard description-level disqualifier |
| `excluded_company` | sanity | Should be ~0; if not, exclusions list is out of sync |

Each ATS API platform row in the JSON now carries `rejection_breakdown`,
`actionable_rejections`, and `actionable_rejection_pct`. Report a
"Rejection Breakdown" subsection for any platform where:
- `qual_rate_pct < 1.0` AND `actionable_rejections >= 50`, OR
- `actionable_rejection_pct >= 5.0`

Show the top 3 reasons for each flagged platform. Lead with the *actionable*
reasons; only mention informational reasons if they dominate so absolutely that
the user might wonder why nothing else shows up (e.g. 99% `too_old`).

If `ats_api_company_actionable_rejections` is non-empty, render a per-company
table after the platform tables:

| Company | Platform | Actionable Rejections | Share | Top Reasons |
|---------|----------|----------------------:|------:|-------------|

Sort by actionable count desc. Cap at top 10. These are companies whose
input flow is dominated by remote/geo/hybrid rejection signals — strong
candidates for removal from `config/company_targets_ats.csv`.

---

### Applications & Outcomes

Top sources by volume — surface response-rate signal:

| Source | Apps | Responses | Rate |
|--------|-----:|----------:|-----:|

If a source has 5+ apps and a 0% response rate, flag it as "consider deprioritizing"
even if it isn't tracked as a job board (e.g. a manual-entry source like "LinkedIn"
that rolls up many underlying boards).

---

### Recommended Actions

A short, prioritized list of edits the user can apply:

1. **Edit `config/config.yml`** — list each suggested role/board move with the new tier (or removal). Cite numbers, not opinions.
2. **Edit `config/company_targets_ats.csv`** — list each company in `ats_api_company_actionable_rejections` whose actionable share is >= 70% AND has been scraped 5+ times. These produce noise but never qualifying jobs.
3. **No action needed** — if everything is `keep_*` / `no_data` and no per-company rejections are flagged, say so explicitly.

DO NOT edit `config/config.yml` or `config/company_targets_ats.csv` yourself. The user reviews and applies.
```

## Interpretation Rules

- The script's `classification` is a heuristic. You can disagree with it in the report — the user wants synthesis, not a rubber stamp. If the numbers tell a different story than the label, say so explicitly ("classification says X, but Y suggests Z").
- A role with `high_volume_low_yield: true` is the canonical "Systems Engineer" pattern: it might still be earning a few qualified hits, but it's burning Firecrawl credits and browser-workflow time disproportionately. Recommend tier changes that reduce its slot share (e.g. drop to secondary even if classified `promote_to_primary`).
- A `removal_candidate` role is a strong signal but the user makes the final call — phrase as "recommend removing" not "remove".
- Don't recommend changes for any group with `runs < 5` or `no_data` classification. Just note them.

---

## Error Handling

| Error | Action |
|-------|--------|
| Script import error | Fix the .py file, re-run |
| Script non-zero exit | Read stderr, report to user, stop |
| Empty role/board CSVs | Report "no data in window", suggest expanding `--days` |
