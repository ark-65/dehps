from __future__ import annotations

import json
import subprocess
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .digest import preregistration_digest
from .enums import PreregistrationStatus
from .validation import InformationTheoryValidationError, validate_preregistration


CANONICAL_PREREGISTRATION_RELATIVE_PATH = Path(
    "configs/research-os/m4-information-theory-preregistration-v1.0.3.json"
)


class PhaseGateError(RuntimeError):
    def __init__(self, message: str) -> None:
        self.code = "phase_gate_not_satisfied"
        super().__init__(f"{self.code}: {message}")


@dataclass(frozen=True)
class FrozenPreregistration:
    payload: dict[str, Any]
    output_path: Path

    @property
    def digest(self) -> str:
        return str(self.payload["artifact_digest"])


def load_preregistration(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise InformationTheoryValidationError(
            "preregistration_root_invalid",
            "preregistration root must be an object",
        )
    return payload


def _git_value(repo_root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _require_clean(repo_root: Path) -> None:
    if _git_value(repo_root, "status", "--porcelain"):
        raise InformationTheoryValidationError(
            "dirty_worktree",
            "preregistration freeze requires a clean working tree",
        )


def freeze_preregistration(
    payload: Mapping[str, Any],
    *,
    output_dir: Path,
    repo_root: Path,
) -> FrozenPreregistration:
    source = deepcopy(dict(payload))
    status = PreregistrationStatus(str(source.get("status")))
    if status not in {
        PreregistrationStatus.DRAFT,
        PreregistrationStatus.VALIDATED,
        PreregistrationStatus.FROZEN,
    }:
        raise InformationTheoryValidationError(
            "preregistration_not_freezable",
            f"cannot freeze {status.value}",
        )
    _require_clean(repo_root)
    if status is PreregistrationStatus.FROZEN:
        validate_preregistration(source)
        frozen = source
    else:
        validate_preregistration(source)
        frozen = deepcopy(source)
        frozen["status"] = PreregistrationStatus.FROZEN.value
        frozen["working_tree_clean"] = True
        frozen["code_commit"] = _git_value(repo_root, "rev-parse", "HEAD")
        frozen["artifact_digest"] = preregistration_digest(frozen)
        validate_preregistration(frozen)

    digest = str(frozen["artifact_digest"])
    artifact_dir = output_dir / digest
    artifact_path = artifact_dir / "preregistration.json"
    if artifact_path.exists():
        existing = load_preregistration(artifact_path)
        if existing != frozen:
            raise InformationTheoryValidationError(
                "frozen_preregistration_modified",
                "digest-addressed artifact already exists with different content",
            )
    else:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(
            json.dumps(frozen, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return FrozenPreregistration(payload=frozen, output_path=artifact_path)


def show_preregistration(
    *,
    digest: str,
    search_paths: tuple[Path, ...],
) -> dict[str, Any]:
    for base in search_paths:
        candidates = (
            base / digest / "preregistration.json",
            base,
        )
        for candidate in candidates:
            if not candidate.is_file():
                continue
            payload = load_preregistration(candidate)
            result = validate_preregistration(payload)
            if result["digest"] == digest:
                return payload
    raise FileNotFoundError(f"preregistration digest not found: {digest}")


def require_formal_run_gate(*, p2_status: str, p1_status: str) -> None:
    if p1_status != "FROZEN" or p2_status != "PASSED":
        raise PhaseGateError(
            "formal information-theory run requires FROZEN P1 and PASSED P2"
        )
