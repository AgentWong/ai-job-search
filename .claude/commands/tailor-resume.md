# Resume Tailoring Orchestrator

Generate keyword-optimized DOCX resumes for all job postings in `config/target_jobs/`.

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
    company, title = parse_filename(file)  # "Company - Title.md" → company, title
    add_todo("Generate resume for {company} - {title}")
```

### 3. Process Each Job Posting

**CRITICAL: Process job postings ONE AT A TIME, sequentially. Do NOT run subagents in parallel or in the background. Wait for each subagent to fully complete before starting the next one. Parallel execution causes hung tasks and excessive resource usage.**

For each job posting, invoke the resume-tailoring agent:

```
FOR each job_file in job_postings:
    mark_todo_in_progress(job_file)

    # WAIT for full completion before proceeding to the next job
    result = runSubagent(
        agent: "resume-tailoring",
        prompt: "Generate a tailored resume for: {job_file}"
    )
    # WAIT: Do not proceed until result is fully returned

    mark_todo_complete(job_file)
    results.append(result)

    # Only now move to the next job_file
```

### 4. Verify Outputs

Check that DOCX files were created in `resumes/generated/tailored/`.

### 5. Report Summary

```markdown
## Resume Tailoring Complete

### Summary
- Job postings processed: X
- Resumes generated: Y

### Generated Resumes

| Company | Title | Output File | Keywords Matched |
|---------|-------|-------------|------------------|
| ... | ... | ... | ... |

### Keywords Not Matched
List any job keywords that could not be matched to CV content.

### Next Steps
1. Review generated DOCX files in `resumes/generated/tailored/`
2. Make any final manual adjustments
```

---

## Error Handling

| Error | Action |
|-------|--------|
| No files in config/target_jobs/ | STOP - add job posting files first |
| Agent fails for a job | Log error, continue to next job posting |
| DOCX generation fails | Log error with details for manual recovery |

---

## Output Location

```
resumes/generated/tailored/
├── Alex_Johnson_Company_Title_content.json   # Intermediate JSON
├── Alex_Johnson_Company_Title.docx           # Final resume
└── ...
```
