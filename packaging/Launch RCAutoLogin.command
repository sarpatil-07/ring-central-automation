#!/bin/bash
# Mac double-click launcher for RCAutoLogin GUI.
# Place at portable zip root (or run from packaging/ — resolves project root).
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
if [[ ! -x .venv/bin/python ]]; then
  echo "Run ./install.sh first." >&2
  exit 1
fi
exec .venv/bin/python rc_autologin_run.py
