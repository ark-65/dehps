from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping


RESEARCH_EXECUTION_MODE = "research"


def _stable_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ResearchTrainingFingerprint:
    history_max_issue: str
    history_fingerprint: str
    training_mode: str
    suite_version: str
    model_version: str
    feature_version: str
    candidate_algorithm_version: str
    config: Mapping[str, Any]
    code_commit: str
    seed: int

    @property
    def config_hash(self) -> str:
        return _stable_hash(dict(self.config))

    @property
    def payload(self) -> dict[str, Any]:
        return {
            "history_max_issue": self.history_max_issue,
            "history_fingerprint": self.history_fingerprint,
            "training_mode": self.training_mode,
            "suite_version": self.suite_version,
            "model_version": self.model_version,
            "feature_version": self.feature_version,
            "candidate_algorithm_version": self.candidate_algorithm_version,
            "config_hash": self.config_hash,
            "code_commit": self.code_commit,
            "seed": self.seed,
        }

    @property
    def value(self) -> str:
        return _stable_hash(self.payload)

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.payload,
            "training_fingerprint": self.value,
            "config": dict(self.config),
        }


def completed_manifest_matches(
    manifest: Any,
    *,
    lane_key: str,
    training_fingerprint: str,
) -> bool:
    return bool(
        isinstance(manifest, dict)
        and manifest.get("status") == "completed"
        and manifest.get("lane_key") == lane_key
        and manifest.get("training_fingerprint") == training_fingerprint
    )
