# Browser Automation Scripts

This directory contains helper scripts for browser-based job search automation using the chrome-devtools MCP server.

## Quick Start

### Step 1: Start Chrome with Debugging Enabled

Run the startup script:
```bash
./scripts/start-chrome-debug.sh
```

This will:
- Launch Chrome with remote debugging on port 9222
- Use a dedicated profile at `~/.chrome-job-hunt-automation`
- Keep your automation browser separate from your main Chrome profile

### Step 2: Run a Browser Workflow

In VS Code with GitHub Copilot (Claude model):
1. Open a workflow prompt (e.g., `.github/prompts/hiringcafe-job-search.prompt.md`)
2. Run the prompt
3. The AI agent will use Chrome DevTools MCP to interact with the browser

## DOCX Generators

The `docx_generator_v2/` directory contains Python scripts for generating Word documents:

- `generate_resume_2page.py` - Generate a 2-page resume from JSON content
- `generate_cover_letter.py` - Generate a cover letter from JSON content

These are invoked automatically by the resume tailoring workflows.

### Prerequisites

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Troubleshooting

### "Cannot connect to browser"
- Ensure Chrome is running with the debug script
- Check that port 9222 is not blocked
- Verify no other Chrome instance is using that port

### "Selectors not found"
- The target website's UI may have changed
- The agent prompts include fallback strategies for handling UI changes

## Security Notes

- The debug port (9222) is only accessible locally
- Don't expose this port to your network
- Close the debug Chrome when not automating
- The dedicated profile keeps automation separate from your main Chrome profile
