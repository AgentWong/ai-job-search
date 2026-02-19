# Full Resume Tailoring Orchestrator

Generate 2-page DOCX resumes AND cover letters for all job postings in `config/target_jobs/`.

---

## Prerequisites

Ensure dependencies are installed:
```bash
.venv/bin/pip install jinja2
```

---

## Execution

### 1. Enumerate Job Postings

List all markdown files in `config/target_jobs/`:

```
job_postings = glob("config/target_jobs/*.md")
```

If no files found, **STOP** and inform user to add job posting files first.

### 2. Create Todo Items

For each job posting:
```
FOR each file in job_postings:
    company, title = parse_filename(file)  # "Company - Title.md" -> company, title
    add_todo("Generate 2-page resume + cover letter for {company} - {title}")
```

### 3. Process Each Job Posting

**CRITICAL: Process job postings ONE AT A TIME, sequentially. Do NOT run subagents in parallel or in the background. Wait for each subagent to fully complete before starting the next one. Parallel execution causes hung tasks and excessive resource usage.**

For each job posting, invoke BOTH agents sequentially:

```
FOR each job_file in job_postings:
    mark_todo_in_progress(job_file)

    # Phase 1: Generate 2-page resume (WAIT for completion before proceeding)
    resume_result = runSubagent(
        agent: "resume-tailoring-2page",
        prompt: "Generate a tailored 2-page resume for: {job_file}"
    )
    # WAIT: Do not proceed until resume_result is fully returned

    # Phase 2: Generate cover letter (WAIT for completion before proceeding)
    cover_letter_result = runSubagent(
        agent: "cover-letter",
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

### 4. Verify Outputs

Check that both files were created for each job posting in `resumes/generated/tailored/`:
- `Alex_Johnson_{Company}_{Title}_2page.docx` (resume)
- `Alex_Johnson_{Company}_{Title}_Cover_Letter.docx` (cover letter)

### 5. Clean Up JSON Files

Delete intermediate JSON files after successful DOCX generation:

```bash
rm resumes/generated/tailored/*_content_2page.json
rm resumes/generated/tailored/*_cover_letter.json
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

---

## Error Handling

| Error | Action |
|-------|--------|
| No files in config/target_jobs/ | STOP - add job posting files first |
| Resume agent fails | Log error, skip cover letter, continue to next job |
| Cover letter agent fails | Log error, continue to next job (resume still valid) |
| DOCX generation fails | Log error with details for manual recovery |

---

## Output Locations

```
resumes/generated/tailored/
├── Alex_Johnson_Company_Title_content_2page.json    # Resume JSON
├── Alex_Johnson_Company_Title_2page.docx            # 2-page resume
├── Alex_Johnson_Company_Title_cover_letter.json     # Cover letter JSON
├── Alex_Johnson_Company_Title_Cover_Letter.docx     # Cover letter
└── ...
```

---

## Comparison with 1-Page Workflow

| Aspect | tailor-resume (1-page) | tailor-resume-full (2-page) |
|--------|------------------------|------------------------------|
| Word count | 400-475 | 880-990 |
| Summary section | No | Yes |
| Skills position | After Experience | Before Experience |
| Prior experience | No bullets | All roles have bullets |
| Cover letter | No | Yes |
| Output suffix | `.docx` | `_2page.docx` + `_Cover_Letter.docx` |
