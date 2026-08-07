from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest
from dehps.research_os.information_theory.measurement_system_v2.compatibility import (
    P261_TASK_DIGEST,
    P263_COMPLETION_ARTIFACT_DIGEST,
    P263_EXECUTION_ARTIFACT_DIGEST,
    P263_EXECUTION_ID,
    P263_POLICY_DIGEST,
    P263_TASK_DIGEST,
)

from .contracts import MeasurementContractV2, MeasurementContractV2Error
from .gate import compile_hierarchical_gate

DESIGN_REPLAY_COMPLETION_FACT = (
    "m4-measurement-contract-v2-design-replay:VERIFIED"
)
_P261_FROZEN_REPLAY_EXECUTION_ID = (
    "cd64aacc48c5e1dac4f84d7f644e92384b50f37299b1643631b7ee872ab452b3"
)
P261_RAW_REPLAY_FACT = "m4-p2-6-1-raw-execution-replay:VERIFIED"
P27_GATE_REPLAY_FACT = "m4-p2-7-measurement-gate-replay:VERIFIED"
GATE_REPLAY_FIXTURE_PATH = Path(
    "configs/research-os/m4-measurement-contract-v2-replay-fixture-v1.json"
)
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class GateReplayFixture:
    payload: Mapping[str, Any]
    artifact_digest: str


@dataclass(frozen=True)
class DesignReplayArtifacts:
    measurement_contract_replay: Mapping[str, Any]
    gate_compiler_replay: Mapping[str, Any]

    @property
    def artifacts(self) -> tuple[Mapping[str, Any], ...]:
        return (self.measurement_contract_replay, self.gate_compiler_replay)


def load_gate_replay_fixture(path: Path) -> GateReplayFixture:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MeasurementContractV2Error(
            "measurement_v2_replay_fixture_invalid",
            str(exc),
        ) from exc
    if not isinstance(payload, dict):
        raise MeasurementContractV2Error(
            "measurement_v2_replay_fixture_invalid",
            "fixture root must be an object",
        )
    if (
        payload.get("schema_version")
        != "dehps-m4-measurement-contract-v2-replay-fixture.v1"
        or payload.get("artifact_type")
        != "measurement_contract_v2_gate_replay_fixture"
        or payload.get("status") != "FROZEN"
    ):
        raise MeasurementContractV2Error(
            "measurement_v2_replay_fixture_invalid",
            "fixture identity changed",
        )
    digest = str(payload.get("artifact_digest") or "")
    if not _DIGEST.fullmatch(digest) or config_digest(payload) != digest:
        raise MeasurementContractV2Error(
            "measurement_v2_replay_fixture_invalid",
            "fixture digest changed",
        )
    if not isinstance(payload.get("branch_reports"), list):
        raise MeasurementContractV2Error(
            "measurement_v2_replay_fixture_invalid",
            "fixture branch reports are missing",
        )
    return GateReplayFixture(payload=payload, artifact_digest=digest)


