from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from dehps.contracts import canonical_digest
from dehps.research_os.information_theory.digest import config_digest
from dehps.research_os.models import ControlPlaneManifest, ResearchOSValidationError

COMPATIBILITY_REQUEST_PATH = Path(
    "configs/research-os/m4-p2-measurement-v2-compatibility-request-v1.json"
)
P261_FROZEN_FIXTURE_PATH = Path(
    "configs/research-os/fixtures/m4-p2.6.1/frozen/source-manifest-fixture-v1.json"
)
P263_SUPERSEDING_FIXTURE_PATH = Path(
    "configs/research-os/fixtures/m4-p2.6.3/superseding/source-manifest-fixture-v1.json"
)
COMPATIBILITY_REQUEST_DIGEST = (
    "42d9583d2b333e171b99dfde27732b687e2deec2359a423d20d5d295103d1cec"
)
P261_FROZEN_FIXTURE_DIGEST = (
    "f9716c799e1e55e58585c7e9acf0730f9d05111ab6e375cfb9bea85ecbdeacc5"
)
P263_SUPERSEDING_FIXTURE_DIGEST = (
    "53f9a4b7d92944dfd6a46d317b018bdc6b434fc69bb977d72ae6d1f177e0c73b"
)
P261_TASK_DIGEST = "80068e22f5e1c343fd86213faa0d9a411d71f92ad2750fed10449a10151de8fa"
P263_TASK_DIGEST = "85a08402a4a0c37f75ee1675f4970ef00a7a0b0992b4204251c0c2cc79324de4"
P263_POLICY_DIGEST = "ad58b9abcd90c5e7ee7b9892ac8c209b8033f7a50e603b58c043685b0c7d6f99"
COMPATIBILITY_COMPLETION_FACT = "m4-p2-6-3-compatibility:VERIFIED"

_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_FIXTURE_FIELDS = {
    "schema_version",
    "artifact_type",
    "artifact_digest",
    "manifest_digest",
    "fixture_key",
    "status",
    "phase",
    "source",
    "runtime_identity",
    "evidence_boundary",
    "result_blind",
    "governance",
}
_SOURCE_FIELDS = {
    "git_commit",
    "manifest_path",
    "manifest_content_sha256",
    "task_key",
    "task_digest",
    "requested_capability",
    "measurement_validation_manifest_digest",
    "measurement_update_policy_digest",
}
_RUNTIME_FIELDS = {
    "classification",
    "execution_ids",
    "execution_artifact_digest",
    "completion_artifact_digest",
    "formal_completion_present",
    "results_or_checkpoints_reusable_by_superseding_execution",
    "runtime_roots_deleted",
}
_RESULT_BLIND_FIELDS = {
    "score_read",
    "prediction_read",
    "ranking_read",
    "power_read",
    "false_positive_read",
    "bias_rmse_coverage_read",
    "mde_read",
}
_EXPECTED_PHASES = {
    "M4-P2.6.1": {
        "artifact_digest": P261_FROZEN_FIXTURE_DIGEST,
        "manifest_digest": (
            "b1f72ebe01daf38c39724f2b6b2beaa1e0be391974e708ba1be65e8cf12ae3be"
        ),
        "fixture_key": "M4-P2.6.1_FROZEN_INCOMPLETE_BASELINE",
        "status": "FROZEN_HISTORICAL_BASELINE",
        "git_commit": "5714688cf50545fd125f4dc8422ac7e5f0bfec1f",
        "content_sha256": (
            "47145fcc36b84a49c3494eedd67121328cce1bd33a14659fcac28b6dc3ddf557"
        ),
        "task_digest": P261_TASK_DIGEST,
        "capability": "m4_p2_6_1_false_positive_and_power",
        "policy_digest": None,
        "classification": "INCOMPLETE_HISTORICAL_RUNTIME_BASELINE",
        "execution_ids": [
            "8e1c601233833b60442b45ebaeeaea53679c34eef1d00de5480827f415d517fd",
            "cd64aacc48c5e1dac4f84d7f644e92384b50f37299b1643631b7ee872ab452b3",
        ],
        "execution_artifact_digest": None,
        "completion_artifact_digest": None,
        "formal_completion_present": False,
        "synthetic_measurement_execution": "INCOMPLETE",
        "change_classification": "HISTORICAL_FROZEN_BOUNDARY",
    },
    "M4-P2.6.3": {
        "artifact_digest": P263_SUPERSEDING_FIXTURE_DIGEST,
        "manifest_digest": (
            "39435df4057f0df747f2b56c48282d6fc4ad9a266fbb8f31262e3984ece712ba"
        ),
        "fixture_key": "M4-P2.6.3_SUPERSEDING_PERIODIC_REFIT_64",
        "status": "SUPERSEDING_IMPLEMENTATION_COMPLETE",
        "git_commit": "947c7b4d8c040fa0d7351a2bf6859c33fa428411",
        "content_sha256": (
            "840c91381be8eedb8e89e076da8c0bc6ed046a941b88dec13270015b86d7bfed"
        ),
        "task_digest": P263_TASK_DIGEST,
        "capability": "m4_p2_6_3_periodic_refit_false_positive_and_power",
        "policy_digest": P263_POLICY_DIGEST,
        "classification": "SUPERSEDING_COMPLETED_MEASUREMENT_IMPLEMENTATION",
        "execution_ids": [
            "7de420e96e495f357a75860249cf1529a0d14a8d272177cacb0eb6f04b556c0d"
        ],
        "execution_artifact_digest": (
            "948a44109cf31eb01ee4edad5363b4ecfc605bd9103813d32e021603268f76bc"
        ),
        "completion_artifact_digest": (
            "448444ad70ff1af46edae795dc516f13fede062cfec6879a2db27b639095c092"
        ),
        "formal_completion_present": True,
        "synthetic_measurement_execution": "COMPLETE",
        "change_classification": "MEASUREMENT_CONTRACT_EVOLUTION",
    },
}


