"""Small OS helpers for Mac vs Linux."""

from __future__ import annotations

import shutil
import subprocess
import sys
import webbrowser


def is_mac() -> bool:
    return sys.platform == "darwin"


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def open_url(url: str) -> None:
    if is_mac() and shutil.which("open"):
        subprocess.run(["open", url], check=False)
        return
    if is_linux() and shutil.which("xdg-open"):
        subprocess.run(["xdg-open", url], check=False)
        return
    webbrowser.open(url)
