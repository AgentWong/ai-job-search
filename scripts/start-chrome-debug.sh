#!/bin/bash
# Start Chrome with remote debugging port for MCP connection
# Uses a dedicated user data directory to preserve LinkedIn session

CHROME_USER_DATA="$HOME/.chrome-linkedin-automation"
DEBUG_PORT=9222

# Detect Chrome path for macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    CHROME="/usr/bin/google-chrome"
else
    echo "Unsupported OS: $OSTYPE"
    exit 1
fi

# Check if Chrome exists
if [ ! -f "$CHROME" ]; then
    echo "Error: Chrome not found at $CHROME"
    echo "Please update the CHROME variable in this script with the correct path."
    exit 1
fi

echo "========================================="
echo "Chrome Debug Mode for LinkedIn Automation"
echo "========================================="
echo ""
echo "Starting Chrome with remote debugging on port $DEBUG_PORT"
echo "User data directory: $CHROME_USER_DATA"
echo ""
echo "IMPORTANT: Log into LinkedIn in this browser window."
echo "Your session will persist across restarts."
echo ""
echo "To stop: Close the Chrome window or press Ctrl+C"
echo "========================================="

# Start Chrome with debugging enabled
"$CHROME" \
    --remote-debugging-port=$DEBUG_PORT \
    --remote-allow-origins="*" \
    --user-data-dir="$CHROME_USER_DATA" \
    "$@"
