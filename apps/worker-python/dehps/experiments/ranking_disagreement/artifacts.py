from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from dehps.experiments.ranking_disagreement.models import (
    FROZEN_HYPOTHESIS_KEY,
    FROZEN_PLAN_FINGERPRINT,
    FROZEN_PLAN_KEY,
    FROZEN_PROPOSAL_FINGERPRINT,
    RANKING_DISAGREEMENT_SCHEMA_VERSION,
    stable_hash,
    stable_json,
    utc_now_iso,
)


class ArtifactWriter:
    def __init__(
        self,
        *,
        base_directory: Path,
        plan_key: str = FROZEN_PLAN_KEY,
        plan_fingerprint: str = FROZEN_PLAN_FINGERPRINT,
        proposal_fingerprint: str = FROZEN_PROPOSAL_FINGERPRINT,
        hypothesis_key: str = FROZEN_HYPOTHESIS_KEY,
        experiment_key: str = "ranking_disagreement_round24_isolated",
        history_fingerprint: str,
        legal_universe_fingerprint: str,
        code_commit: str | None = None,
    ) -> None:
        self.base_directory = base_directory
        self.base_directory.mkdir(parents=True, exist_ok=True)
        self.common = {
            "schema_version": RANKING_DISAGREEMENT_SCHEMA_VERSION,
            "plan_key": plan_key,
            "plan_fingerprint": plan_fingerprint,
            "proposal_fingerprint": proposal_fingerprint,
            "hypothesis_key": hypothesis_key,
            "experiment_key": experiment_key,
            "history_fingerprint": history_fingerprint,
            "legal_universe_fingerprint": legal_universe_fingerprint,
            "code_commit": code_commit or _git_commit(),
        }
        self._artifacts: list[dict[str, str]] = []

    @property
    def artifact_paths(self) -> list[str]:
        return [item["path"] for item in self._artifacts]

    def write_json(self, filename: str, payload: dict[str, Any]) -> dict[str, Any]:
        path = self.base_directory / filename
        envelope = self._envelope(payload)
        path.write_text(stable_json(envelope) + "\n", encoding="utf-8")
        self._record(path)
        return envelope

    def write_jsonl(self, filename: str, rows: list[dict[str, Any]]) -> Path:
        path = self.base_directory / filename
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(stable_json(self._envelope(row)) + "\n")
        self._record(path)
        return path

    def write_summary(self, filename: str, payload: dict[str, Any]) -> Path:
        path = self.base_directory / filename
        body = [
            "# Round 24 Ranking Disagreement Isolated Execution",
            "",
            f"- plan_key: `{self.common['plan_key']}`",
            f"- plan_fingerprint: `{self.common['plan_fingerprint']}`",
            f"- hypothesis_key: `{self.common['hypothesis_key']}`",
            f"- history_fingerprint: `{self.common['history_fingerprint']}`",
            f"- legal_universe_fingerprint: `{self.common['legal_universe_fingerprint']}`",
            f"- code_commit: `{self.common['code_commit']}`",
            "",
            "## Summary",
            "",
            "```json",
            json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2),
            "```",
        ]
        text_without_hash = "\n".join(body) + "\n"
        content_hash = hashlib.sha256(text_without_hash.encode("utf-8")).hexdigest()
        path.write_text(text_without_hash + f"\ncontent_hash: `{content_hash}`\n", encoding="utf-8")
        self._record(path)
        return path

    def write_manifest(self) -> dict[str, Any]:
        payload = {
            **self.common,
            "generated_at": utc_now_iso(),
            "artifacts": list(self._artifacts),
            "artifact_count": len(self._artifacts),
        }
        payload["content_hash"] = stable_hash(payload)
        path = self.base_directory / "manifest.json"
        path.write_text(stable_json(payload) + "\n", encoding="utf-8")
        return payload

    def _envelope(self, payload: dict[str, Any]) -> dict[str, Any]:
        envelope = {
            **self.common,
            "generated_at": utc_now_iso(),
            "payload": payload,
        }
        envelope["content_hash"] = stable_hash(envelope)
        return envelope

    def _record(self, path: Path) -> None:
        self._artifacts.append({"path": path.as_posix(), "content_hash": _file_hash(path)})


def validate_manifest(manifest_path: Path) -> dict[str, Any]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("manifest artifacts must be a list")
    missing: list[str] = []
    mismatched: list[str] = []
    for item in artifacts:
        path = Path(str(item.get("path", "")))
        if not path.exists():
            missing.append(path.as_posix())
            continue
        if _file_hash(path) != item.get("content_hash"):
            mismatched.append(path.as_posix())
    if missing or mismatched:
        raise ValueError(f"artifact validation failed; missing={missing}, mismatched={mismatched}")
    return {"valid": True, "artifact_count": len(artifacts), "manifest": payload}


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[5],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"
