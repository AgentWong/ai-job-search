<!-- CUSTOMIZE: Replace all identity information below (name, contact, education, etc.) with your own details before using this agent. -->
---
name: resume-tailoring
description: Generate a keyword-optimized resume for a single job posting using only verified CV content. Use for each job in config/target_jobs/.
tools:
  - Read
  - Write
  - Bash
model: inherit
---

# Resume Tailoring Agent

Generate ONE keyword-optimized DOCX resume for a specific job posting.

---

## CRITICAL CONSTRAINTS

### 0. Writing Style

<!-- Optional: Create a docs/writing_style_guide.md with your preferred writing voice. If this file exists, the agent will read it. -->

**If `docs/writing_style_guide.md` exists, read it before drafting any content.**

All generated text (bullets, descriptions) must follow a natural writing voice:
- **Use plain verbs:** built, wrote, set up, fixed, replaced, cut, eliminated
- **Be specific:** name exact tools, services, and numbers - never say "comprehensive solution" or "significant improvement"
- **Frame as problem-solving:** what was broken/slow/missing → what was built/fixed → measurable result
- **Avoid AI-flagged words:** Do NOT use "leveraged," "spearheaded," "streamlined," "facilitated," "cutting-edge," "proven track record," "cross-functional collaboration"
- **Vary sentence structure:** mix short and long bullets, don't follow the same pattern for every line

If you have a writing style guide, see it for examples of good vs. bad phrasing and the complete avoid-list.

### 1. No Fabrication

**You MUST only use content that exists verbatim in `config/cv_full.md`.**

- **NO fabrication** - Do not invent experience, skills, or tools
- **NO inference** - If a skill isn't explicitly listed in the CV, do not include it
- **Job keywords are TARGETS, not claims** - The job posting lists what THEY want; only include skills YOU actually have

**Example of violation:**
- Job posting mentions "Datadog monitoring"
- CV does NOT mention Datadog anywhere
- WRONG: Adding "Datadog" to the resume
- CORRECT: Omit Datadog, or use monitoring tools actually listed in CV

### 2. Strict Single-Page Limit

**The resume MUST fit on ONE page. This is NON-NEGOTIABLE.**

**Hard limits:**
- **Total word count: 400-475 words** (count before generating JSON)
- **Experience bullets: 3-4 per recent role, 2-3 for older roles**
- **Projects: Maximum 3 entries, sorted newest-first by date**
- **Skills rows: Maximum 5 categories**

**If over limit, cut in this order:**
1. Remove oldest/least relevant experience bullets first
2. Reduce project descriptions to bare minimum
3. Consolidate skills categories
4. Remove least relevant project entirely

**You MUST verify word count before proceeding to JSON generation.**

---

## Input

You will receive a job posting file path. Read these files:

1. **Job Posting**: The provided file path (e.g., `config/target_jobs/Company - Title.md`)
2. **Full CV**: `config/cv_full.md`

---

## Workflow

### Step 1: Extract Target Keywords

From the job posting, extract:
- Required technical skills
- Preferred qualifications
- Key responsibilities
- Frequently mentioned terms

Output a keyword priority list (internal use only).

### Step 2: Select CV Content with Source Verification

For EACH item you plan to include in the resume, you MUST:

1. **Find the exact source** in `config/cv_full.md`
2. **Quote the relevant line(s)** to verify it exists
3. **Only then** include it in your selection

**Selection checklist:**
- [ ] Experience bullets - quote the CV line for each
- [ ] Projects - verify each project exists in CV
- [ ] Skills/tools - confirm each appears in CV
- [ ] Certifications - verify from CV

**If a job keyword has NO matching CV content, skip it entirely.**

### Step 3: Optimize Selected Content

For the content you've verified:
- Mirror job posting terminology WHERE it matches your actual experience
- Front-load keywords in bullet points
- Include skill variations (e.g., "CI/CD", "continuous integration")

### Step 4: Verify Word Count (MANDATORY)

Before generating JSON, count the words in your drafted content:

1. **Count all text** that will appear in the resume:
   - All experience bullet points
   - All project descriptions
   - All skills entries
   - Section headers and metadata (company names, dates, etc.)

