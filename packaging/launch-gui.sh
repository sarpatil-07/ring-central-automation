#!/usr/bin/env bash
# Start RCAutoLogin GUI (Mac + Linux).
# Works from portable zip root or from packaging/ in a git clone.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$HERE/rc_autologin_run.py" ]]; then
  ROOT="$HERE"
elif [[ -f "$HERE/../rc_autologin_run.py" ]]; then
  ROOT="$(cd "$HERE/.." && pwd)"
else
  echo "Cannot find rc_autologin_run.py near $HERE" >&2
  exit 1
fi

cd "$ROOT"
PORT=8765
URL="http://127.0.0.1:${PORT}/"
PYTHON="${ROOT}/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "Run ./install.sh first (or: bash packaging/install.sh)." >&2
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

# Already running — just open the control panel.
if curl -sf "${URL}api/state" >/dev/null 2>&1 || curl -sf "${URL}api/status" >/dev/null 2>&1; then
  open_url "$URL"
  exit 0
fi

exec "$PYTHON" rc_autologin_run.py
