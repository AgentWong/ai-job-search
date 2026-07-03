# Applied Jobs Filter

This document defines how to use the application log to filter positions from search results. Agents MUST apply these rules in addition to `config/exclusions.yml`.

---

## Source of Truth

All applied jobs are recorded in `job_search_log/applications.csv`, with linked pipeline events in `job_search_log/pipeline_events.csv`. **Do not parse these CSVs directly** — use the helper script:

```
.venv/bin/python scripts/recent_applications.py
```

The script lists applications where `date_applied` is within the past 60 days, one per line:

```
# Applications in the past 60 days (75 total)
# Company | Role | Date Applied
SPS Commerce | Cloud Engineer | 2026-04-28
Aha! Labs | DevOps Engineer | 2026-03-15
GitLab | Intermediate Site Reliability Engineer, Environment Automation | 2026-04-21
...
```

For ghost-job detection (Rule 2 below), pass `--days 365 --json` to get a wider window with `app_id`s included.

---

## Rule 1: Cooldown Filter (Past 60 Days)

**Purpose:** Skip positions you applied to within the past 60 days, where it's the same role at the same company. 60 days is chosen because many companies enforce a 60-day re-application moratorium.

**How to apply:**
1. Run `.venv/bin/python scripts/recent_applications.py` once at the start of evaluation.
2. For each candidate position from search results, fuzzy-match against the script output:
   - Does the candidate's **company** match a logged application?
   - AND does the candidate's **role** match the logged role?
3. If BOTH match → skip the candidate with reason `"Recently applied — cooldown"`.
4. If only the company matches but the role is different → keep the candidate. Companies often post multiple distinct roles; you should still apply to a genuinely different role.

### Fuzzy company matching (treat as the same employer)

- Substring or near-substring: `"Aha!"` ≈ `"Aha! Labs"`
- Common corporate suffix variation: `"Acme Corp"` ≈ `"Acme Corporation"` ≈ `"Acme, Inc."`
- Punctuation/spacing differences: `"Cloud-Native Inc"` ≈ `"Cloud Native"`

### Fuzzy role matching (treat as the same role)

- Same role with different seniority modifier: `"DevOps Engineer"` ≈ `"Sr DevOps Engineer"` ≈ `"DevOps Engineer II"` ≈ `"Intermediate DevOps Engineer"`
- Common abbreviation: `"SRE"` ≈ `"Site Reliability Engineer"`
- Trivial wording variation: `"DevOps Engineer"` ≈ `"Dev Ops Engineer"`
- Department/scope qualifier suffix: `"DevOps Engineer"` ≈ `"DevOps Engineer, DevEx"` ≈ `"DevOps Engineer (Platform Team)"`

### Do NOT treat as the same role (these are different — surface them)

- DevOps Engineer vs MLOps Engineer
- DevOps Engineer vs Site Reliability Engineer
- Cloud Engineer vs Cloud Operations Engineer
- DevOps Engineer vs Platform Engineer
- DevOps Engineer vs Infrastructure Engineer

The cooldown is the 60-day re-application courtesy window, **not** a blanket company exclusion. Different role functions at the same company should still surface.

---

## Rule 2: Ghost Job Detection (Older Than 60 Days)

**Purpose:** Companies that post the same role repeatedly and never respond are wasting applicant time. Treat repeat postings as ghost jobs and skip them.

**Source data:** `applications.csv` + `pipeline_events.csv`. The Python ATS scraper consumes both directly via `scripts/ats_scraper/cooldown.py`. LLM workflows can detect ghost jobs by running:

```
.venv/bin/python scripts/recent_applications.py --days 365 --json
```

Then cross-referencing against `pipeline_events.csv` (look for `app_id`s whose only event is `applied` with `event_outcome=no_response`).

**Ghost criteria (BOTH must be true):**
1. The same company is posting the **same role** (per fuzzy match rules above) as a past application that is older than 60 days.
2. The past application has **only** the initial `applied` event with `event_outcome = no_response` — no recruiter contact, no later-stage events.

**Action:**
- Skip the candidate with reason `"Suspected ghost job — applied YYYY-MM-DD with no response"`.
- Flag the company in workflow output so the user can add it to `config/exclusions.yml` under `# Ghost Jobs`.

A company that responded with anything (even a rejection or `ghosted` outcome at a later stage) is NOT a ghost job. Only bare no-response applications qualify.
