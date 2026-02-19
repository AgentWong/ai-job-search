# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-assisted job search automation using GitHub Copilot workflows with Claude models. The system discovers, evaluates, and tracks cloud infrastructure engineering positions through structured workflows executed as prompt files.

This is a showcase project demonstrating practical AI/LLM usage for job searching. All configuration files are working examples for a Cloud Infrastructure Engineer role -- customize them for your own target role.

## Architecture: Orchestrator + Dedicated Agents

All workflows use an **orchestrator + dedicated agent pattern** to prevent context degradation:

```
Orchestrator (prompt file): Load configs → Build task queue → Track progress
    ↓
FOR EACH task:
    Agent (agent file): Execute isolated task → Return structured JSON
    ↓
Orchestrator: Aggregate results → Write outputs → Report
```

This pattern is critical because:
- Search results and job descriptions consume significant context
- Each agent gets clean context for accurate analysis
- The orchestrator maintains state across many iterations
- Agents are reusable across multiple orchestrator workflows

### Agent Files (`.github/agents/`)

| Agent | Purpose | Used By |
|-------|---------|---------|
| `firecrawl-job-search.agent.md` | Search/scrape with Firecrawl, filter & score positions | ats-platform-search, company-monitoring |
| `hiringcafe-job-search.agent.md` | Search Hiring Cafe, extract & score from search cards in single pass | hiringcafe-job-search |
| `company-evaluator.agent.md` | Evaluate companies for monitoring inclusion | company-curation |

### Orchestrator-Agent Relationship

Orchestrators (`.github/prompts/*.prompt.md`) handle:
- Loading configuration files
- Building task queues
- Invoking agents via `runSubagent(agent: "agent-name", prompt: "...")`
- Aggregating results and writing outputs

Agents (`.github/agents/*.agent.md`) handle:
- Single isolated task execution
- Tool usage (Firecrawl, Chrome DevTools)
- Filtering and scoring logic
- Returning structured JSON

### Single-Phase Pattern (Hiring Cafe)

Hiring Cafe uses a **single-phase agent** because full scoring data is available without visiting detail pages. Search cards display AI-parsed metadata (title, company, salary, YOE, tech tools, requirements summary). All scoring criteria visible on cards. URL-based filter state -- no UI interaction needed. No login required.

## Workflow Prompts

Located in `.github/prompts/`:

| Prompt | Purpose | Agent Used |
|--------|---------|------------|
| `ats-platform-search.prompt.md` | Search job boards (Greenhouse, Lever, etc.) | firecrawl-job-search |
| `company-monitoring.prompt.md` | Monitor curated company career pages | firecrawl-job-search |
| `company-curation.prompt.md` | Curate companies for direct monitoring | company-evaluator |
| `hiringcafe-job-search.prompt.md` | Search Hiring Cafe with structured metadata | hiringcafe-job-search |

## Resume Tailoring

Located in `.claude/commands/`:

| Command | Purpose | Agents Used |
|---------|---------|-------------|
| `/tailor-resume` | Generate 1-page keyword-optimized resumes | resume-tailoring |
| `/tailor-resume-full` | Generate 2-page resumes + cover letters | resume-tailoring-2page, cover-letter |

## Configuration Hierarchy

### Core Configuration (`config/`)
- `inclusions.yml` - Job boards and target roles in priority order
- `job_preferences.md` - Work arrangement, technical requirements, salary
- `exclusions.yml` - Companies and patterns to skip
- `cv_full.md` - Complete work history for resume generation

### Shared Rules (`shared/`)
- `scoring_framework.md` - Position scoring (0-10 scale) with boosters, penalties, and disqualifiers
- `company_evaluation_rules.md` - Company filtering by size, business model, industry
- `technical_requirements.md` - Technical skill matching criteria

## Output Files

### Main Output
- `results/application_queue.csv` - Qualified positions (company, title, URL, score)

### Generated Resumes
- `resumes/generated/tailored/` - Tailored DOCX resumes and cover letters

## Resume Generation Workflow

The resume generation workflow uses a manual curation approach:
1. Review `results/application_queue.csv` for promising job postings
2. Save job posting markdown files to `config/target_jobs/`
3. Run `/tailor-resume` or `/tailor-resume-full` command
4. Each subagent produces a tailored DOCX resume optimizing for that specific posting's keywords

## MCP Tools

The workflows rely on MCP (Model Context Protocol) servers:

1. **Firecrawl MCP** - Web scraping and search (`firecrawl_search`, `firecrawl_scrape`)
   - Configured via `.mcp.json` (see `.mcp.json.example` for setup)
   - Requires `FIRECRAWL_API_KEY`
   - Used by: ats-platform-search, company-monitoring, company-curation

2. **Chrome DevTools MCP** - Browser automation for job boards requiring JavaScript
   - Requires Chrome running with remote debugging: `./scripts/start-chrome-debug.sh`
   - Connects to `http://127.0.0.1:9222`
   - Used by: hiringcafe-job-search

## Resume Generation Rules

When modifying resume templates or generation logic:

1. **Date format**: Use short month abbreviations only (`Jan`, `Sept`, not `January`, `September`)
2. **Word count**: ~450 words for single page, ~900 words for 2-page
3. **Projects section**: Compact single-line format, no tables or URLs
4. **Template structure**: Follow `resumes/reference/template.docx` formatting

## Scoring Quick Reference

| Score | Classification | Action |
|-------|----------------|--------|
| 8-10 | Exceptional | Apply immediately |
| 6-7 | Strong | Apply |
| 4-5 | Moderate | Manual review |
| 0-3 | Disqualified | Skip |

Key boosters: Terraform (+2), Ansible (+2), AWS-focused (+2)
Key disqualifiers: Senior/Staff/Lead titles, GCP-only, non-remote, 24/7 on-call, Crypto/Blockchain/Web3, AI startups (<10K employees), "software development experience" requirements
