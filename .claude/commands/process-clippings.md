Process new job clippings from the Clippings/ directory and organize them into the job search system.

The job search log uses two CSVs as the source of truth:

  job_search_log/applications.csv     application metadata (one row per app)
  job_search_log/pipeline_events.csv  pipeline events (multiple rows per app)
  job_search_log/narratives.md        manual narrative notes (edited by hand)

These three files drive two generated artifacts:

  job_search_log/dashboard.html              human-facing dashboard
  job_search_log/job_search_sankey_d3.html   Sankey funnel diagrams

Never edit the generated HTMLs directly; they are regenerated from the CSVs
and narratives.md every run.

## Steps

1. **Organize clipped files**: Run the organizer to group files by base name, parse frontmatter, and move files into the correct month folder. Dry-run first to review planned moves:
   ```
   .venv/bin/python -m scripts.process_clippings.organize --dry-run --verbose
   ```
   Then run for real:
   ```
   .venv/bin/python -m scripts.process_clippings.organize
   ```
   Confirm output lists each processed job folder and that `Clippings/` is empty.

2. **Extract resume text as a permanent artifact**: Run the extractor to write `resume.txt` alongside every `resume.pdf` in `job_search_log/`. It is idempotent — only PDFs without an up-to-date `resume.txt` are re-processed:
   ```
   .venv/bin/python scripts/extract_resume_text.py
   ```
   `resume.txt` is a permanent artifact (kept in the job folder for later LLM analysis); do not delete it after computing the match.

3. **Compute Match % for each new application**: Before adding the row, compute an estimated *fitness* match between the job posting and the resume. This is NOT a tool-presence count — it's a recruiter's-eye estimate of whether the resume actually demonstrates what the posting asks for, in the context the posting describes.
   1. Read the job's `resume.txt` (created in the previous step) for the plain-text resume content.
   2. From `posting.md`, extract two lists:
      - **MUST-HAVE requirements**: anything in "Requirements", "Qualifications", "Minimum Qualifications", or written as "X years of Y" / "Strong experience in Z" / "Required: ...". Includes specific languages and frameworks even when buried in the qualifications bullet list.
      - **NICE-TO-HAVE requirements**: anything in "Nice to have", "Preferred", "Bonus", "Plus", or framed as "experience with X is a plus".
   3. For EACH must-have, score on this fitness scale (not presence):
      - **Full credit (1.0)**: resume shows the tool/skill **in production** at roughly the **scale or depth** the posting describes (e.g., posting says "Kubernetes at thousands of nodes" → resume shows production K8s with comparable scale).
      - **Half credit (0.5)**: resume shows the tool hands-on but only in a **smaller-scale production context, a personal project, or as a tangential mention** (e.g., posting wants "production Kafka" → resume has an 11-node Kafka lab project).
      - **Quarter credit (0.25)**: tool/skill appears only in a Skills row with no supporting bullet, or only via "comparable to" equivalence annotation.
      - **Zero (0)**: not present at all (including required languages or frameworks the resume does not list).
   4. For NICE-TO-HAVES, use the same scale but each item is worth half the weight of a must-have.
   5. Compute the weighted average across must-haves (and nice-to-haves), then convert to an integer 0–100. Round to the nearest 5%.
   6. **Apply hard caps:**
      - Any **fully missing required language or framework** (e.g., posting requires Java; resume has none) caps the final score at **70**.
      - **Two or more** fully missing must-haves cap the final score at **60**.
      - The score may **not exceed 90** unless every must-have is at full credit (in-production, in-context evidence). 95+ is reserved for cases where you also match the majority of nice-to-haves at full credit.
   7. Be honest. The goal is signal about which apps are real shots vs. lottery tickets — inflated scores defeat the purpose.

4. **Resolve `original_source`**: This is the LLM workflow that originally surfaced this posting (distinct from the clipping `source`, since the user often clips from the ATS or company page even when the workflow that surfaced it was different). Run the resolver script — it implements the matching ladder (exact URL → substring URL → Company+Role normalized → inference fallback) and reads `results/application_queue.csv` directly. No LLM judgment is needed.

   ```
   .venv/bin/python -m scripts.source_resolver --posting "<path/to/posting.md>"
   ```

   The script reads the posting's frontmatter (`source` URL, `author` tags) and parses the parent dir name as `Company - Role`. Override with `--url`, `--company`, `--role` if the defaults are wrong. Output is one JSON object on stdout with:
   - `original_source` — the resolved value (use this verbatim as the `--original-source` arg in step 6)
   - `matched` — true if a queue row was found, false if it fell back to inference
   - `match_strategy` — `exact_url`, `substring_url`, `company_role`, or `inferred`
   - `queue_url` — the queue row's URL (empty on inference)

   Known `source_track` values (returned verbatim when matched):
   - `ats-platform` (ats-platform-search workflow)
   - `ats-api-<platform>` (ats-api-search — `ats-api-greenhouse`, `ats-api-lever`, `ats-api-ashby`, `ats-api-rippling`, `ats-api-workday`, `ats-api-smartrecruiters`)
   - `builtin-api` (builtin-api-search)
   - `builtin` (legacy — historical rows only; the `builtin-job-search` browser workflow has been retired in favor of `builtin-api`)
   - `company_direct` (legacy — historical rows only; the company-monitoring workflow that produced these has been retired)
   - `hiringcafe` (hiringcafe-job-search)
   - `linkedin-api` (linkedin-api-search)
   - `linkedin(verified)` (legacy — historical rows only; the `linkedin-job-search` browser workflow has been retired in favor of `linkedin-api`)

   Inference fallback values (when no queue row matches; `?` flags them as inferred):
   - LinkedIn host → `linkedin-api?`
   - Built In host or `Built In` author tag → `builtin-api?`
   - ATS/company career-site hosts (greenhouse, lever, ashby, workday, etc.) → `unknown` — these can come from any of `ats-platform`, `ats-api-*`, or `hiringcafe` and cannot be reliably attributed without the queue row.

   **Do not delete `results/application_queue.csv` until after this step has populated `original_source` for every new row.**

