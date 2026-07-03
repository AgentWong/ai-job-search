# LinkedIn Automation Scripts

This directory contains helper scripts for LinkedIn job search automation using the chrome-devtools MCP server.

> **Note:** The LinkedIn browser workflow this guide was written for has been retired and replaced by the script-driven `/linkedin-api-search` (public guest API — no browser, no login). The Chrome remote-debugging setup below is still used by `/hiringcafe-job-search`, the only remaining browser-driven workflow.

## Quick Start

### Step 1: Start Chrome with Debugging Enabled

Run the startup script:
```bash
./scripts/start-chrome-debug.sh
```

This will:
- Launch Chrome with remote debugging on port 9222
- Use a dedicated profile at `~/.chrome-linkedin-automation`
- Preserve your LinkedIn login session across restarts

### Step 2: Log Into LinkedIn

In the Chrome window that just opened:
1. Navigate to https://www.linkedin.com
2. Log in with your credentials
3. Leave this window open

### Step 3: Run the LinkedIn Test

In VS Code with Claude Code or Claude Desktop:
1. Open the prompt: `.github/prompts/linkedin-test-exploration.prompt.md`
2. Run the prompt with Claude
3. Claude will use the chrome-devtools MCP to interact with your logged-in browser

## What the Test Does

The test prompt will:
1. Connect to your Chrome browser via the debugging port
2. Navigate to LinkedIn Jobs
3. Execute a test search for "devops engineer"
4. Try to apply various filters (date, experience level, remote, salary)
5. Extract job listings to understand the DOM structure
6. Take screenshots at each step
7. Document what works and what doesn't

## Expected Outcomes

After running the test, you should have:
- Screenshots of LinkedIn's interface at various stages
- Documentation of CSS selectors that work for extracting job data
- Understanding of URL parameters for filters
- Knowledge of timing requirements (how long to wait between actions)
- List of any limitations or challenges with automation

## Troubleshooting

### "Cannot connect to browser"
- Ensure Chrome is running with the debug script
- Check that port 9222 is not blocked
- Verify no other Chrome instance is using that port

### "Not logged into LinkedIn"
- Log in manually in the debug Chrome window
- The session will persist in the dedicated profile

### "Selectors not found"
- LinkedIn's UI may have changed
- The test prompt includes multiple fallback selectors
- Document which selectors work for future reference

## Next Steps

After successful testing:
1. Review the test results and screenshots
2. Build a production workflow under `.claude/commands/`
3. Add LinkedIn configuration to `config/config.yml`
4. Build job extraction and scoring logic

## Security Notes

- The debug port (9222) is only accessible locally
- Don't expose this port to your network
- Close the debug Chrome when not automating
- The dedicated profile keeps automation separate from your main Chrome profile
