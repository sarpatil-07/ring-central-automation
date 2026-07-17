#!/usr/bin/env bash
# Build shareable RCAutoLogin zip (excludes .env, chrome profile, logs, .venv)
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -x .venv/bin/python ]]; then
  echo "Run bash setup.sh first." >&2
  exit 1
fi

echo "Building RCAutoLogin portable zip..."
echo ""
.venv/bin/python rc_autologin_run.py build-release
echo ""
echo "Done. Share only the .zip file from dist/ — not your whole project folder."