5. **Determine `source` from the clipping URL**: Parse the `source` URL in the clipping frontmatter:
   - `linkedin.com` → "LinkedIn"
   - `greenhouse.io` → "Greenhouse"
   - `jobs.lever.co` → "jobs.lever.co"
   - Other: extract domain (e.g., "builtin.com") or company career-site label.

6. **Append the application to `applications.csv`**: For each new application, run:
   ```
   .venv/bin/python scripts/append_application.py \
       --company "Acme Corp" \
       --role "DevOps Engineer" \
       --date-applied 2026-04-28 \
       --source "jobs.lever.co" \
       --original-source "ats-platform" \
       --match 85 \
       --resume-format 2-page \
       --used-cover-letter true \
       [--application-notes "..."]
   ```
   `app_id` is generated as `<company-slug>__<YYYY-MM-DD>`. The script also appends an initial `applied` event with outcome `no_response` to `pipeline_events.csv`.

   `--resume-format` and `--used-cover-letter` should match the format you actually used. By default earlier months in 2026 used 1-page (Jan, Mar) or 2-page (Feb, Apr); whichever you used for this batch.

7. **Add narrative notes** if relevant: edit `job_search_log/narratives.md` directly to record any strategy changes that month (e.g., "Lifted Healthcare/Government industry exclusions", "Re-wrote CV with more human-sounding language", "Added keyword equivalence matching"). The dashboard renders these per month.

8. **Regenerate dashboards**: Run both regenerators after every batch:
   ```
   .venv/bin/python scripts/regenerate_dashboard.py
   .venv/bin/python scripts/extract_sankey_data.py
   .venv/bin/python scripts/sankey_d3.py
   ```
   Confirm `job_search_log/dashboard.html` and `job_search_log/job_search_sankey_d3.html` were regenerated.

9. **Verify**: Confirm the new folders exist with the correct files, the new rows appear in `applications.csv` and `pipeline_events.csv`, and the dashboard reflects the additions.

## Logging pipeline progression

When an application progresses (recruiter emailed, phone screen happened, interview scheduled/completed, rejection, offer), append a pipeline event:

```
# Recruiter emailed (no screen yet — this is the email_response stage)
.venv/bin/python scripts/append_event.py <APP_ID> email_response \
    --date 2026-04-15

# Phone screen actually happened (phone_screen stage). Only log this when the
# screen took place. If a screen was scheduled then cancelled, leave the
# email_response event in place and update its outcome (see below).
.venv/bin/python scripts/append_event.py <APP_ID> phone_screen \
    --date 2026-04-20

# 1st interview happened
.venv/bin/python scripts/append_event.py <APP_ID> interview_1 \
    --date 2026-04-26

# 2nd / follow-up
.venv/bin/python scripts/append_event.py <APP_ID> interview_2 \
    --date 2026-05-03

# Nth round (extends as far as needed)
.venv/bin/python scripts/append_event.py <APP_ID> interview_3 \
    --date 2026-05-10

# Offer
.venv/bin/python scripts/append_event.py <APP_ID> offer --date 2026-05-15
```

When the application terminates at the current stage, set the outcome on the highest stage:

```
# Got rejected at the 1st interview
.venv/bin/python scripts/append_event.py <APP_ID> --update-outcome rejected \
    [--notes "Rejection email said role was filled internally"]

# Ghosted at email-response stage (e.g., screen scheduled then cancelled, no follow-up)
.venv/bin/python scripts/append_event.py <APP_ID> --update-outcome ghosted \
    [--notes "Phone screen scheduled then cancelled, no further contact"]

# Withdrew at email stage (e.g., declined to do AI screening)
.venv/bin/python scripts/append_event.py <APP_ID> --update-outcome withdrew \
    [--notes "Requested one-way AI screener, declined to participate"]

# Accepted / declined an offer
.venv/bin/python scripts/append_event.py <APP_ID> --update-outcome accepted
.venv/bin/python scripts/append_event.py <APP_ID> --update-outcome declined
```

The outcome enum:
- *(blank)* — advanced to a later stage (only valid if a later stage event exists)
- `pending` — currently waiting at this stage, no resolution yet
- `no_response` — applied with no contact (only valid at stage `applied`)
- `rejected` — employer rejected at this stage
- `ghosted` — went silent at this stage (no further contact)
- `withdrew` — candidate withdrew at this stage
- `aborted` — candidate aborted (similar to withdrew, more decisive)
- `accepted` / `declined` — only valid at stage `offer`

After appending events, regenerate the artifacts (step 8).

## Stage classification rules of thumb

When deciding which stage a new event belongs to:

- `email_response`: ANY recruiter contact via email — outreach, scheduling, AI/HackerRank assessment requests, scheduling/cancellation of a screen, "Phone Screen Scheduled". The screen has NOT yet taken place.
- `phone_screen`: a phone screen ACTUALLY happened (do NOT use this stage for "Phone Screen Scheduled" or "Phone Screen Cancelled" — those are email_response events with notes).
- `interview_N`: a video/in-person interview round took place. Use sequential N (1 for first round, 2 for next, etc.) regardless of how the company labels them. "Follow-up Interview" after a 1st interview = `interview_2`.
- `offer`: a written offer was extended.

If you're unsure whether an event was a phone screen or an interview, prefer the lower stage. The point of the phone_screen stage is to capture "got past the recruiter into a technical/role conversation"; interview rounds are more substantive evaluations.
