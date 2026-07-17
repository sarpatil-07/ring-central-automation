#!/usr/bin/env python3
"""
Record UI selectors while YOU click in Chrome.

Setup:
  1. ./launch-chrome.sh          # opens Chrome with debug port + saved login profile
  2. Log in to CXone manually once in that Chrome window
  3. python record.py            # then click elements; each click is saved

Output: recorded-selectors.yaml (used by run.py instead of selectors.yaml)
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

import yaml
from playwright.sync_api import sync_playwright

import config

JS_GET_CLICKED = """
() => {
  function getXPath(el) {
    if (!el || el.nodeType !== 1) return '';
    if (el.id) return '//*[@id="' + el.id + '"]';
    const parts = [];
    while (el && el.nodeType === 1) {
      let index = 1;
      let sib = el.previousElementSibling;
      while (sib) {
        if (sib.nodeName === el.nodeName) index++;
        sib = sib.previousElementSibling;
      }
      parts.unshift(el.nodeName.toLowerCase() + '[' + index + ']');
      el = el.parentElement;
    }
    return '/' + parts.join('/');
  }
  return new Promise((resolve) => {
    const handler = (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      const t = ev.target;
      document.removeEventListener('click', handler, true);
      resolve({
        tag: t.tagName,
        id: t.id || '',
        className: (t.className && t.className.toString()) || '',
        title: t.getAttribute('title') || '',
        text: (t.innerText || t.textContent || '').trim().slice(0, 120),
        xpath: getXPath(t),
        css: t.id ? '#' + CSS.escape(t.id) : t.tagName.toLowerCase(),
      });
    };
    document.addEventListener('click', handler, true);
  });
}
"""

STEPS = [
    ("switch_application", "Click: Switch application (top-left menu)"),
    ("max_button", "Click: MAX under Omnichannel Routing"),
    ("station_id_option", "In MAX popup: click Station ID option (if shown)"),
    ("station_id_input", "In MAX popup: click the Station ID text field"),
    ("connect_button", "In MAX popup: click Connect"),
    ("status_available", "In MAX popup: click Available status"),
    ("status_unavailable", "In MAX popup: click Unavailable status"),
]


def main() -> int:
    print("Connecting to Chrome at", config.CDP_URL)
    print("If this fails, run: ./launch-chrome.sh\n")

    recorded: dict = {}
    if config.RECORDED_FILE.exists():
        recorded = yaml.safe_load(config.RECORDED_FILE.read_text()) or {}

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(config.CDP_URL)
        except Exception as exc:
            print("Could not connect:", exc)
            print("\nStart Chrome first:\n  ./launch-chrome.sh")
            return 1

        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.pages[0] if context.pages else context.new_page()

        def active_page():
            pages = context.pages
            return pages[-1] if pages else page

        print("Open myprofile / CXone in this Chrome window if needed.")
        print("When ready, press Enter here to start recording…")
        input()

        for step, prompt in STEPS:
            if step in recorded and recorded[step].get("xpath"):
                skip = input(f"{step} already recorded. Re-record? [y/N]: ").strip().lower()
                if skip != "y":
                    continue

            print(f"\n>>> {prompt}")
            print("    Click the element in Chrome now…")

            target = active_page()
            info = target.evaluate(JS_GET_CLICKED)
            if step == "max_button":
                target.wait_for_timeout(2500)
                target = active_page()
                print(f"    (MAX window: {target.url[:70]}…)")
            entry = {
                "xpath": info["xpath"],
                "css": info["css"] if info.get("id") else "",
                "text": info.get("text", "")[:80],
                "_meta": {
                    "tag": info.get("tag"),
                    "title": info.get("title"),
                    "class": info.get("className", "")[:120],
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                },
            }
            recorded[step] = entry
            config.RECORDED_FILE.write_text(
                yaml.safe_dump(recorded, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            print(f"    Saved xpath: {info['xpath'][:100]}")
            print(f"    text: {info.get('text', '')[:60]!r}")

        print("\nDone. Saved to recorded-selectors.yaml")
        print("Run automation: python run.py available")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
