import json
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest
from dehps import cli
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory import (
    ArtifactContractViolation,
    InformationTheoryValidationError,
    PhaseGateError,
    build_m4_status,
    freeze_preregistration,
    information_theory_contract_digest,
    load_m4_manifest,
    preregistration_digest,
    require_formal_run_gate,
    validate_artifact_identity,
    validate_decision_policy,
    validate_p2_input_contract,
    validate_preregistration,
)
from dehps.research_os.information_theory.contracts import (
    DeterministicTaskContract,
    RandomizedTaskContract,
)
from dehps.research_os.information_theory.digest import config_digest
from dehps.research_os.models import TaskStatus
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[3]
PREREG_PATH = ROOT / "configs/research-os/m4-information-theory-preregistration-v1.json"
POLICY_PATH = ROOT / "configs/research-os/m4-information-theory-decision-policy-v1.json"
P2_INPUT_PATH = ROOT / "configs/research-os/m4-information-theory-p2-input-v1.json"
MANIFEST_PATH = ROOT / "configs/research-os/m4-information-theory-evidence-v1.json"


def _load(path: Path = PREREG_PATH):
    return json.loads(path.read_text(encoding="utf-8"))


def _expect_invalid(payload, code: str) -> None:
    with pytest.raises(InformationTheoryValidationError) as exc_info:
        validate_preregistration(payload)
    assert exc_info.value.code == code


def test_01_canonical_preregistration_validates_and_is_frozen() -> None:
    result = validate_preregistration(_load())
    assert result == {
        "valid": True,
        "status": "FROZEN",
        "version": "1.0.1",
        "digest": "6e03cd828378badda6995c6582d80165b0a4ee3b5899b97737bad1494fcf1ae1",
        "contract_version": "m4-information-theory-contract-v1",
    }


def test_02_missing_primary_endpoint_fails() -> None:
    payload = _load()
    payload["primary_endpoints"].pop()
    _expect_invalid(payload, "missing_primary_endpoints")


def test_03_missing_practical_null_fails() -> None:
    payload = _load()
    payload.pop("practical_null")
    _expect_invalid(payload, "missing_practical_null")


def test_04_missing_negative_control_fails() -> None:
    payload = _load()
    payload["negative_controls"].pop()
    _expect_invalid(payload, "missing_negative_controls")


def test_05_missing_injected_signal_fails() -> None:
    payload = _load()
    payload["synthetic_validation"]["injected_signals"].pop()
    _expect_invalid(payload, "missing_synthetic_injected_signal")


def test_06_missing_multiplicity_family_fails() -> None:
    payload = _load()
    payload["multiplicity"]["families"].pop("PAIR_FAMILY")
    _expect_invalid(payload, "missing_multiplicity_family")


def test_07_missing_power_policy_fails() -> None:
    payload = _load()
    payload["power_equivalence"].pop("target_power")
    _expect_invalid(payload, "missing_power_policy")


def test_08_missing_decision_policy_fails() -> None:
    payload = _load()
    payload["decision_policy"].pop("digest")
    _expect_invalid(payload, "missing_decision_policy")


def test_09_missing_dataset_identity_fails() -> None:
    payload = _load()
    payload["dataset_identity"].pop("history_dataset_digest")
    _expect_invalid(payload, "missing_dataset_identity")