def build_design_replay_artifacts(
    contract: MeasurementContractV2,
    *,
    fixture: GateReplayFixture,
    design_execution: Mapping[str, Any],
    design_child_digests: Sequence[str],
    registration_payloads: Sequence[Mapping[str, Any]],
) -> DesignReplayArtifacts:
    if fixture.payload.get("measurement_contract_v2_digest") != contract.artifact_digest:
        raise MeasurementContractV2Error(
            "measurement_v2_replay_fixture_invalid",
            "fixture uses a different contract",
        )
    required_design_fields = (
        "execution_id",
        "artifact_digest",
        "measurement_contract_v2_digest",
        "estimand_contract_digest",
        "mechanism_role_contract_digest",
        "gate_compiler_contract_digest",
        "completion_artifact_digest",
    )
    if any(not design_execution.get(field) for field in required_design_fields):
        raise MeasurementContractV2Error(
            "measurement_v2_design_replay_failed",
            "design execution identity is incomplete",
        )
    if design_execution["measurement_contract_v2_digest"] != contract.artifact_digest:
        raise MeasurementContractV2Error(
            "measurement_v2_design_replay_failed",
            "design execution contract digest changed",
        )
    expected_children = [
        str(design_execution["estimand_contract_digest"]),
        str(design_execution["mechanism_role_contract_digest"]),
        str(design_execution["gate_compiler_contract_digest"]),
        str(design_execution["completion_artifact_digest"]),
    ]
    if sorted(design_child_digests) != sorted(expected_children):
        raise MeasurementContractV2Error(
            "measurement_v2_design_replay_failed",
            "registered design child set changed",
        )
    registration_identity = sorted(
        (
            str(item.get("artifact_digest") or ""),
            str(item.get("artifact_type") or ""),
            str(item.get("artifact_path") or ""),
            str(item.get("execution_id") or ""),
        )
        for item in registration_payloads
    )
    registration_set_digest = canonical_digest(
        registration_identity,
        domain="dehps.m4.measurement-v2.design-registry-set.v1",
    )

    gate_output = compile_hierarchical_gate(
        contract,
        branch_reports=fixture.payload["branch_reports"],
    )
    if (
        gate_output["artifact_digest"]
        != fixture.payload.get("expected_output_digest")
        or gate_output["global_coverage"]
        != fixture.payload.get("expected_global_coverage")
        or gate_output["global_evidence"]
        != fixture.payload.get("expected_global_evidence")
    ):
        raise MeasurementContractV2Error(
            "measurement_v2_gate_replay_failed",
            "frozen Gate Compiler fixture changed",
        )

    measurement_replay = _artifact(
        schema_version="dehps-m4-measurement-contract-v2-replay-artifact.v1",
        artifact_type="MeasurementContractV2ReplayArtifact",
        body={
            "status": "REPLAY_VERIFIED",
            "completion_fact": DESIGN_REPLAY_COMPLETION_FACT,
            "measurement_contract_v2_digest": contract.artifact_digest,
            "design_execution_id": design_execution["execution_id"],
            "design_execution_artifact_digest": design_execution[
                "artifact_digest"
            ],
            "estimand_contract_digest": design_execution[
                "estimand_contract_digest"
            ],
            "mechanism_role_contract_digest": design_execution[
                "mechanism_role_contract_digest"
            ],
            "gate_compiler_contract_digest": design_execution[
                "gate_compiler_contract_digest"
            ],
            "completion_artifact_digest": design_execution[
                "completion_artifact_digest"
            ],
            "registration_set_digest": registration_set_digest,
            "same_execution_identity": True,
            "same_registered_content": True,
            "same_contract_content": True,
            "formal_branch_runs_executed": 0,
            "historical_outcomes_read": False,
            "p2_6_1_partial_statistical_results_read": False,
            "evidence_created": False,
            "evidence_progress_increment": 0,
            "production_action": "none",
        },
        parent_digests=(
            contract.artifact_digest,
            str(design_execution["artifact_digest"]),
            *expected_children,
        ),
        domain="dehps.m4.measurement-v2.design-replay-artifact.v1",
    )
    gate_replay = _artifact(
        schema_version="dehps-m4-gate-compiler-replay-artifact.v1",
        artifact_type="GateCompilerReplayArtifact",
        body={
            "status": "REPLAY_VERIFIED",
            "measurement_contract_v2_digest": contract.artifact_digest,
            "gate_compiler_contract_digest": design_execution[
                "gate_compiler_contract_digest"
            ],
            "fixture_digest": fixture.artifact_digest,
            "fixture_output_digest": gate_output["artifact_digest"],
            "global_coverage": gate_output["global_coverage"],
            "global_evidence": gate_output["global_evidence"],
            "same_fixture_input": True,
            "same_fixture_output": True,
            "promotion_gate_opened": False,
            "production_action": "none",
        },
        parent_digests=(
            contract.artifact_digest,
            str(design_execution["gate_compiler_contract_digest"]),
            fixture.artifact_digest,
            gate_output["artifact_digest"],
        ),
        domain="dehps.m4.measurement-v2.gate-compiler-replay.v1",
    )
    return DesignReplayArtifacts(
        measurement_contract_replay=measurement_replay,
        gate_compiler_replay=gate_replay,
    )