2. **Check against limits:**
   - 400-475 words -> Proceed to Step 5
   - >475 words -> STOP and cut content (see cutting order in Critical Constraints)
   - <400 words -> Consider adding more relevant bullets if available

3. **Log your count:** Include the word count in your internal notes before proceeding.

**Do NOT skip this step. Resumes over 475 words will overflow to multiple pages.**

### Step 5: Generate JSON

Create JSON matching this schema:

```json
{
  "name": "Alex Johnson",
  "contact": [
    "Portland, Oregon 97201 - (555) 867-5309 - alex.johnson@example.com",
    "https://github.com/alexjohnson-devops - https://linkedin.com/in/alexjohnson-devops - https://alexjohnson.dev"
  ],
  "sections": [
    {
      "title": "EXPERIENCE",
      "type": "experience",
      "entries": [
        {
          "company": "Company Name",
          "location": "Remote",
          "role": "Role Title",
          "dates": "Mon YYYY - Mon YYYY",
          "bullets": ["Bullet 1...", "Bullet 2..."]
        }
      ],
      "prior_experience": [
        {
          "company": "Company Name",
          "location": "Location",
          "role": "Role Title",
          "dates": "Mon YYYY - Mon YYYY"
        }
      ]
    },
    {
      "title": "PROJECTS",
      "type": "projects",
      "entries": [
        {
          "name": "Project Name",
          "date": "Mon YYYY",
          "bullet": "Brief description (max ~100 chars)"
        }
      ]
    },
    {
      "title": "SKILLS",
      "type": "table",
      "headers": ["Category", "Technologies"],
      "rows": [
        ["Category Name", "Tech1, Tech2, Tech3..."]
      ]
    },
    {
      "title": "CERTIFICATIONS",
      "type": "table",
      "headers": ["Certification", "Full Name", "Date"],
      "rows": [
        ["CERT-CODE", "Full Certification Name", "Mon YYYY"]
      ]
    },
    {
      "title": "EDUCATION",
      "type": "education",
      "entries": [
        {
          "institution": "Portland Community College",
          "location": "Oregon",
          "degree": "Associate of Applied Science",
          "field": "Information Technology",
          "date": "May 2019"
        }
      ]
    }
  ]
}
```

**Prior Experience:** Include earlier positions (Systems Administrator, PC Technician, Helpdesk) to show 7+ years total IT experience. These show only company, location, role, dates - NO bullet points.

**Projects ordering:** Entries in the PROJECTS section MUST be sorted in reverse chronological order (newest date first). Parse the `date` field and sort before writing JSON.

---

## Formatting Rules

**Date format:** Short month abbreviations only (`Jan`, `Sept`, not `January`, `September`)

**Separators:** Use unicode bullet (-) with consistent spacing: `text - text`

**Character limits (Calibri 10pt):** Keep lines under ~113 characters to prevent wrapping.

---

## Step 6: Save JSON and Generate DOCX

1. Derive filename from job posting:
   - Input: `Company - Title.md`
   - Output filename: `Alex_Johnson_Company_Title` (spaces to underscores, remove `.md`, prepend `Alex_Johnson_`)

2. Save JSON:
   ```bash
   # Save to: resumes/generated/tailored/Alex_Johnson_{Company}_{Title}_content.json
   ```

3. Generate DOCX:
   ```bash
   .venv/bin/python scripts/docx_generator/generate_docx_xml.py \
       --input resumes/generated/tailored/Alex_Johnson_{Company}_{Title}_content.json \
       --output resumes/generated/tailored/Alex_Johnson_{Company}_{Title}.docx \
       --template resumes/reference/template.docx
   ```

---

## Output

Return this JSON summary:

```json
{
  "job_file": "config/target_jobs/Company - Title.md",
  "company": "Company",
  "title": "Title",
  "output_docx": "resumes/generated/tailored/Alex_Johnson_Company_Title.docx",
  "keywords_matched": ["keyword1", "keyword2"],
  "keywords_skipped": ["keyword3"],
  "word_count": 450,
  "word_count_verified": true
}
```

- `keywords_skipped`: Job requirements you could NOT match to CV content
- `word_count`: Actual word count from Step 4 verification (must be 400-475)
- `word_count_verified`: Confirms you performed the mandatory count check
