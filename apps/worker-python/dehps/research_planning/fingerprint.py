from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


def normalized(value: Any) -> Any:
    if is_dataclass(value):
        return normalized(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {str(key): normalized(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [normalized(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        normalized(value),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )


def stable_fingerprint(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def plan_fingerprint_payload(plan_payload: dict[str, Any]) -> dict[str, Any]:
    payload = dict(plan_payload)
    payload["plan_fingerprint"] = ""
    return payload
