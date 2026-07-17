#!/usr/bin/env bash
# RCAutoLogin — first-time setup (Mac or Linux). Run once after unzipping / clone.
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

# shellcheck disable=SC1091
source "$ROOT/packaging/pick_python.sh"
PYTHON="$(pick_python)"
echo "Using: $("$PYTHON" --version)"

if [[ -d .venv ]]; then
  venv_py="$(
    .venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null \
      || echo unknown
  )"
  if [[ "$venv_py" != "3.12" && "$venv_py" != "3.13" ]]; then
    echo "Removing .venv (Python $venv_py not supported — need 3.12 or 3.13)."
    rm -rf .venv
  fi
fi

if [[ ! -d .venv ]]; then
  "$PYTHON" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
python -m playwright install chrome 2>/dev/null || python -m playwright install chromium

if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    cp .env.example .env
  elif [[ -f rc_autologin/.env.example ]]; then
    cp rc_autologin/.env.example .env
  fi
  echo "Created .env — edit work/lunch times before using."
fi

mkdir -p logs
echo ""
echo "RCAutoLogin setup complete."
echo ""
echo "Launch GUI:"
echo "  ./launch-gui.sh"
echo "  # or:  .venv/bin/python rc_autologin_run.py"
if [[ "$(uname -s)" == "Darwin" ]]; then
  echo "  # Mac also:  open 'Launch RCAutoLogin.command'"
  echo "  # or drag RCAutoLogin.app to Dock (if present)"
else
  DESKTOP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
  mkdir -p "$DESKTOP_DIR"
  if [[ -f packaging/RCAutoLogin.desktop ]]; then
    sed "s|@ROOT@|$ROOT|g" packaging/RCAutoLogin.desktop > "$DESKTOP_DIR/rcautologin.desktop"
    echo "  Menu entry: $DESKTOP_DIR/rcautologin.desktop"
  fi
fi
echo ""
echo "Requires: Python 3.12+, Google Chrome, desktop session."
echo ""
