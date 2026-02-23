# AI Job Search Automation

AI-assisted job search automation using [GitHub Copilot](https://github.com/features/copilot) prompt files and Claude models. Discovers, evaluates, scores, and tracks job positions through structured agent workflows -- then generates tailored resumes and cover letters for the best matches.

**This is not an auto-apply tool.** It automates the tedious parts of job searching (finding, filtering, scoring) so you can focus your time on applications worth submitting.

## How It Works

The system uses an **Orchestrator + Agent pattern** where prompt files coordinate isolated subagents for each task:

```
Orchestrator (prompt file)
├── Load configuration (roles, preferences, exclusions)
├── Build task queue (which boards to search, which roles)
├── FOR EACH task:
│   └── Agent (agent file): Execute isolated search → Filter → Score → Return JSON
├── Aggregate all results
├── Deduplicate against existing queue
└── Write results to CSV + report
```

**Why this pattern?** Job descriptions are token-heavy. A single search can return 25+ results with full descriptions. By delegating each search to an isolated subagent, the orchestrator maintains clean context across many iterations, and each agent gets fresh context for accurate analysis.

### MCP Tools

The workflows use [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) servers to interact with external services:

- **[Firecrawl MCP](https://github.com/firecrawl/firecrawl-mcp-server)** -- Web search and scraping for ATS platforms (Greenhouse, Lever, Ashby, etc.)
- **[Chrome DevTools MCP](https://github.com/ChromeDevTools/chrome-devtools-mcp)** -- Browser automation for JavaScript-heavy job boards (Hiring Cafe)

## Included Workflows

### Job Discovery

| Workflow | What It Does | MCP Tool | Docs |
|----------|-------------|----------|------|
| `/ats-platform-search` | Search ATS platforms (Greenhouse, Lever, Ashby, Workday, etc.) for open positions | Firecrawl | [Guide](docs/ats-platform-search.md) |
| `/hiringcafe-job-search` | Search [Hiring Cafe](https://hiring.cafe) using its AI-enriched metadata cards | Chrome DevTools | [Guide](docs/hiringcafe-job-search.md) |
| `/company-monitoring` | Monitor a curated list of company career pages for new openings | Firecrawl | [Guide](docs/company-monitoring.md) |
| `/company-curation` | Discover and validate new companies to add to the monitoring list | Firecrawl | [Guide](docs/company-curation.md) |

### Resume Tailoring

| Command | What It Does | Docs |
|---------|-------------|------|
| `/tailor-resume` | Generate a 1-page keyword-optimized DOCX resume for each job in `config/target_jobs/` | [Guide](docs/resume-tailoring.md) |
| `/tailor-resume-full` | Generate a 2-page resume + cover letter for each job in `config/target_jobs/` | [Guide](docs/resume-tailoring.md) |

Resume tailoring uses your `config/cv_full.md` as the source of truth. The agent extracts keywords from the job posting, matches them to your actual experience, and generates a DOCX file using your template. **No fabrication** -- if a skill isn't in your CV, it won't appear on the resume. For resumes that sound like you wrote them (not like ChatGPT wrote them), populate `docs/writing_style_guide.md` with samples of your actual writing.

## Quick Start

### Prerequisites

- [VS Code](https://code.visualstudio.com/) with [GitHub Copilot](https://github.com/features/copilot) (Claude model access)
- [Node.js](https://nodejs.org/) (for MCP servers via `npx`)
- Python 3.x with venv (for DOCX generation)
- Google Chrome (for Hiring Cafe workflow only)

### Setup

1. **Clone the repo:**
   ```bash
   git clone https://github.com/AgentWong/ai-job-search
   cd ai-job-search
   ```

2. **Install Python dependencies:**
   ```bash
   python -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

3. **Configure MCP servers:**

   Copy the example config for Chrome DevTools:
   ```bash
   cp .mcp.json.example .mcp.json
   ```

   Install the **Firecrawl MCP Server** from the [VS Code Extensions Marketplace](https://marketplace.visualstudio.com/items?itemName=nicepkg.firecrawl-mcp) (filter by "MCP Servers"). The extension prompts you for your API key and stores it securely outside the repo -- this avoids accidentally committing secrets to git. Get a Firecrawl API key at [firecrawl.dev](https://www.firecrawl.dev/).

4. **For browser workflows (Hiring Cafe), start Chrome:**
   ```bash
   ./scripts/start-chrome-debug.sh
   ```

5. **Customize for your job search** (see below).

### Customizing for Your Job Search

All configuration is in the `config/` directory. The included files are working examples for a Cloud Infrastructure Engineer role.

| File | What to Change |
|------|---------------|
| `config/cv_full.md` | Replace with your complete work history |
| `config/job_preferences.md` | Set your remote/salary/industry/experience preferences |
| `config/inclusions.yml` | Define which ATS boards to search and which role titles to look for |
| `config/exclusions.yml` | Add companies you've already applied to or want to skip |
| `config/company_targets.csv` | Curate companies you want to monitor directly |
| `docs/writing_style_guide.md` | Add samples of your own writing so AI-generated resumes sound like you (see [guide](docs/writing_style_guide.md)) |

The `shared/` directory contains scoring rules that reference your preferences:

| File | What to Change |
|------|---------------|
| `shared/scoring_framework.md` | Adjust score boosters/penalties for your tech stack |
| `shared/technical_requirements.md` | Update to match your technical background |
| `shared/company_evaluation_rules.md` | Adjust company size/industry filters |

## Repository Structure

```
ai-job-search/
├── .github/
│   ├── prompts/          # Orchestrator workflows (run these)
│   └── agents/           # Reusable subagents (called by orchestrators)
├── .claude/
│   ├── commands/         # Slash commands (/tailor-resume, /tailor-resume-full)
│   └── agents/           # Resume tailoring subagents
├── config/
│   ├── cv_full.md        # Your complete work history
│   ├── job_preferences.md # Search criteria and preferences
│   ├── inclusions.yml    # Job boards and target roles
│   ├── exclusions.yml    # Companies to skip
│   ├── company_targets.csv # Companies to monitor
│   └── target_jobs/      # Job postings for resume tailoring
├── shared/
│   ├── scoring_framework.md      # Position scoring rules
│   ├── company_evaluation_rules.md # Company filtering rules
│   └── technical_requirements.md   # Technical matching criteria
├── scripts/
│   ├── start-chrome-debug.sh     # Chrome setup for browser workflows
│   └── docx_generator/           # Python DOCX generation scripts - 1-page resume
│   └── docx_generator_v2/        # Python DOCX generation scripts - 2-page resume
├── resumes/
│   ├── reference/        # DOCX templates
│   └── generated/tailored/ # Output: generated resumes
├── results/
│   └── application_queue.csv # Output: qualified positions
└── docs/                 # Additional documentation
    └── writing_style_guide.md  # Template for your writing voice
```

## Scoring System

Positions are scored on a 0-10 scale:

| Score | Classification | Action |
|-------|----------------|--------|
| 8-10 | Exceptional | Apply immediately |
| 6-7 | Strong | Apply |
| 4-5 | Moderate | Manual review |
| 0-3 | Disqualified | Skip |

The scoring considers:
- **Boosters:** Terraform (+2), Ansible (+2), AWS-focused (+2), education flexibility (+1)
- **Penalties:** Azure-primary (-1), travel requirements (-2), large company (-1)
- **Disqualifiers:** Senior/Staff/Lead titles, GCP-only, non-remote, crypto/blockchain, "software development experience" requirements

All scoring logic is in `shared/scoring_framework.md` -- customize it for your own tech stack and preferences.

## Documentation

Detailed guides for each workflow are in the [`docs/`](docs/) directory:

- [ATS Platform Search](docs/ats-platform-search.md) -- Search parameters, credit usage, and tuning tips
- [Hiring Cafe Job Search](docs/hiringcafe-job-search.md) -- Chrome setup, single-phase agent, filter customization
- [Company Monitoring](docs/company-monitoring.md) -- Run cadence, evaluation rules, validation reports
- [Company Curation](docs/company-curation.md) -- Building and managing your target company list
- [Company Targets Maintenance](docs/company_targets_maintenance.md) -- CSV format, exclusions, monthly audit process
- [Resume Tailoring](docs/resume-tailoring.md) -- End-to-end workflow from job clipping to PDF submission

## Pricing

This project uses paid services. Here's what I use and what it costs:

| Service | Plan | Cost | Required? |
|---------|------|------|-----------|
| [GitHub Copilot](https://github.com/features/copilot) | Pro | $10/month | Yes |
| [Anthropic Claude](https://claude.com/pricing) | Pro | ~$17/month (billed yearly at $200) | No |
| [Firecrawl](https://www.firecrawl.dev/pricing) | Hobby | $19/month + ~$18/month in credit recharges | No |

**GitHub Copilot** is the bare minimum. Its request-based pricing model is well-suited for agentic workflows where a single orchestrator run can spawn many subagent calls. I use Claude Sonnet 4.6 within Copilot for the most predictable results -- ChatGPT and Gemini can produce unexpected output in these workflows. Other AI models are not thoroughly tested.

**Claude Pro** is optional but generally useful. I use it for Claude Code (VS Code integration), which powers the resume tailoring slash commands. Having both Copilot and Claude gives flexibility across pricing models -- Copilot uses request-based limits while Claude uses token-based usage limits. If you skip Claude Pro, the resume tailoring commands (currently in `.claude/commands/`) would need to be migrated into `.github/prompts/` and adjusted for Copilot's agent system.

**Firecrawl** is the most expensive component. The Hobby plan ($19/month) includes credits, but I typically recharge twice a month at $9 each (limit of 4 recharges/month), bringing the real cost closer to $37/month. I only use Firecrawl for job searching, so I can cancel anytime between job search campaigns. Firecrawl is **not an absolute requirement** -- alternatives include using Google Search directly through a Chrome DevTools MCP browser session, or a Google Search MCP server depending on search volume. I personally find Firecrawl's LLM-friendly markdown output worth the cost.

## Responsible Use

This project automates job *discovery*, not job *applications*. Please:

- Respect the terms of service of any platform you interact with
- Use reasonable rate limits and don't hammer job board APIs
- Review all generated resumes before submitting -- AI output needs human review
- This project does not include workflows for platforms that prohibit automated access

**LinkedIn, Indeed, and Glassdoor:** These platforms have terms of service that restrict or prohibit automated access and scraping. I do not endorse using this project against their websites. My workflows use negative search operators (e.g., `-site:linkedin.com`) specifically because their anti-scraping measures produce non-scrapable results that waste Firecrawl API credits.

## Disclaimers

**Target audience:** This project was built by a mid-level IT professional (my last role was as a remote DevOps Engineer). It assumes comfort with the command line, scripting, YAML configuration, and AI tooling. It may not be suitable for recent graduates, entry-level IT users who aren't comfortable with automation, or non-technical users.

**Platform support:** This project has only been tested on macOS. I do not have a Windows machine to test with. Windows users may need to install Python and Node.js manually, and shell scripts (`.sh`) may require WSL or Git Bash. Linux should work with minimal adjustments.

## License

MIT
