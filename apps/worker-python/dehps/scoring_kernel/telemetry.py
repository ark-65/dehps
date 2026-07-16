from __future__ import annotations

import json
import os
from pathlib import Path

from dehps.config import ROOT_DIR


DEFAULT_TELEMETRY_PATH = ROOT_DIR / "runtime/logs/scoring-kernel.jsonl"


def record_kernel_telemetry(payload: dict[str, int | float | str]) -> None:
    configured = os.getenv("DEHPS_SCORING_TELEMETRY_PATH")
    if configured == "off":
        return
    path = Path(configured) if configured else DEFAULT_TELEMETRY_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
    try:
        os.write(descriptor, encoded)
    finally:
        os.close(descriptor)