class MeasurementCompatibilityError(RuntimeError):
    pass


@dataclass(frozen=True)
class MeasurementCompatibilityFixture:
    payload: Mapping[str, Any]
    artifact_digest: str
    phase: str


@dataclass(frozen=True)
class MeasurementCompatibilityRequest:
    payload: Mapping[str, Any]
    artifact_digest: str


def _mapping(value: object, *, field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise MeasurementCompatibilityError(f"compatibility_{field}_invalid")
    return dict(value)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MeasurementCompatibilityError(
            f"compatibility_artifact_invalid:{path}:{exc}"
        ) from exc
    if not isinstance(value, dict):
        raise MeasurementCompatibilityError(
            f"compatibility_artifact_invalid:{path}:root"
        )
    return value


def validate_measurement_compatibility_fixture(
    value: object,
    *,
    expected_phase: str,
) -> MeasurementCompatibilityFixture:
    payload = _mapping(value, field="fixture")
    expected = _EXPECTED_PHASES.get(expected_phase)
    if expected is None or set(payload) != _FIXTURE_FIELDS:
        raise MeasurementCompatibilityError("compatibility_fixture_shape_changed")
    source = _mapping(payload.get("source"), field="fixture_source")
    runtime = _mapping(payload.get("runtime_identity"), field="fixture_runtime")
    evidence = _mapping(payload.get("evidence_boundary"), field="fixture_evidence")
    blind = _mapping(payload.get("result_blind"), field="fixture_result_blind")
    governance = _mapping(payload.get("governance"), field="fixture_governance")
    artifact_digest = str(payload.get("artifact_digest") or "")
    if (
        payload.get("schema_version")
        != "dehps-m4-p2-measurement-supersession-fixture.v1"
        or payload.get("artifact_type") != "measurement_source_compatibility_fixture"
        or payload.get("phase") != expected_phase
        or artifact_digest != expected["artifact_digest"]
        or config_digest(payload) != artifact_digest
        or payload.get("manifest_digest") != expected["manifest_digest"]
        or payload.get("fixture_key") != expected["fixture_key"]
        or payload.get("status") != expected["status"]
        or set(source) != _SOURCE_FIELDS
        or source.get("git_commit") != expected["git_commit"]
        or source.get("manifest_path")
        != "configs/research-os/m4-information-theory-evidence-v1.json"
        or source.get("manifest_content_sha256") != expected["content_sha256"]
        or source.get("task_key") != "m4-p2-false-positive-and-power-runs"
        or source.get("task_digest") != expected["task_digest"]
        or source.get("requested_capability") != expected["capability"]
        or source.get("measurement_validation_manifest_digest")
        != "a4e46a434a4b2ef9fe56ed0390d58ca5a45bbad21685b81cb983f7261b3abf58"
        or source.get("measurement_update_policy_digest") != expected["policy_digest"]
        or set(runtime) != _RUNTIME_FIELDS
        or runtime.get("classification") != expected["classification"]
        or runtime.get("execution_ids") != expected["execution_ids"]
        or runtime.get("execution_artifact_digest")
        != expected["execution_artifact_digest"]
        or runtime.get("completion_artifact_digest")
        != expected["completion_artifact_digest"]
        or runtime.get("formal_completion_present")
        is not expected["formal_completion_present"]
        or runtime.get("results_or_checkpoints_reusable_by_superseding_execution")
        is not False
        or runtime.get("runtime_roots_deleted") is not False
        or evidence
        != {
            "synthetic_measurement_execution": expected[
                "synthetic_measurement_execution"
            ],
            "historical_evidence": "NOT_RUN",
            "prediction_promotion_eligible": False,
            "research_conclusion_created": False,
        }
        or set(blind) != _RESULT_BLIND_FIELDS
        or set(blind.values()) != {False}
        or governance
        != {
            "change_classification": expected["change_classification"],
            "immutable": True,
            "in_place_rewrite_allowed": False,
            "evidence_progress_increment": 0,
            "production_action": "none",
        }
    ):
        raise MeasurementCompatibilityError("compatibility_fixture_identity_changed")
    if _COMMIT.fullmatch(str(source["git_commit"])) is None or any(
        _DIGEST.fullmatch(str(value)) is None
        for value in (
            artifact_digest,
            payload["manifest_digest"],
            source["manifest_content_sha256"],
            source["task_digest"],
            source["measurement_validation_manifest_digest"],
            *runtime["execution_ids"],
        )
    ):
        raise MeasurementCompatibilityError("compatibility_fixture_digest_invalid")
    return MeasurementCompatibilityFixture(
        payload=payload,
        artifact_digest=artifact_digest,
        phase=expected_phase,
    )


def load_measurement_compatibility_fixture(
    path: Path,
    *,
    expected_phase: str,
) -> MeasurementCompatibilityFixture:
    return validate_measurement_compatibility_fixture(
        _load_json(path),
        expected_phase=expected_phase,
    )


def validate_measurement_compatibility_pair(
    p261: MeasurementCompatibilityFixture,
    p263: MeasurementCompatibilityFixture,
) -> None:
    old_source = p261.payload["source"]
    new_source = p263.payload["source"]
    if (
        p261.phase != "M4-P2.6.1"
        or p263.phase != "M4-P2.6.3"
        or p261.artifact_digest == p263.artifact_digest
        or p261.payload["manifest_digest"] == p263.payload["manifest_digest"]
        or old_source["task_digest"] == new_source["task_digest"]
        or old_source["task_key"] != new_source["task_key"]
        or p261.payload["runtime_identity"]["formal_completion_present"] is not False
        or p263.payload["runtime_identity"]["formal_completion_present"] is not True
    ):
        raise MeasurementCompatibilityError("compatibility_pair_not_superseding")


def load_measurement_compatibility_request(
    path: Path,
    *,
    p261: MeasurementCompatibilityFixture,
    p263: MeasurementCompatibilityFixture,
) -> MeasurementCompatibilityRequest:
    payload = _load_json(path)
    digest = str(payload.get("artifact_digest") or "")
    classification = _mapping(
        payload.get("change_classification"), field="request_classification"
    )
    frozen = _mapping(payload.get("frozen_boundary"), field="request_frozen")
    superseding = _mapping(
        payload.get("superseding_boundary"), field="request_superseding"
    )
    semantics = _mapping(
        payload.get("compatibility_semantics"), field="request_semantics"
    )
    blind = _mapping(payload.get("result_blind_freeze"), field="request_blind")
    integration = _mapping(
        payload.get("mainline_integration"), field="request_integration"
    )
    promotion = _mapping(payload.get("promotion_boundary"), field="request_promotion")
    agent = _mapping(payload.get("agent_request"), field="request_agent")
    validate_measurement_compatibility_pair(p261, p263)
    if (
        set(payload)
        != {
            "schema_version",
            "artifact_type",
            "artifact_digest",
            "request_key",
            "semantic_version",
            "status",
            "change_classification",
            "frozen_boundary",
            "superseding_boundary",
            "compatibility_semantics",
            "result_blind_freeze",
            "mainline_integration",
            "promotion_boundary",
            "agent_request",
            "production_action",
        }
        or payload.get("schema_version")
        != "dehps-m4-p2-measurement-v2-compatibility-request.v1"
        or payload.get("artifact_type") != "measurement_contract_compatibility_request"
        or payload.get("request_key") != "m4-p2-measurement-v2-compatibility-request"
        or payload.get("semantic_version") != "1.0.0"
        or payload.get("status") != "FROZEN_SOURCE_INTEGRATION_PENDING"
        or payload.get("production_action") != "none"
        or digest != COMPATIBILITY_REQUEST_DIGEST
        or config_digest(payload) != digest
        or classification
        != {
            "type": "MEASUREMENT_CONTRACT_EVOLUTION",
            "impact": "HIGH",
            "affected": [
                "MATHEMATICAL_KERNEL",
                "INDEPENDENT_ORACLE",
                "ACCELERATION_BACKEND",
                "RUNTIME_ORCHESTRATION",
            ],
        }
        or frozen.get("fixture_digest") != p261.artifact_digest
        or frozen.get("manifest_digest") != p261.payload["manifest_digest"]
        or frozen.get("task_digest") != p261.payload["source"]["task_digest"]
        or frozen.get("formal_completion_present") is not False
        or superseding.get("fixture_digest") != p263.artifact_digest
        or superseding.get("manifest_digest") != p263.payload["manifest_digest"]
        or superseding.get("task_digest") != p263.payload["source"]["task_digest"]
        or superseding.get("periodic_refit_policy_digest") != P263_POLICY_DIGEST
        or superseding.get("formal_completion_present") is not True
        or semantics.get("relationship")
        != "P2.6.3_SUPERSEDES_P2.6.1_FOR_FUTURE_MEASUREMENT_EXECUTION"
        or semantics.get("same_task_key_reused_in_source_history") is not True
        or semantics.get("same_task_identity") is not False
        or semantics.get("in_place_identity_rewrite_allowed") is not False
        or semantics.get("old_runtime_artifacts_deleted") is not False
        or semantics.get("old_results_or_checkpoints_reused") is not False
        or semantics.get("old_and_new_results_mixed") is not False
        or semantics.get("both_fixture_replays_required") is not True
        or semantics.get("digest_expectation_rebind_without_fixture") != "FORBIDDEN"
        or set(blind.values()) != {False}
        or integration.get("goal") != "M4_INFORMATION_THEORY_EVIDENCE"
        or integration.get("task") != "m4-p2-6-3-superseding-compatibility-acceptance"
        or integration.get("runner") != "research_evidence_supervisor"
        or integration.get("next_consumer") != "m4-v2-measurement-contract-design"
        or integration.get("evidence_rule")
        != "zero_compatibility_and_replay_attestations_are_not_research_evidence"
        or promotion
        != {
            "prediction_v2_promotion_allowed": False,
            "production_mainline_switch_allowed": False,
            "p3_allowed": False,
            "required_next_gate": "MEASUREMENT_V2_RUNTIME_AUDIT_AND_FULL_REPLAY",
        }
        or agent
        != {
            "request_id": 292,
            "execution_id": 213,
            "request_key": (
                "engineering-m4-p263-superseding-compatibility-round-24-20260807"
            ),
        }
    ):
        raise MeasurementCompatibilityError("compatibility_request_identity_changed")
    return MeasurementCompatibilityRequest(payload=payload, artifact_digest=digest)


def replay_measurement_source_fixture(
    *,
    root_dir: Path,
    fixture: MeasurementCompatibilityFixture,
) -> dict[str, Any]:
    source = fixture.payload["source"]
    object_name = f"{source['git_commit']}:{source['manifest_path']}"
    try:
        completed = subprocess.run(
            ("git", "show", object_name),
            cwd=root_dir,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise MeasurementCompatibilityError(
            "compatibility_source_fixture_unavailable"
        ) from exc
    raw = completed.stdout
    if sha256(raw).hexdigest() != source["manifest_content_sha256"]:
        raise MeasurementCompatibilityError("compatibility_source_bytes_changed")
    try:
        manifest = ControlPlaneManifest.from_dict(json.loads(raw))
    except (json.JSONDecodeError, ResearchOSValidationError) as exc:
        raise MeasurementCompatibilityError(
            "compatibility_source_manifest_invalid"
        ) from exc
    tasks = [item for item in manifest.tasks if item.task_key == source["task_key"]]
    if (
        manifest.artifact_digest != fixture.payload["manifest_digest"]
        or len(tasks) != 1
        or tasks[0].artifact_digest != source["task_digest"]
        or tasks[0].requested_capability != source["requested_capability"]
    ):
        raise MeasurementCompatibilityError("compatibility_source_replay_mismatch")
    payload: dict[str, Any] = {
        "schema_version": "dehps-m4-p2-source-fixture-replay.v1",
        "artifact_type": "measurement_source_fixture_replay",
        "artifact_digest": "",
        "status": "REPLAY_VERIFIED",
        "fixture_digest": fixture.artifact_digest,
        "phase": fixture.phase,
        "git_commit": source["git_commit"],
        "manifest_digest": manifest.artifact_digest,
        "task_digest": tasks[0].artifact_digest,
        "requested_capability": tasks[0].requested_capability,
        "historical_outcomes_read": False,
        "evidence_created": False,
        "evidence_progress_increment": 0,
        "production_action": "none",
        "parent_digests": [fixture.artifact_digest, manifest.artifact_digest],
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4.p2.measurement-source-fixture-replay.v1",
    )
    return payload


def build_measurement_compatibility_acceptance(
    *,
    request: MeasurementCompatibilityRequest,
    p261: MeasurementCompatibilityFixture,
    p263: MeasurementCompatibilityFixture,
    p261_replay: Mapping[str, Any],
    p263_replay: Mapping[str, Any],
    execution_id: str,
    git_commit: str,
) -> dict[str, Any]:
    # The request loader is the single trust boundary for the fixture pair.
    # Repeating that validation here would make the mainline replay the same
    # source-independent checks twice without adding a new invariant.
    for fixture, replay in ((p261, p261_replay), (p263, p263_replay)):
        if (
            replay.get("status") != "REPLAY_VERIFIED"
            or replay.get("fixture_digest") != fixture.artifact_digest
            or replay.get("manifest_digest") != fixture.payload["manifest_digest"]
            or replay.get("task_digest") != fixture.payload["source"]["task_digest"]
            or replay.get("historical_outcomes_read") is not False
        ):
            raise MeasurementCompatibilityError(
                "compatibility_acceptance_replay_invalid"
            )
    payload: dict[str, Any] = {
        "schema_version": "dehps-m4-p2-measurement-compatibility-acceptance.v1",
        "artifact_type": "MeasurementCompatibilityAcceptanceArtifact",
        "artifact_digest": "",
        "status": "VERIFIED",
        "request_digest": request.artifact_digest,
        "execution_id": execution_id,
        "git_commit": git_commit,
        "frozen_phase": p261.phase,
        "frozen_fixture_digest": p261.artifact_digest,
        "frozen_manifest_digest": p261.payload["manifest_digest"],
        "frozen_task_digest": p261.payload["source"]["task_digest"],
        "frozen_formal_completion_present": False,
        "superseding_phase": p263.phase,
        "superseding_fixture_digest": p263.artifact_digest,
        "superseding_manifest_digest": p263.payload["manifest_digest"],
        "superseding_task_digest": p263.payload["source"]["task_digest"],
        "superseding_formal_completion_present": True,
        "relationship": ("P2.6.3_SUPERSEDES_P2.6.1_FOR_FUTURE_MEASUREMENT_EXECUTION"),
        "same_task_identity": False,
        "old_results_or_checkpoints_reused": False,
        "both_source_fixture_replays_verified": True,
        "historical_outcomes_read": False,
        "evidence_created": False,
        "evidence_progress_increment": 0,
        "prediction_v2_promotion_allowed": False,
        "production_action": "none",
        "next_consumer": "m4-v2-measurement-contract-design",
        "parent_digests": [
            request.artifact_digest,
            p261.artifact_digest,
            p263.artifact_digest,
            str(p261_replay["artifact_digest"]),
            str(p263_replay["artifact_digest"]),
        ],
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain="dehps.m4.p2.measurement-compatibility-acceptance.v1",
    )
    return payload
