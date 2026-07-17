#!/bin/bash
# Recommended launch — same as dev path (fastest).
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  echo "Run ./install.sh first." >&2
  exit 1
fi
exec .venv/bin/python rc_autologin_run.py