def test_10_dirty_worktree_freeze_fails(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@dehps.local"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "DEHPS Test"], cwd=tmp_path, check=True)
    marker = tmp_path / "tracked.txt"
    marker.write_text("clean\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=tmp_path, check=True)
    marker.write_text("dirty\n", encoding="utf-8")
    with pytest.raises(InformationTheoryValidationError) as exc_info:
        freeze_preregistration(_load(), output_dir=tmp_path / "out", repo_root=tmp_path)
    assert exc_info.value.code == "dirty_worktree"


def test_11_frozen_content_cannot_change_in_place() -> None:
    payload = _load()
    payload["practical_null"]["rationale"] += " changed after freeze"
    _expect_invalid(payload, "frozen_preregistration_modified")


def test_12_new_version_can_trace_superseded_digest() -> None:
    payload = _load()
    old_digest = payload.pop("artifact_digest")
    payload.pop("working_tree_clean")
    payload.pop("code_commit")
    payload["status"] = "VALIDATED"
    payload["version"] = "1.1.0"
    payload["supersedes_digest"] = old_digest
    result = validate_preregistration(payload)
    assert result["valid"] is True
    assert result["digest"] != old_digest


def test_13_deterministic_contract_rejects_seed_policy() -> None:
    assert DeterministicTaskContract.from_dict(
        {"task_key": "digest", "seed_policy": "none"}
    ).task_key == "digest"
    with pytest.raises(ValueError, match="cannot carry"):
        DeterministicTaskContract.from_dict(
            {"task_key": "digest", "seed_policy": {"seeds": [1]}}
        )


def test_14_randomized_control_without_seed_policy_fails() -> None:
    payload = _load()
    payload["negative_controls"][0].pop("seed_policy")
    _expect_invalid(payload, "randomized_control_seed_policy_invalid")
    with pytest.raises(ValueError, match="requires seed_policy"):
        RandomizedTaskContract.from_dict({"task_key": "random", "replicate_count": 1})


def test_15_formal_run_is_phase_gated() -> None:
    with pytest.raises(PhaseGateError) as exc_info:
        require_formal_run_gate(p1_status="FROZEN", p2_status="NOT_STARTED")
    assert exc_info.value.code == "phase_gate_not_satisfied"
    result = CliRunner().invoke(
        cli.app,
        ["research-os", "information-theory", "run"],
    )
    assert result.exit_code == 2
    assert "phase_gate_not_satisfied" in result.stdout + result.stderr


def test_16_preregistration_digest_is_stable() -> None:
    payload = _load()
    assert preregistration_digest(payload) == payload["artifact_digest"]


def test_17_object_field_order_does_not_change_digest() -> None:
    payload = _load()
    reordered = dict(reversed(list(payload.items())))
    assert preregistration_digest(reordered) == preregistration_digest(payload)


def test_18_substantive_content_changes_digest() -> None:
    payload = _load()
    changed = deepcopy(payload)
    changed["walk_forward"]["minimum_training_issues"] = 901
    assert preregistration_digest(changed) != preregistration_digest(payload)


def test_19_old_training_mainline_remains_rejected_and_frozen() -> None:
    status = build_m4_status(load_m4_manifest(MANIFEST_PATH))
    assert status["previous_goal_research_status"] == "REJECTED"
    assert status["old_training_mainline"] == "FROZEN"


def test_20_promotion_gate_remains_closed() -> None:
    status = build_m4_status(load_m4_manifest(MANIFEST_PATH))
    assert status["gate_status"]["promotion_gate"] == "CLOSED"


def test_21_adaptive_supervisor_remains_stopped() -> None:
    status = build_m4_status(load_m4_manifest(MANIFEST_PATH))
    assert status["gate_status"]["adaptive_supervisor"] == "STOPPED"


def test_22_2026085_remains_external_wait_and_ineligible() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    snapshot = ResearchOSControlPlane().resolve(manifest)
    by_task = {item.task_key: item for item in snapshot.resolutions}
    assert (
        by_task["m4-forward-evidence-intake-2026085"].status
        is TaskStatus.EXTERNAL_WAIT
    )
    status = build_m4_status(manifest, snapshot=snapshot)
    assert status["forward_event_2026085"]["m4_forward_evidence_eligible"] is False
    assert status["progress"]["forward_samples"]["retroactively_ineligible_issues"] == [
        "2026085"
    ]


def test_23_engineering_progress_records_preflight_mainline_execution() -> None:
    status = build_m4_status(load_m4_manifest(MANIFEST_PATH))
    assert status["progress"]["engineering_percent"] == 38
    assert status["p2_subphase"]["completion_classification"] == "COMPLETE"


def test_24_evidence_progress_remains_zero() -> None:
    status = build_m4_status(load_m4_manifest(MANIFEST_PATH))
    assert status["progress"]["evidence_percent"] == 0
    assert status["current_statistics"]["evidence_state"] == "NOT_STARTED"


def test_25_resolver_advances_only_to_measurement_repair() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    snapshot = ResearchOSControlPlane().resolve(manifest)
    assert [item.task_key for item in snapshot.ready_queue] == [
        "m4-p2-repair-measurement-system"
    ]
    status = build_m4_status(manifest, snapshot=snapshot)
    assert (status["current_phase"], status["current_state"]) == (
        "M4-P2",
        "REPAIR_REQUIRED",
    )


def test_26_decision_policy_is_digest_addressed_and_valid() -> None:
    result = validate_decision_policy(_load(POLICY_PATH))
    assert result["digest"] == "824f91d5d012caed9c7a273c7a3fb9fcf1b6c3fb6a4f0465707441c7c261790d"


def test_27_p2_input_contract_is_valid_but_not_executed() -> None:
    result = validate_p2_input_contract(_load(P2_INPUT_PATH))
    assert result == {"valid": True, "status": "VALID"}
    payload = _load(P2_INPUT_PATH)
    assert payload["synthetic_validation"] == "NOT_STARTED"
    assert payload["formal_real_data_analysis"] == "NOT_STARTED"


def test_28_artifact_identity_enforces_seed_policy_by_execution_mode() -> None:
    base = {
        "schema_version": "artifact.v1",
        "artifact_type": "test",
        "artifact_digest": "a" * 64,
        "parent_digests": [],
        "created_at": "2026-07-24T14:30:00+08:00",
        "git_commit": "b" * 40,
        "working_tree_clean": True,
        "dataset_digest": "c" * 64,
        "preregistration_digest": "d" * 64,
        "config_digest": "e" * 64,
        "seed_policy": "none",
    }
    validate_artifact_identity(base, stochastic=False)
    with pytest.raises(ArtifactContractViolation):
        validate_artifact_identity(base, stochastic=True)


def test_29_contract_itself_is_digest_addressed() -> None:
    payload = _load(ROOT / "configs/research-os/m4-information-theory-contract-v1.json")
    assert information_theory_contract_digest(payload) == payload["artifact_digest"]


def test_artifact_index_keeps_every_registered_identity_replayable() -> None:
    index = _load(
        ROOT / "configs/research-os/m4-information-theory-artifact-index-v1.json"
    )
    for digest, entry in index["artifacts"].items():
        if "path" in entry:
            artifact = _load(ROOT / entry["path"])
            identity_field = entry.get("identity_field", "artifact_digest")
            if identity_field == "manifest_digest":
                if entry["artifact_type"] == (
                    "measurement_source_compatibility_fixture"
                ):
                    assert artifact["artifact_type"] == (
                        "measurement_source_compatibility_fixture"
                    )
                    assert entry["fixture_artifact_digest"] == artifact[
                        "artifact_digest"
                    ]
                    assert config_digest(artifact) == artifact["artifact_digest"]
                else:
                    assert entry["artifact_type"] == (
                        "research_os_control_plane_manifest"
                    )
            else:
                assert identity_field == "artifact_digest"
            identity = artifact.get(identity_field)
            assert identity == digest
        elif "path_at_source" in entry:
            assert len(entry["source_commit"]) == 40
            assert entry["path_at_source"].endswith(".json")
        else:
            assert len(entry["source_commit"]) == 40
            assert entry["runtime_path"].endswith(".json")
        if entry["artifact_type"] == "superseded_information_theory_preregistration":
            if "runtime_path" in entry:
                assert entry["runtime_path"].endswith(
                    f"{digest}/preregistration.json"
                )
            assert entry["superseded_by_digest"] in index["artifacts"]
