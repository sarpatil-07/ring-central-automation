#!/usr/bin/env bash
# Pick a Python 3.11–3.13 interpreter (Playwright/greenlet do not support 3.14+ yet).
pick_python() {
  if [[ -n "${PYTHON:-}" ]]; then
    if ! command -v "$PYTHON" >/dev/null 2>&1; then
      echo "PYTHON=$PYTHON not found on PATH." >&2
      return 1
    fi
    if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] <= (3, 13) else 1)'; then
      echo "PYTHON=$PYTHON is not supported. Use Python 3.11, 3.12, or 3.13." >&2
      echo "  brew install python@3.13" >&2
      return 1
    fi
    echo "$PYTHON"
    return 0
  fi

  for cmd in python3.13 python3.12 python3.11; do
    if command -v "$cmd" >/dev/null 2>&1; then
      echo "$cmd"
      return 0
    fi
  done

  if command -v python3 >/dev/null 2>&1; then
    if python3 -c 'import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] <= (3, 13) else 1)'; then
      echo python3
      return 0
    fi
    ver="$(python3 --version 2>&1 | awk '{print $2}')"
    echo "Found $ver but RCAutoLogin needs Python 3.11–3.13 (Playwright/greenlet fail on 3.14+)." >&2
    echo "Install a supported version, then re-run setup:" >&2
    echo "  brew install python@3.13" >&2
    echo "  rm -rf .venv && PYTHON=python3.13 bash setup.sh" >&2
    return 1
  fi

  echo "Python 3.11+ not found. Install Python 3.13 and run setup again." >&2
  echo "  brew install python@3.13" >&2
  return 1
}
