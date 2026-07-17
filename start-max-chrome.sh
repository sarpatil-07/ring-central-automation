#!/bin/bash
# MAX-only Chrome — separate from your normal work browser.
# Your daily Chrome (Dock) stays open; this is a second window for NICE/MAX only.
#
# Morning: bash start-max-chrome.sh → OTP login here → python run.py schedule

set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
[[ -f "$DIR/.env" ]] && set -a && source "$DIR/.env" && set +a

CHROME="${CHROME_APP:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
PROFILE_DIR="${CHROME_MAX_PROFILE_DIR:-$DIR/chrome-max-profile}"
PORT="${CHROME_DEBUG_PORT:-9222}"

mkdir -p "$PROFILE_DIR"

if curl -sf "http://127.0.0.1:${PORT}/json/version" >/dev/null 2>&1; then
  echo "MAX Chrome already running (port ${PORT})."
  echo "Complete OTP in that window if needed, then: python run.py morning"
  exit 0
fi

echo "Starting MAX-only Chrome (separate from your normal work browser)"
echo "  Profile: $PROFILE_DIR"
echo "  Port:    $PORT"
echo ""
echo "  • Keep using normal Chrome for daily work — no need to quit it"
echo "  • In THIS window: OTP login → myprofile"
echo "  • Then: python run.py schedule"
echo ""

exec "$CHROME" \
  --remote-debugging-port="$PORT" \
  --user-data-dir="$PROFILE_DIR" \
  --no-first-run \
  --no-default-browser-check
