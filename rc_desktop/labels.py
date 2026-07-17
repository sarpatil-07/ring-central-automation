"""Load editable UI label map from labels.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from rc_desktop import config


def load_labels(path: Path | None = None) -> dict[str, Any]:
    file_path = path or config.LABELS_FILE
    if not file_path.exists():
        raise FileNotFoundError(f"Missing labels file: {file_path}")
    data = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    if not data.get("app_process"):
        data["app_process"] = config.RC_APP_PROCESS
    return data


def app_process(labels: dict[str, Any] | None = None) -> str:
    data = labels or load_labels()
    return str(data.get("app_process") or config.RC_APP_PROCESS)
