#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

# shellcheck disable=SC1091
source packaging/pick_python.sh
PYTHON="$(pick_python)"

echo "Using: $("$PYTHON" --version)"

if [[ -d .venv ]]; then
  venv_py="$(
    .venv/bin/python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null \
      || echo unknown
  )"
  if [[ "$venv_py" != "3.11" && "$venv_py" != "3.12" && "$venv_py" != "3.13" ]]; then
    echo "Removing .venv (Python $venv_py not supported — need 3.11–3.13)."
    rm -rf .venv
  fi
fi

[[ -d .venv ]] || "$PYTHON" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
python -m playwright install chrome 2>/dev/null || python -m playwright install chromium
cp -n .env.example .env 2>/dev/null || cp -n rc_autologin/.env.example .env 2>/dev/null || true

echo ""
echo "RCAutoLogin setup complete."
echo ""
echo "  .venv/bin/python rc_autologin_run.py          # open GUI"
echo "  .venv/bin/python rc_autologin_run.py build-release   # shareable zip"
echo ""
