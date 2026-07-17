#!/usr/bin/env bash
# RCAutoLogin GUI — RingCX web only
cd "$(dirname "$0")"
exec .venv/bin/python rc_autologin_run.py gui "$@"