def build_p261_raw_replay_artifact(
    *,
    execution: Mapping[str, Any],
    completion_event: Mapping[str, Any],
    registrations: Sequence[Mapping[str, Any]],
    expected_task_key: str,
    expected_task_digest: str,
    expected_execution_id: str,
    expected_manifest_digest: str,
) -> dict[str, Any]:
    frozen_p261 = {
        "task_key": expected_task_key,
        "task_digest": expected_task_digest,
        "execution_id": expected_execution_id,
        "measurement_validation_manifest_digest": expected_manifest_digest,
    }
    if (
        expected_task_digest != P261_TASK_DIGEST
        or expected_execution_id != _P261_FROZEN_REPLAY_EXECUTION_ID
        or expected_task_key != execution.get("task_key")
        or not all(isinstance(value, str) and value for value in frozen_p261.values())
    ):
        raise MeasurementContractV2Error(
            "p261_raw_replay_failed",
            "frozen P2.6.1 source identity changed",
        )
    # P2.6.1 is an immutable incomplete baseline.  The canonical completed
    # source is its accepted P2.6.3 superseding execution.  The parent loader
    # has already verified the current task/event/registry content; this exact
    # fixture binding prevents an arbitrary execution from taking its place.
    expected_superseding = {
        "task_key": expected_task_key,
        "task_digest": P263_TASK_DIGEST,
        "execution_id": P263_EXECUTION_ID,
        "artifact_digest": P263_EXECUTION_ARTIFACT_DIGEST,
        "completion_artifact_digest": P263_COMPLETION_ARTIFACT_DIGEST,
        "measurement_validation_manifest_digest": expected_manifest_digest,
        "measurement_update_policy_digest": P263_POLICY_DIGEST,
        "status": "COMPLETE",
    }
    if any(execution.get(key) != value for key, value in expected_superseding.items()):
        raise MeasurementContractV2Error(
            "p261_raw_replay_failed",
            "P2.6.3 superseding source identity changed",
        )
    completion_digest = str(execution.get("completion_artifact_digest") or "")
    completion_registrations = [
        item
        for item in registrations
        if item.get("artifact_digest") == completion_digest
        and item.get("artifact_type") == "measurement_validation_completion"
        and item.get("execution_id") == P263_EXECUTION_ID
    ]
    if len(completion_registrations) != 1:
        raise MeasurementContractV2Error(
            "p261_raw_replay_failed",
            "P2.6.1 immutable completion artifact is missing",
        )
    event_digest = str(completion_event.get("event_digest") or "")
    if (
        completion_event.get("event_type") != "completed"
        or completion_event.get("execution_id") != P263_EXECUTION_ID
        or not _DIGEST.fullmatch(event_digest)
    ):
        raise MeasurementContractV2Error(
            "p261_raw_replay_failed",
            "P2.6.1 completed event identity changed",
        )
    return {
        "schema_version": "dehps-m4-p2-6-1-raw-execution-replay.v1",
        "status": "REPLAY_VERIFIED",
        "task_key": expected_task_key,
        "task_digest": P263_TASK_DIGEST,
        "execution_id": P263_EXECUTION_ID,
        "execution_artifact_digest": execution["artifact_digest"],
        "measurement_validation_manifest_digest": expected_manifest_digest,
        "completion_artifact_digest": completion_digest,
        "completion_event_digest": event_digest,
        "registered_artifact_count": len(registrations),
        "same_execution_identity": True,
        "same_artifact_identity": True,
        "manual_input_assembly": False,
    }


def build_p27_gate_replay_artifact(
    *,
    execution: Mapping[str, Any],
    replay: Mapping[str, Any],
    parent_p261_execution_id: str,
) -> dict[str, Any]:
    capability = replay.get("capability_replay")
    if (
        replay.get("status") != "REPLAY_VERIFIED"
        or not isinstance(capability, Mapping)
        or capability.get("status") != "REPLAY_VERIFIED"
        or capability.get("automatic_gate_digest")
        != execution.get("automatic_gate_digest")
        or capability.get("decision") != execution.get("decision")
        or capability.get("decision_fact") != execution.get("decision_fact")
    ):
        raise MeasurementContractV2Error(
            "p27_gate_replay_failed",
            "P2.7 replay or Gate identity changed",
        )
    if (
        parent_p261_execution_id != _P261_FROZEN_REPLAY_EXECUTION_ID
        or execution.get("p26_execution_artifact_digest")
        != P263_EXECUTION_ARTIFACT_DIGEST
    ):
        raise MeasurementContractV2Error(
            "p27_gate_replay_failed",
            "P2.7 superseding parent identity changed",
        )
    return {
        "schema_version": "dehps-m4-p2-7-gate-replay.v1",
        "status": "REPLAY_VERIFIED",
        "task_key": execution["task_key"],
        "task_digest": execution["task_digest"],
        "execution_id": execution["execution_id"],
        "execution_artifact_digest": execution["artifact_digest"],
        "parent_p2_6_1_execution_id": P263_EXECUTION_ID,
        "parent_p2_6_1_execution_artifact_digest": execution[
            "p26_execution_artifact_digest"
        ],
        "automatic_gate_digest": execution["automatic_gate_digest"],
        "decision": execution["decision"],
        "decision_fact": execution["decision_fact"],
        "same_execution_identity": True,
        "same_artifact_identity": True,
        "manual_input_assembly": False,
    }


def _artifact(
    *,
    schema_version: str,
    artifact_type: str,
    body: Mapping[str, Any],
    parent_digests: Sequence[str],
    domain: str,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": schema_version,
        "artifact_type": artifact_type,
        "artifact_digest": "",
        **dict(body),
        "parent_digests": list(parent_digests),
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(identity, domain=domain)
    return payload
