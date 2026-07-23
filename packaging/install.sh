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

# Playwright browsers:
# - Mac: install Chrome channel for Playwright
# - Linux: use system Google Chrome / Chromium if present; otherwise install Playwright Chromium.
#   "chrome is already installed" is normal on Fedora/Ubuntu and is NOT a failure.
_install_playwright_browsers() {
  local os
  os="$(uname -s)"
  if [[ "$os" == "Darwin" ]]; then
    if python -m playwright install chrome; then
      return 0
    fi
    echo "Note: Playwright Chrome install skipped/failed — trying Chromium…"
    python -m playwright install chromium || true
    return 0
  fi

  # Linux (Fedora, Ubuntu, etc.)
  if command -v google-chrome >/dev/null 2>&1 \
    || command -v google-chrome-stable >/dev/null 2>&1 \
    || command -v chromium >/dev/null 2>&1 \
    || command -v chromium-browser >/dev/null 2>&1; then
    echo "System Chrome/Chromium found — Playwright will use it (skipping playwright install chrome)."
  else
    echo "No system Chrome found — installing Playwright Chromium…"
  fi
  # Always ensure Playwright has a browser binary for its driver (hermetic Chromium).
  # Ubuntu20.04 fallback warnings on Fedora are harmless.
  if ! python -m playwright install chromium; then
    echo "WARNING: playwright install chromium failed." >&2
    echo "  If Login fails later, try:  .venv/bin/python -m playwright install chromium" >&2
  fi
  # Optional OS libs (may need sudo; ignore failure on locked-down machines).
  python -m playwright install-deps chromium >/dev/null 2>&1 || true
}

_install_playwright_browsers

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
echo "Requires: Python 3.12+, Google Chrome (or Chromium), desktop session."
echo "Fedora note: Playwright may print ubuntu20.04 fallback warnings — that is OK."
echo ""
