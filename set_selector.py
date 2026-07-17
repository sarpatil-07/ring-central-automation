#!/usr/bin/env python3
"""Paste a single XPath into selectors without recording clicks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

import config

VALID_STEPS = [
    "switch_application",
    "max_button",
    "station_id_option",
    "station_id_input",
    "connect_button",
    "status_available",
    "status_unavailable",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Set one selector by hand")
    parser.add_argument("step", choices=VALID_STEPS)
    parser.add_argument("xpath", help="XPath from Chrome DevTools (Copy → Copy XPath)")
    parser.add_argument("--text", default="", help="Optional visible text fallback")
    args = parser.parse_args()

    out = config.RECORDED_FILE if config.RECORDED_FILE.exists() else config.SELECTORS_FILE
    data = yaml.safe_load(out.read_text(encoding="utf-8")) if out.exists() else {}

    data[args.step] = {
        "xpath": args.xpath,
        "css": "",
        "text": args.text,
    }
    out.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"Updated {out.name} → {args.step}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
