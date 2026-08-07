from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from dehps.research_os.information_theory.digest import config_digest
from dehps.research_os.information_theory.measurement_system_v2 import (
    COMPATIBILITY_REQUEST_DIGEST,
    COMPATIBILITY_REQUEST_PATH,
    P261_FROZEN_FIXTURE_DIGEST,
    P261_FROZEN_FIXTURE_PATH,
    P263_SUPERSEDING_FIXTURE_DIGEST,
    P263_SUPERSEDING_FIXTURE_PATH,
    MeasurementCompatibilityError,
    build_measurement_compatibility_acceptance,
    load_measurement_compatibility_fixture,
    load_measurement_compatibility_request,
    replay_measurement_source_fixture,
)
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.supervisor import (
    M4_P263_COMPATIBILITY_CAPABILITY,
    M4_P263_COMPATIBILITY_TASK_KEY,
    M4P263SupersedingCompatibilityCapability,
)

ROOT = Path(__file__).resolve().parents[3]
P261_REPLAY_DIGEST = "8a8f76a9df75feed30a8d7edbabd3ab572bfaba406f57e090223bf2f8a343a2f"
P263_REPLAY_DIGEST = "466e27854724e1a19b73287af32c9234794442e3f3fb1f4bb7885752c43fd592"


def _load_pair():
    p261 = load_measurement_compatibility_fixture(
        ROOT / P261_FROZEN_FIXTURE_PATH,
        expected_phase="M4-P2.6.1",
    )
    p263 = load_measurement_compatibility_fixture(
        ROOT / P263_SUPERSEDING_FIXTURE_PATH,
        expected_phase="M4-P2.6.3",
    )
    request = load_measurement_compatibility_request(
        ROOT / COMPATIBILITY_REQUEST_PATH,
        p261=p261,
        p263=p263,
    )
    return p261, p263, request


def test_frozen_and_superseding_identities_are_distinct_and_result_blind() -> None:
    p261, p263, request = _load_pair()
    assert p261.artifact_digest == P261_FROZEN_FIXTURE_DIGEST
    assert p263.artifact_digest == P263_SUPERSEDING_FIXTURE_DIGEST
    assert request.artifact_digest == COMPATIBILITY_REQUEST_DIGEST
    assert p261.payload["source"]["task_key"] == p263.payload["source"]["task_key"]
    assert (
        p261.payload["source"]["task_digest"] != p263.payload["source"]["task_digest"]
    )
    assert p261.payload["manifest_digest"] != p263.payload["manifest_digest"]
    assert set(p261.payload["result_blind"].values()) == {False}
    assert set(p263.payload["result_blind"].values()) == {False}
    assert set(request.payload["result_blind_freeze"].values()) == {False}


def test_both_source_manifests_replay_from_their_immutable_commits() -> None:
    p261, p263, _ = _load_pair()
    old_replay = replay_measurement_source_fixture(root_dir=ROOT, fixture=p261)
    new_replay = replay_measurement_source_fixture(root_dir=ROOT, fixture=p263)
    assert old_replay["artifact_digest"] == P261_REPLAY_DIGEST
    assert new_replay["artifact_digest"] == P263_REPLAY_DIGEST
    assert old_replay["task_digest"] != new_replay["task_digest"]
    assert old_replay["historical_outcomes_read"] is False
    assert new_replay["historical_outcomes_read"] is False
    assert old_replay["evidence_created"] is False
    assert new_replay["evidence_created"] is False


def test_fixture_identity_rebind_is_rejected_even_with_a_new_self_digest() -> None:
    p261, _, _ = _load_pair()
    changed = copy.deepcopy(dict(p261.payload))
    changed["source"]["task_digest"] = "f" * 64
    changed["artifact_digest"] = config_digest(changed)
    with pytest.raises(
        MeasurementCompatibilityError,
        match="compatibility_fixture_identity_changed",
    ):
        load_measurement_compatibility_fixture_from_payload_for_test(changed)


def load_measurement_compatibility_fixture_from_payload_for_test(payload):
    from dehps.research_os.information_theory.measurement_system_v2.compatibility import (
        validate_measurement_compatibility_fixture,
    )

    return validate_measurement_compatibility_fixture(
        payload,
        expected_phase="M4-P2.6.1",
    )


def test_acceptance_binds_both_replays_without_creating_evidence() -> None:
    p261, p263, request = _load_pair()
    old_replay = replay_measurement_source_fixture(root_dir=ROOT, fixture=p261)
    new_replay = replay_measurement_source_fixture(root_dir=ROOT, fixture=p263)
    acceptance = build_measurement_compatibility_acceptance(
        request=request,
        p261=p261,
        p263=p263,
        p261_replay=old_replay,
        p263_replay=new_replay,
        execution_id="e" * 64,
        git_commit="a68016c189ca8dc066fa9ca01cc67f3ccf916a12",
    )
    assert acceptance["artifact_digest"] == (
        "5e1096c08b0a65a19e96dc0a33ed0b79aa9c74784c6e2143b7ce249cc53fbe4f"
    )
    assert acceptance["both_source_fixture_replays_verified"] is True
    assert acceptance["old_results_or_checkpoints_reused"] is False
    assert acceptance["historical_outcomes_read"] is False
    assert acceptance["evidence_created"] is False
    assert acceptance["prediction_v2_promotion_allowed"] is False


def test_compatibility_capability_materializes_the_canonical_mainline_chain(
    tmp_path: Path,
) -> None:
    for relative in (
        COMPATIBILITY_REQUEST_PATH,
        P261_FROZEN_FIXTURE_PATH,
        P263_SUPERSEDING_FIXTURE_PATH,
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    manifest = ControlPlaneManifest.from_dict(
        json.loads(
            (
                ROOT / "configs/research-os/m4-information-theory-evidence-v1.json"
            ).read_text(encoding="utf-8")
        )
    )
    task = next(
        item
        for item in manifest.tasks
        if item.task_key == M4_P263_COMPATIBILITY_TASK_KEY
    )
    assert task.requested_capability == M4_P263_COMPATIBILITY_CAPABILITY
    result = M4P263SupersedingCompatibilityCapability(
        root_dir=tmp_path,
        source_repository_dir=ROOT,
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="c" * 64,
        git_commit="d" * 40,
    )
    assert result.completion_facts == ("m4-p2-6-3-compatibility:VERIFIED",)
    assert result.execution_artifact["completion_classification"] == (
        "VALIDATED_IN_MAINLINE"
    )
    assert result.execution_artifact["replay_status"] == "REPLAY_VERIFIED"
    assert result.execution_artifact["evidence_progress_before"] == 25
    assert result.execution_artifact["evidence_progress_after"] == 25
    assert result.execution_artifact["prediction_v2_promotion_allowed"] is False
    assert len(result.registrations) == 4
    assert {item.artifact_type for item in result.registrations} == {
        "measurement_source_fixture_replay",
        "MeasurementCompatibilityAcceptanceArtifact",
        "research_os_mainline_execution",
    }
    assert result.execution_artifact_path.is_file()
