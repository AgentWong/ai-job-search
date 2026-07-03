# Full Resume Tailoring Orchestrator

Generate 2-page DOCX resumes and point-by-point cover letters for all job postings in `Clippings/`.

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
    company, title = parse_filename(file)  # "Company - Title.md" -> company, title
    add_todo("Generate 2-page resume + cover letter for {company} - {title}")
```

### 3. Process Each Job Posting

**CRITICAL: Process job postings ONE AT A TIME, sequentially. Do NOT run subagents in parallel or in the background. Wait for each subagent to fully complete before starting the next one. Parallel execution causes hung tasks and excessive resource usage.**

For each job posting, invoke BOTH agents sequentially with a validator gate between them:

```
FOR each job_file in job_postings:
    mark_todo_in_progress(job_file)

    # Phase 1: Generate 2-page resume (WAIT for completion before proceeding)
    resume_result = runSubagent(
        agent: "resume-tailoring-2page",
        prompt: "Generate a tailored 2-page resume for: {job_file}"
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
    json_path = "resumes/generated/tailored/Alex_Johnson_{company}_{title}_content_2page.json"
    validation = bash(
        ".venv/bin/python scripts/validate_resume_content.py "
        "{json_path} --type 2page --posting '{job_file}'"
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

    # Phase 2: Generate cover letter (WAIT for completion before proceeding)
    cover_letter_result = runSubagent(
        agent: "cover-letter-pitch",
        prompt: "Generate a cover letter for: {job_file}"
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

**Validator rationale:** The resume-tailoring agent is instructed to run the validator itself in its Step 8, but agent self-enforcement is unreliable for long prompts (observed regressions: summary length, banned phrases, word count). The orchestrator re-runs the validator independently as a hard gate. If the agent's content fails validation here, the cover letter is not generated — there is no point pairing a polished cover letter with a rule-violating resume.

### 4. Verify Outputs

Check that all files were created for each job posting in `resumes/generated/tailored/`:
- `Alex_Johnson_{Company}_{Title}_2page.docx` (resume)
- `Alex_Johnson_{Company}_{Title}_Cover_Letter.docx` (cover letter)

### 5. Clean Up JSON Files

Delete intermediate JSON files after successful DOCX generation:

```bash
rm resumes/generated/tailored/*_content_2page.json
rm resumes/generated/tailored/*_cover_letter_pitch.json
```

Only retain the `.docx` files.

### 6. Report Summary

```markdown
## Full Resume Tailoring Complete

### Summary
- Job postings processed: X
- Resumes generated: Y
- Cover letters generated: Z

### Generated Documents

| Company | Title | Resume | Cover Letter | Resume Keywords | Requirements Addressed |
|---------|-------|--------|--------------|-----------------|------------------------|
| ... | ... | ... | ... | ... | ... |

### Keywords Not Matched (Resume)
List any job keywords that could not be matched to CV content.

### Requirements Not Addressed (Cover Letter)
List any requirements that had no matching CV evidence.

### Next Steps
1. Review generated DOCX files in `resumes/generated/tailored/`
2. Verify formatting in Word/LibreOffice
3. Make any final manual adjustments before submitting
```

## Error Handling

| Error | Action |
|-------|--------|
| No files in Clippings/ | STOP - add job posting files first |
| Resume agent fails | Log error, skip cover letter, continue to next job |
| Cover letter agent fails | Log error, continue to next job (resume still valid) |
| DOCX generation fails | Log error with details for manual recovery |

---

## Output Locations

```
resumes/generated/tailored/
├── Alex_Johnson_Company_Title_content_2page.json    # Resume JSON (cleaned up)
├── Alex_Johnson_Company_Title_2page.docx            # 2-page resume
├── Alex_Johnson_Company_Title_cover_letter_pitch.json  # Cover letter JSON (cleaned up)
├── Alex_Johnson_Company_Title_Cover_Letter.docx     # Cover letter
└── ...
```

---

## Comparison with 1-Page Workflow

| Aspect | tailor-resume (1-page) | tailor-resume-full (2-page) |
|--------|------------------------|------------------------------|
| Resume word count | 400-475 | 880-990 |
| Summary section | No | Yes |
| Skills position | After Experience | After Projects (ATS keyword soup) |
| Experience bullets | Multi-pass: 2-6 recent, 0-3 others | All roles with bullets |
| Cover letter style | 3-paragraph pitch (150-250 words) | 3-paragraph pitch with technical problem analysis (150-250 words) |
| LinkedIn message | Yes | No |
| Output files | `.docx` + `_Pitch_Letter.docx` + `_linkedin.txt` | `_2page.docx` + `_Cover_Letter.docx` |
