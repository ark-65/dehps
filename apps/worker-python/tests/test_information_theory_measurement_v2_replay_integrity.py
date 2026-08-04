from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path

import pytest
from dehps.research_os.information_theory.progress import load_m4_manifest
from dehps.research_os.supervisor import (
    M4_V2_DESIGN_TASK_KEY,
    M4MeasurementContractV2DesignCapability,
    MainlineSupervisorError,
    ResearchEvidenceSupervisor,
    _verify_v2_registered_artifacts,
)

CONTROL_PLANE_KEY = "m4-information-theory-mainline"


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_v2_replay_compares_registered_artifact_content(
    tmp_path: Path,
) -> None:
    first = {
        "artifact_type": "measurement_v2_estimand_contract",
        "artifact_digest": "1" * 64,
        "contract": {"branch": "MARGINAL_STATIC"},
    }
    second = {
        "artifact_type": "research_os_mainline_execution",
        "artifact_digest": "2" * 64,
        "status": "COMPLETE",
    }
    first_path = Path("runtime/first.json")
    second_path = Path("runtime/second.json")
    _write(tmp_path / first_path, first)
    _write(tmp_path / second_path, second)
    registrations = [
        {
            "artifact_digest": first["artifact_digest"],
            "artifact_type": first["artifact_type"],
            "artifact_path": str(first_path),
        },
        {
            "artifact_digest": second["artifact_digest"],
            "artifact_type": second["artifact_type"],
            "artifact_path": str(second_path),
        },
    ]

    _verify_v2_registered_artifacts(
        root_dir=tmp_path,
        registrations=registrations,
        expected_payloads=(first, second),
    )

    tampered = {
        **first,
        "contract": {"branch": "JOINT_RESIDUAL_INCREMENT"},
    }
    _write(tmp_path / first_path, tampered)
    with pytest.raises(
        MainlineSupervisorError,
        match="registered artifact content changed",
    ):
        _verify_v2_registered_artifacts(
            root_dir=tmp_path,
            registrations=registrations,
            expected_payloads=(first, second),
        )


class _ReplayRepository:
    def __init__(self, *, event: dict, registrations: list[dict]) -> None:
        self.event = event
        self.registrations = registrations

    def list_mainline_execution_events(
        self,
        *,
        control_plane_key: str,
        task_key: str | None = None,
        execution_id: str | None = None,
    ) -> tuple[dict, ...]:
        if task_key is not None and task_key != self.event["task_key"]:
            return ()
        if execution_id is not None and execution_id != self.event["execution_id"]:
            return ()
        return (self.event,)

    def list_mainline_artifacts(
        self,
        *,
        control_plane_key: str,
        execution_id: str,
    ) -> list[dict]:
        assert execution_id == self.event["execution_id"]
        return self.registrations


def test_supervisor_v2_replay_rejects_tampered_registered_child(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[3]
    source_contract = root / "configs/research-os/m4-measurement-contract-v2.json"
    source_manifest = (
        root / "configs/research-os/m4-information-theory-evidence-v1.json"
    )
    target_contract = tmp_path / "configs/research-os/m4-measurement-contract-v2.json"
    target_contract.parent.mkdir(parents=True)
    shutil.copy2(source_contract, target_contract)
    manifest = load_m4_manifest(source_manifest)
    task = next(
        item for item in manifest.tasks if item.task_key == M4_V2_DESIGN_TASK_KEY
    )
    execution_id = "5" * 64
    result = M4MeasurementContractV2DesignCapability(root_dir=tmp_path).execute(
        control_plane_key=CONTROL_PLANE_KEY,
        task=task,
        execution_id=execution_id,
        git_commit="6" * 40,
    )
    registrations = [asdict(item) for item in result.registrations]
    event = {
        "event_type": "completed",
        "task_key": task.task_key,
        "execution_id": execution_id,
        "payload": {
            "execution_artifact_path": str(
                result.execution_artifact_path.relative_to(tmp_path)
            ),
            "execution_artifact_digest": result.execution_artifact["artifact_digest"],
            "registered_artifact_count": len(registrations),
            "actual_fold_count": 0,
        },
    }
    repository = _ReplayRepository(
        event=event,
        registrations=registrations,
    )
    supervisor = ResearchEvidenceSupervisor(
        repository=repository,
        control_plane_key=CONTROL_PLANE_KEY,
        root_dir=tmp_path,
        git_commit="6" * 40,
        require_clean_tree=False,
    )
    assert supervisor.replay(task_key=task.task_key)["status"] == ("REPLAY_VERIFIED")

    child = next(
        item
        for item in registrations
        if item["artifact_type"] != "research_os_mainline_execution"
    )
    child_path = tmp_path / child["artifact_path"]
    tampered = json.loads(child_path.read_text(encoding="utf-8"))
    tampered["tampered_without_digest_change"] = True
    _write(child_path, tampered)
    with pytest.raises(
        MainlineSupervisorError,
        match="registered artifact content changed",
    ):
        supervisor.replay(task_key=task.task_key)
