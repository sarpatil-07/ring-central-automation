#!/bin/bash
# Legacy debug mode only — not needed if BROWSER_MODE=launch (default).
echo "Default mode needs NO debug port."
echo "Just run:  python run.py morning"
echo ""
echo "Only use this if .env has BROWSER_MODE=debug"
exec bash "$(dirname "$0")/start-max-chrome.sh" 2>/dev/null || bash "$(dirname "$0")/install-work-chrome.command"
