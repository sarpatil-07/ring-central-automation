#!/usr/bin/env bash
# Start RCAutoLogin GUI. Uses the same fast path as Launch RCAutoLogin.command.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
PORT=8765
URL="http://127.0.0.1:${PORT}/"
PYTHON="${ROOT}/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "Run ./install.sh first." >&2
  exit 1
fi

open_url() {
  if command -v open >/dev/null 2>&1; then
    open "$1"
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$1"
  else
    echo "Open in your browser: $1"
  fi
}

# Already running — just open the control panel (instant).
if curl -sf "${URL}api/state" >/dev/null 2>&1 || curl -sf "${URL}api/status" >/dev/null 2>&1; then
  open_url "$URL"
  exit 0
fi

# Fast path: same as dev — no nohup, no curl polling loop.
exec "$PYTHON" rc_autologin_run.py
