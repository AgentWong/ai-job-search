# AI Job Search Automation

AI-assisted job search automation built on [Claude Code](https://claude.com/claude-code) slash commands and subagents. Discovers, filters, and scores cloud infrastructure engineering positions across ATS platforms and job boards, then generates tailored resumes and cover letters for the best matches.

**This is not an auto-apply tool.** It automates the tedious parts of job searching (finding, filtering, scoring) so you can focus your time on applications worth submitting.

**This is a public showcase repo.** All personal data — the candidate's real name, contact info, employers, and application history — has been replaced with a fictional "Alex Johnson" persona. See [Customizing for Your Own Job Search](#customizing-for-your-own-job-search) to adapt it.

## How It Works

The system uses an **orchestrator + dedicated agent pattern**, where slash commands (`.claude/commands/`) coordinate isolated subagents (`.claude/agents/`) for each task:

```
Orchestrator (.claude/commands/*.md): Load configs → Build task queue → Track progress
    ↓
FOR EACH task:
    Agent (.claude/agents/*.agent.md): Execute isolated task → Return structured JSON
    ↓
Orchestrator: Aggregate results → Write outputs → Report
```

**Why this pattern?** Job descriptions are token-heavy — a single search can return dozens of results with full descriptions. Delegating each search or generation task to an isolated subagent keeps the orchestrator's context clean across many iterations, and every agent gets fresh context for accurate analysis.

### Python-stages, LLM-reviews

Where possible, deterministic work (pagination, regex filtering, scoring math, CSV I/O) runs in Python scripts instead of an LLM context. The LLM is reserved for judgment calls: fuzzy disqualification against the scoring framework, matching resume content to a job posting, writing prose. This keeps the token-heavy steps cheap and the model-driven steps focused. See [docs/llm-deterministic-offload-strategy.md](docs/llm-deterministic-offload-strategy.md) for the pattern written up in the abstract.

## Included Workflows

### Job Discovery

| Command | What It Does | Backing |
|---------|--------------|---------|
| `/ats-platform-search` | Search ATS platforms (Greenhouse, Lever, Ashby, Workday, etc.) for open positions via Firecrawl | `scripts/ats_platform_search/` → `ats-platform-review` agent |
| `/ats-platform-validate` | Reachability probe for candidate ATS/job-board domains before adding them to `config.yml` | `scripts/ats_platform_validate/` |
| `/ats-api-search` | Fetch jobs directly from curated companies' public ATS APIs (Ashby, Greenhouse, Lever, SmartRecruiters, Rippling, Workday, Dayforce, iSolvedHire) | `scripts/ats_scraper/` → `ats-api-llm-review` agent |
| `/linkedin-api-search` | Fetch jobs from LinkedIn's public guest API | `scripts/linkedin_scraper/` → `linkedin-llm-review` agent |
| `/builtin-api-search` | Fetch jobs from Built In's public API | `scripts/builtin_scraper/` → `builtin-llm-review` agent |
| `/hiringcafe-job-search` | Search [Hiring Cafe](https://hiring.cafe) using its AI-enriched metadata cards, then resolve outbound ATS/company URLs via browser automation | `hiringcafe-job-search` agent → `browser-fetch` agent |

The script-driven workflows (`ats-api-search`, `linkedin-api-search`, `builtin-api-search`) hit public job-board APIs directly — no scraping credits spent on search. Python does the pagination, regex pre-filtering, and scoring; a single LLM review pass then applies fuzzy judgment (title typos, non-US locations Python's regex missed, subtle disqualifiers in the full description) before qualified rows are written to `results/application_queue.csv`.

### Resume & Cover Letter Generation

| Command | What It Does |
|---------|--------------|
| `/tailor-resume` | Generate a 1-page keyword-optimized resume + 3-paragraph pitch cover letter for each job posting in `config/target_jobs/` |
| `/tailor-resume-full` | Generate a 2-page resume + point-by-point cover letter + LinkedIn outreach message for each job posting |
| `/process-clippings` | Process new job postings clipped into `Clippings/` and organize them into `config/target_jobs/` |

Resume tailoring uses `config/cv_full.md` as the sole source of truth. Agents extract keywords from the job posting, match them against verified CV content, and generate a DOCX resume — **no fabrication**: if a skill isn't in your CV, it won't appear on the resume. Populate `.claude/skills/writing-style/SKILL.md` with samples of your own writing so generated resumes and cover letters sound like you, not like an LLM.

### Maintenance

| Command | What It Does |
|---------|--------------|
| `/data-analysis` | Monthly: aggregate effectiveness tracking + application history into a report; recommends `config.yml` tuning |

## Cost

This project is designed to run on flat-rate consumer plans, not metered API billing. Because the token-heavy work (pagination, filtering, scoring math, CSV I/O) is offloaded to Python and only judgment calls hit the LLM, the whole search-and-tailor loop fits comfortably inside a Claude Pro subscription.

| Service | Plan | Cost | Needed for |
|---------|------|------|------------|
| [Claude Code](https://claude.com/claude-code) | Claude Pro | **$20/mo** (less on an annual commitment) | Every workflow (the orchestrators and review agents) |
| [Firecrawl](https://www.firecrawl.dev/) | Hobby | **$19/mo** | Only `/ats-platform-search` and `/ats-platform-validate` |

**Total: ~$39/mo**, or just **$20/mo** if you skip the Firecrawl-backed platform search and rely on the direct-API discovery workflows (`/ats-api-search`, `/linkedin-api-search`, `/builtin-api-search`) and `/hiringcafe-job-search`, which hit public endpoints and cost nothing beyond your Claude plan.

**Why it stays this cheap:**

- **The [Python-stages, LLM-reviews](#python-stages-llm-reviews) split** keeps searches, filtering, and scoring math off the LLM. The model is invoked only for fuzzy disqualification and prose generation, so a Claude Pro plan's usage limits are enough for regular runs.
- **Firecrawl credit refunds.** Each `/v2/search` call costs ~2 credits per 10 results, and the workflow immediately submits feedback via `/v2/search/{id}/feedback` to refund 1 credit per query — roughly halving the effective search cost. (Refunds are capped at ~100/day by Firecrawl.)
- **Direct-API discovery is free.** The ATS-API, LinkedIn, Built In, and Hiring Cafe workflows use public/guest endpoints — no scraping credits are spent on search.

Your actual Claude usage depends on how often you run searches and how many resumes/cover letters you generate; heavy daily use may bump into Pro's rate limits, in which case the Max plan raises the ceiling.

## Quick Start

### Prerequisites

- [Claude Code](https://claude.com/claude-code) (VS Code extension, desktop app, or CLI)
- Python 3.x with venv (scrapers, filters, and DOCX generation)
- Node.js (for MCP servers via `npx`)
- Google Chrome (only for the `/hiringcafe-job-search` workflow)
- A [Firecrawl](https://www.firecrawl.dev/) API key (only for `/ats-platform-search` and `/ats-platform-validate`)

### Setup

1. **Clone the repo:**
   ```bash
   git clone https://github.com/your-username/ai-job-search
   cd ai-job-search
   ```

2. **Install Python dependencies:**
   ```bash
   python -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

3. **Configure MCP servers:**
   ```bash
   cp .mcp.json.example .mcp.json
   ```
   Edit `.mcp.json` and set `FIRECRAWL_API_KEY` to your own key (only needed for the ATS platform search/validate workflows). Don't commit `.mcp.json` — it's gitignored.

4. **For the Hiring Cafe workflow, start Chrome with remote debugging:**
   ```bash
   ./scripts/start-chrome-debug.sh
   ```

5. **Customize for your own job search** (see below).

### Customizing for Your Own Job Search

All configuration is in `config/`. The included files are a working example for a mid-level Cloud/DevOps Engineer search under a fictional "Alex Johnson" persona — replace them with your own.

| File | What to Change |
|------|-----------------|
| `config/cv_full.md` | Replace with your complete work history |
| `config/linkedin_profile.md` | Replace with your LinkedIn profile content (used for outreach message generation) |
| `config/job_preferences.md` | Set your remote/salary/industry/experience preferences |
| `config/config.yml` | Job boards, target role tiers, and the `location` block (remote vs. local search, your residence state for eligibility checks) |
| `config/exclusions.yml` | Companies you've already applied to, been rejected by, or want to skip |
| `config/company_targets_ats.csv` | Curate companies for the ATS API scraper to monitor directly (regenerate `company_targets_ats.json` after editing, via `scripts/curation_appender/rebuild_companion.py`) |
| `.claude/skills/writing-style/SKILL.md` | Add samples of your own writing so AI-generated resumes and cover letters sound like you |

The `shared/` directory contains scoring rules referenced by every review agent:

| File | What to Change |
|------|-----------------|
| `shared/scoring_framework.md` | Score boosters/penalties/disqualifiers for your tech stack |
| `shared/technical_requirements.md` | Update to match your technical background |
| `shared/company_evaluation_rules.md` | Company size/industry/business-model filters |

## Repository Structure

```
ai-job-search/
├── .claude/
│   ├── commands/         # Slash commands (orchestrators)
│   ├── agents/           # Subagents (isolated task execution)
│   └── skills/           # writing-style: your voice, for resume/cover-letter prose
├── config/
│   ├── cv_full.md            # Complete work history (source of truth)
│   ├── linkedin_profile.md   # LinkedIn profile content
│   ├── job_preferences.md    # Search criteria and preferences
│   ├── config.yml            # Job boards, target roles, location targeting
│   ├── exclusions.yml        # Companies to skip
│   ├── company_targets_ats.csv/.json  # Curated companies for the ATS API scraper
│   └── target_jobs/          # Job postings staged for resume tailoring
├── shared/
│   ├── scoring_framework.md         # Position scoring rules
│   ├── company_evaluation_rules.md  # Company filtering rules
│   └── technical_requirements.md    # Technical matching criteria
├── scripts/               # Scrapers, filters, scorers, DOCX generators (Python)
├── resumes/
│   ├── reference/         # DOCX templates
│   └── generated/         # Output: tailored resumes/cover letters
├── results/               # Output: application_queue.csv
├── tests/                 # Unit tests for the deterministic Python layer
└── docs/                  # Workflow guides and design notes
```

## Scoring System

Positions are scored on a 0-10 scale:

| Score | Classification | Action |
|-------|-----------------|--------|
| 8-10 | Exceptional | Apply immediately |
| 6-7 | Strong | Apply |
| 4-5 | Moderate | Manual review |
| 0-3 | Disqualified | Skip |

Key boosters: Terraform (+2), Ansible (+2), AWS-focused (+2)
Key disqualifiers: Senior/Staff/Lead titles, GCP-only, non-remote, 24/7 on-call, Crypto/Blockchain/Web3, AI startups (<10K employees), "software development experience" requirements

All scoring logic lives in `shared/scoring_framework.md` — customize it for your own tech stack and preferences.

## Documentation

- [Resume Tailoring Workflow](docs/workflow-resume-tailoring.md) — end-to-end flow, agent responsibilities, output format
- [LLM-Deterministic Offload Strategy](docs/llm-deterministic-offload-strategy.md) — the Python-stages/LLM-reviews pattern in the abstract
- [Pipeline Events Guide](docs/pipeline-events-guide.md) — tracking application status by hand after you apply

## Responsible Use

This project automates job *discovery*, not job *applications*. Please:

- Respect the terms of service of any platform you interact with
- Use reasonable rate limits — don't hammer job board APIs
- Review every generated resume and cover letter before submitting; AI output needs human review
- This project does not include workflows for platforms that prohibit automated access (e.g. LinkedIn's authenticated site, Indeed, Glassdoor). The LinkedIn workflow here uses only LinkedIn's public, unauthenticated guest API.

## Disclaimers

**Target audience:** Built for a mid-level infrastructure/DevOps job search. It assumes comfort with the command line, scripting, YAML configuration, and AI tooling.

**Platform support:** Developed and tested on Linux. macOS should work with minimal adjustments. Windows users may need WSL or Git Bash for the shell scripts.

## License

MIT
