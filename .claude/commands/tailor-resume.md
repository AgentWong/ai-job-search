# Resume Tailoring Orchestrator

Generate keyword-optimized DOCX resumes and pitch cover letters for all job postings in `Clippings/`.

---

## Prerequisites

Ensure dependencies are installed:
```bash
.venv/bin/pip install jinja2
```

---

## Execution

### 1. Enumerate Job Postings

List all markdown files in `Clippings/`:

```
job_postings = glob("Clippings/*.md")
```

If no files found, **STOP** and inform user to add job posting files to `Clippings/` using the Obsidian Web Clipper first.

### 2. Create Todo Items

For each job posting:
```
FOR each file in job_postings:
    company, title = parse_filename(file)  # "Company - Title.md" → company, title
    add_todo("Generate resume + cover letter for {company} - {title}")
```

### 3. Process Each Job Posting

**CRITICAL: Process job postings ONE AT A TIME, sequentially. Do NOT run subagents in parallel or in the background. Wait for each subagent to fully complete before starting the next one. Parallel execution causes hung tasks and excessive resource usage.**

For each job posting, invoke BOTH agents sequentially with a validator gate between them:

```
FOR each job_file in job_postings:
    mark_todo_in_progress(job_file)

    # Phase 1: Generate 1-page resume (WAIT for completion before proceeding)
    resume_result = runSubagent(
        agent: "resume-tailoring",
        prompt: "Generate a tailored resume for: {job_file}"
    )
    # WAIT: Do not proceed until resume_result is fully returned

    # Phase 1.5: Validate resume content (HARD GATE)
    # Re-run the validator independently of the agent's self-report — agents
    # have been observed to claim word_count_verified=true while violating
    # rules. Trust the script, not the agent.
    #
    # IMPORTANT: invoke the validator as a single plain command. The Bash tool
    # already returns the exit code in the tool result, so DO NOT append
    # `; echo "EXIT: $?"`, `2>&1`, `|| true`, or any other shell suffix —
    # chained operators trigger an extra permission prompt and add no
    # information. The script exits 0 on PASS and non-zero on FAIL.
    company, title = parse_filename(job_file)
    json_path = "resumes/generated/tailored/Alex_Johnson_{company}_{title}_content.json"
    validation = bash(
        ".venv/bin/python scripts/validate_resume_content.py "
        "{json_path} --type 1page --posting '{job_file}'"
    )
    IF validation.exit_code != 0:
        # Fail this job; record the validator stderr; SKIP cover letter and continue
        results.append({
            job_file: job_file,
            resume: "FAILED VALIDATION",
            validator_errors: validation.stderr,
            cover_letter: "SKIPPED"
        })
        mark_todo_failed(job_file, validation.stderr)
        CONTINUE  # next job_file

    # Phase 2: Generate pitch cover letter (WAIT for completion before proceeding)
    cover_letter_result = runSubagent(
        agent: "cover-letter-pitch",
        prompt: "Generate a pitch cover letter for: {job_file}"
    )
    # WAIT: Do not proceed until cover_letter_result is fully returned

    mark_todo_complete(job_file)
    results.append({
        job_file: job_file,
        resume: resume_result,
        cover_letter: cover_letter_result
    })

    # Only now move to the next job_file
```

**Validator rationale:** The resume-tailoring agent is instructed to run the validator itself in its Step 6, but agent self-enforcement is unreliable for long prompts (observed regressions: summary length, banned phrases, word count). The orchestrator re-runs the validator independently as a hard gate. If the agent's content fails validation here, the cover letter is not generated — there is no point pairing a polished cover letter with a rule-violating resume.

### 4. Verify Outputs

Check that all files were created for each job posting in `resumes/generated/tailored/`:
- `Alex_Johnson_{Company}_{Title}.docx` (resume)
- `Alex_Johnson_{Company}_{Title}_Cover_Letter.docx` (cover letter)

### 5. Clean Up JSON Files

Delete intermediate JSON files after successful DOCX generation:

```bash
rm resumes/generated/tailored/*_content.json
rm resumes/generated/tailored/*_cover_letter_pitch.json
```

Only retain the `.docx` files.

### 6. Report Summary

```markdown
## Resume Tailoring Complete

### Summary
- Job postings processed: X
- Resumes generated: Y
- Cover letters generated: Z

### Generated Documents

| Company | Title | Resume | Cover Letter | Keywords Matched |
|---------|-------|--------|--------------|------------------|
| ... | ... | ... | ... | ... |

### Keywords Not Matched
List any job keywords that could not be matched to CV content.

### Next Steps
1. Review generated DOCX files in `resumes/generated/tailored/`
2. Make any final manual adjustments
```

## Error Handling

| Error | Action |
|-------|--------|
| No files in Clippings/ | STOP - add job posting files first |
| Resume agent fails | Log error, skip cover letter + LinkedIn, continue to next job |
| Cover letter agent fails | Log error, continue to next job (resume still valid) |
| DOCX generation fails | Log error with details for manual recovery |

---

## Output Locations

```
resumes/generated/tailored/
├── Alex_Johnson_Company_Title.docx             # 1-page resume
├── Alex_Johnson_Company_Title_Cover_Letter.docx # Pitch cover letter
└── ...
```
