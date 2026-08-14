from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2.fixture_freeze import (
    FIXTURE_FREEZE_TASK_KEY,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_contract import (
    MARGINAL_STATIC_CONTRACT_FREEZE_COMPLETION_FACT,
    MARGINAL_STATIC_CONTRACT_FREEZE_TASK_KEY,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_fixtures import (
    FIXTURE_ORDER,
    MARGINAL_STATIC_FIXTURE_FREEZE_CAPABILITY,
    MARGINAL_STATIC_FIXTURE_FREEZE_COMPLETION_FACT,
    MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY,
    MARGINAL_STATIC_FIXTURE_SOURCE_CONTRACT_PATH,
    MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY,
    MarginalStaticFixtureError,
    MarginalSufficientStatistics,
    build_marginal_static_fixture_artifacts,
    load_marginal_static_fixture_source_contract,
    verify_marginal_static_fixture_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.measurement_system_v2.preflight_execution import (
    PREFLIGHT_EXECUTION_PASS_FACT,
    PREFLIGHT_EXECUTION_TASK_KEY,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.supervisor import (
    M4MarginalStaticFixtureFreezeCapability,
    ResearchEvidenceSupervisor,
)

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "apps/worker-python/tests/fixtures/research_os/m4-information-theory-evidence-head-b6c03ba.json"
SOURCE_CONTRACT_PATH = ROOT / MARGINAL_STATIC_FIXTURE_SOURCE_CONTRACT_PATH


def _copy_source_contract_tree(target_root: Path) -> dict:
    contract = load_marginal_static_fixture_source_contract(SOURCE_CONTRACT_PATH)
    for entry in contract["source_entries"]:
        relative = Path(entry["path"])
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    target_contract = target_root / MARGINAL_STATIC_FIXTURE_SOURCE_CONTRACT_PATH
    target_contract.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_CONTRACT_PATH, target_contract)
    return contract


def _inputs() -> tuple[dict, dict, dict, dict, dict, dict, dict]:
    source = load_marginal_static_fixture_source_contract(SOURCE_CONTRACT_PATH)
    marginal_contract = {
        "artifact_type": "m4_v2_marginal_static_measurement_contract",
        "artifact_digest": "1" * 64,
        "status": "FROZEN_SYNTHETIC_HEALTH_PENDING",
        "legacy_measurement_health": "REPAIR",
        "legacy_repair_overridden": False,
        "historical_execution_status": "NOT_AUTHORIZED",
        "accepted_model_artifact_digest": None,
        "next_fixture_obligations": {
            "positive_control": "V2_M1_GROUP_ODDS_2_STATIONARY",
            "negative_controls": [
                "NULL_UNIFORM_LEGAL_SIX_OF_33",
                (
                    "V2_T1_OVERLAP_ODDS_2_MARKOV projected to stationary "
                    "marginals"
                ),
                (
                    "V2_J1_HISTORY_IS4_LAMBDA_HALF projected to stationary "
                    "marginals"
                ),
            ],
        },
    }
    marginal_completion = {
        "artifact_type": "m4_v2_marginal_static_contract_freeze_completion",
        "artifact_digest": "2" * 64,
        "status": "COMPLETE",
        "completion_fact": MARGINAL_STATIC_CONTRACT_FREEZE_COMPLETION_FACT,
        "marginal_static_measurement_contract_digest": marginal_contract[
            "artifact_digest"
        ],
    }
    fixture_specs = {
        item["fixture_id"]: item for item in source["frozen_contract"]["fixtures"]
    }
    orthogonal_fixtures = []
    for fixture_id in (
        FIXTURE_ORDER[0],
        FIXTURE_ORDER[2],
        FIXTURE_ORDER[3],
        FIXTURE_ORDER[1],
    ):
        role = fixture_specs[fixture_id]["role"]
        orthogonal_fixtures.append(
            {
                "fixture_id": fixture_id,
                "definition": fixture_specs[fixture_id]["generator"].get(
                    "process", "uniform"
                ),
                "expected_roles": {
                    "MARGINAL_STATIC": role,
                    "TEMPORAL_MARGINAL_INCREMENT": "NEGATIVE_CONTROL",
                    "JOINT_RESIDUAL_INCREMENT": "NEGATIVE_CONTROL",
                },
                "truth_anchor_bits": {
                    "marginal_static": (
                        0.4403398887146399 if role == "POSITIVE_CONTROL" else 0.0
                    ),
                    "temporal_increment": 0.0,
                    "joint_residual": 0.0,
                },
            }
        )
    orthogonal = {
        "artifact_type": "m4_v2_orthogonal_control_fixture_contract",
        "artifact_digest": "3" * 64,
        "status": "FROZEN_FIXTURES",
        "fixtures": orthogonal_fixtures,
    }
    fixture_completion = {
        "artifact_type": "m4_v2_branch_fixture_freeze_completion",
        "artifact_digest": "4" * 64,
        "status": "COMPLETE",
        "orthogonal_control_fixture_contract_digest": orthogonal[
            "artifact_digest"
        ],
    }
    health = {
        "artifact_type": "m4_v2_branch_health_preflight_result",
        "artifact_digest": "5" * 64,
        "branch_id": "MARGINAL_STATIC",
        "status": "PASS",
        "measurement_health": "PASS",
        "decision_credit": False,
        "historical_evidence_eligible": False,
        "primary_positive_fixture_id": "V2_M1_GROUP_ODDS_2_STATIONARY",
        "negative_endpoint_keys": [
            "V2_T1_OVERLAP_ODDS_2_MARKOV:MARGINAL_STATIC",
            "V2_J1_HISTORY_IS4_LAMBDA_HALF:MARGINAL_STATIC",
            "NULL_UNIFORM_LEGAL_SIX_OF_33:MARGINAL_STATIC",
        ],
    }
    preflight_completion = {
        "artifact_type": "m4_v2_branch_preflight_execution_completion",
        "artifact_digest": "6" * 64,
        "status": "COMPLETE",
        "all_branches_pass": True,
        "all_branches_pass_fact": PREFLIGHT_EXECUTION_PASS_FACT,
        "branch_result_digests": [health["artifact_digest"]],
    }
    return (
        source,
        marginal_contract,
        marginal_completion,
        orthogonal,
        fixture_completion,
        health,
        preflight_completion,
    )


def _build_run() -> object:
    (
        source,
        marginal_contract,
        marginal_completion,
        orthogonal,
        fixture_completion,
        health,
        preflight_completion,
    ) = _inputs()
    return build_marginal_static_fixture_artifacts(
        source_contract=source,
        marginal_contract_execution_artifact_digest="7" * 64,
        marginal_measurement_contract=marginal_contract,
        marginal_contract_completion=marginal_completion,
        orthogonal_fixture_contract=orthogonal,
        branch_fixture_completion=fixture_completion,
        marginal_branch_health=health,
        preflight_completion=preflight_completion,
        execution_id="8" * 64,
        git_commit="9" * 40,
    )


def test_sufficient_statistics_updates_in_memory_without_database_or_csv() -> None:
    state = MarginalSufficientStatistics()
    state.update((1, 2, 3, 4, 5, 6))
    state.update((1, 7, 8, 9, 10, 11))
    snapshot = state.snapshot()

    assert state.number_event_counts.itemsize == 8
    assert snapshot["issue_count"] == 2
    assert snapshot["number_event_counts_1_to_33"][0] == 2
    assert sum(snapshot["number_event_counts_1_to_33"]) == 12
    assert snapshot["database_reads"] == 0
    assert snapshot["database_writes"] == 0
    assert snapshot["csv_materialized"] is False

    with pytest.raises(MarginalStaticFixtureError, match="draw_invalid"):
        state.update((1, 1, 2, 3, 4, 5))


def test_fixture_freeze_is_deterministic_orthogonal_and_zero_work() -> None:
    first = _build_run()
    second = _build_run()

    assert first == second
    assert len(first.fixtures) == 4
    assert len(first.artifacts) == 6
    assert tuple(item["fixture_id"] for item in first.fixtures) == FIXTURE_ORDER
    assert [item["role"] for item in first.fixtures] == [
        "POSITIVE_CONTROL",
        "NEGATIVE_CONTROL",
        "NEGATIVE_CONTROL",
        "NEGATIVE_CONTROL",
    ]
    assert first.fixtures[0]["stationary_marginal_truth"] == {
        "group_a_numbers": "1..16",
        "group_a_q": "47343/200861",
        "group_b_numbers": "17..33",
        "group_b_q": "26334/200861",
        "exact_sum": "16*q_a+17*q_b=6",
    }
    assert first.fixtures[0]["expected_marginal_gain_bits_per_issue"] == pytest.approx(
        0.4403398887146399,
        abs=1e-15,
    )
    assert all(
        item["expected_marginal_gain_bits_per_issue"] == 0.0
        for item in first.fixtures[1:]
    )
    assert first.bundle["sampled_workload_status"] == "NOT_FROZEN"
    assert first.bundle["runtime_boundary"]["database_reads_during_replicate"] == 0
    assert first.bundle["runtime_boundary"]["duplicate_raw_replay"] == "forbidden"
    assert first.completion["generated_issues"] == 0
    assert first.completion["synthetic_replicates"] == 0
    assert first.completion["actual_fold_count"] == 0
    assert first.completion["evidence_created"] is False
    assert first.completion["next_consumer"] == MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY


def test_fixture_freeze_fails_closed_on_truth_or_lineage_drift() -> None:
    values = list(_inputs())
    values[3]["fixtures"][0]["truth_anchor_bits"]["marginal_static"] = 0.4
    with pytest.raises(MarginalStaticFixtureError, match="truth_anchor_changed"):
        build_marginal_static_fixture_artifacts(
            source_contract=values[0],
            marginal_contract_execution_artifact_digest="7" * 64,
            marginal_measurement_contract=values[1],
            marginal_contract_completion=values[2],
            orthogonal_fixture_contract=values[3],
            branch_fixture_completion=values[4],
            marginal_branch_health=values[5],
            preflight_completion=values[6],
            execution_id="8" * 64,
            git_commit="9" * 40,
        )

    values = list(_inputs())
    values[5]["historical_evidence_eligible"] = True
    with pytest.raises(MarginalStaticFixtureError, match="input_identity_changed"):
        build_marginal_static_fixture_artifacts(
            source_contract=values[0],
            marginal_contract_execution_artifact_digest="7" * 64,
            marginal_measurement_contract=values[1],
            marginal_contract_completion=values[2],
            orthogonal_fixture_contract=values[3],
            branch_fixture_completion=values[4],
            marginal_branch_health=values[5],
            preflight_completion=values[6],
            execution_id="8" * 64,
            git_commit="9" * 40,
        )


def test_source_contract_detects_byte_and_contract_tamper(tmp_path: Path) -> None:
    contract = _copy_source_contract_tree(tmp_path)
    verify_marginal_static_fixture_source_bytes(root_dir=tmp_path, contract=contract)

    source_path = tmp_path / contract["source_entries"][0]["path"]
    source_path.write_bytes(source_path.read_bytes() + b"\n# tampered\n")
    with pytest.raises(MarginalStaticFixtureError, match="source_modified"):
        verify_marginal_static_fixture_source_bytes(
            root_dir=tmp_path,
            contract=contract,
        )

    drifted = deepcopy(contract)
    drifted["frozen_contract"]["runtime_boundary"][
        "database_reads_during_replicate"
    ] = 1
    drifted["artifact_digest"] = "0" * 64
    drift_path = tmp_path / "drift.json"
    drift_path.write_text(json.dumps(drifted), encoding="utf-8")
    with pytest.raises(MarginalStaticFixtureError, match="source_invalid"):
        load_marginal_static_fixture_source_contract(drift_path)


def test_capability_materializes_seven_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _copy_source_contract_tree(tmp_path)
    manifest = load_m4_manifest(MANIFEST_PATH)
    task = next(
        item
        for item in manifest.tasks
        if item.task_key == MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY
    )
    (
        _,
        marginal_contract,
        marginal_completion,
        orthogonal,
        fixture_completion,
        health,
        preflight_completion,
    ) = _inputs()
    expected = task.input_artifact_digests
    marginal_contract["artifact_digest"] = expected[2]
    marginal_completion["artifact_digest"] = expected[3]
    marginal_completion["marginal_static_measurement_contract_digest"] = expected[2]
    orthogonal["artifact_digest"] = expected[4]
    fixture_completion["artifact_digest"] = expected[5]
    fixture_completion["orthogonal_control_fixture_contract_digest"] = expected[4]
    health["artifact_digest"] = expected[6]
    preflight_completion["artifact_digest"] = expected[7]
    preflight_completion["branch_result_digests"] = [expected[6]]
    marginal_execution = {
        "execution_id": "a" * 64,
        "artifact_digest": expected[1],
        "completion_fact": MARGINAL_STATIC_CONTRACT_FREEZE_COMPLETION_FACT,
        "actual_fold_count": 0,
        "synthetic_replicates": 0,
        "historical_outcomes_read": False,
        "evidence_created": False,
        "legacy_repair_overridden": False,
    }

    def fake_load_parent(**kwargs: object) -> tuple[dict, dict, object]:
        task_key = kwargs["task_key"]
        if task_key == MARGINAL_STATIC_CONTRACT_FREEZE_TASK_KEY:
            return {}, marginal_execution, "marginal"
        if task_key == FIXTURE_FREEZE_TASK_KEY:
            return {}, {}, "fixture"
        assert task_key == PREFLIGHT_EXECUTION_TASK_KEY
        return {}, {}, "preflight"

    def fake_registered_type(**kwargs: object) -> dict:
        return {
            "m4_v2_marginal_static_measurement_contract": marginal_contract,
            "m4_v2_marginal_static_contract_freeze_completion": (
                marginal_completion
            ),
            "m4_v2_orthogonal_control_fixture_contract": orthogonal,
            "m4_v2_branch_fixture_freeze_completion": fixture_completion,
            "m4_v2_branch_preflight_execution_completion": preflight_completion,
        }[kwargs["artifact_type"]]

    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        fake_load_parent,
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type",
        fake_registered_type,
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type_group",
        lambda **_: (health,),
    )
    result = M4MarginalStaticFixtureFreezeCapability(
        repository=object(),
        root_dir=tmp_path,
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="b" * 64,
        git_commit="c" * 40,
    )

    assert result.completion_facts == (
        MARGINAL_STATIC_FIXTURE_FREEZE_COMPLETION_FACT,
    )
    assert len(result.registrations) == 7
    assert result.execution_artifact["registered_artifact_count"] == 7
    assert result.execution_artifact["fixture_count"] == 4
    assert result.execution_artifact["database_reads_during_replicate"] == 0
    assert result.execution_artifact["csv_materialized"] is False
    assert result.execution_artifact["generated_issues"] == 0
    assert result.execution_artifact["historical_outcomes_read"] is False


def test_additive_migration_preserves_live_truth() -> None:
    source = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source.pop("manifest_digest")
    live = ControlPlaneManifest.from_dict(source).to_dict(include_digest=False)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"] != MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY
    ]
    live_fixture = next(
        item
        for item in live["tasks"]
        if item["task_key"] == MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY
    )
    live_fixture.pop("requested_capability")
    live_fixture.pop("input_artifact_digests")
    live_fixture["dependencies"] = live_fixture["dependencies"][:2]
    live_fixture["metric_contract"] = {
        key: value
        for key, value in live_fixture["metric_contract"].items()
        if key
        not in {
            "mainline_integration",
            "generated_issues",
            "database_reads_during_replicate",
            "database_writes_during_replicate",
            "csv_materialization",
        }
    }
    source_fact = next(
        item
        for item in source["facts"]["artifacts"]
        if item.startswith("m4-v2-marginal-static-fixture-freeze-source:")
    )
    live["facts"]["artifacts"].remove(source_fact)

    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY,),
        allowlisted_revised_task_keys=(MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY,),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )

    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY]
    assert dry_run["revised_task_keys"] == [
        MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY
    ]
    assert dry_run["existing_task_deletions"] == 0
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert source_fact in migrated["facts"]["artifacts"]


def test_completion_projects_health_design_as_only_next_consumer() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    fixture_task = next(
        item
        for item in manifest.tasks
        if item.task_key == MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY
    )
    for task in payload["tasks"]:
        if task["task_key"] == MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY:
            task["status"] = "completed"
            task["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        (
            MARGINAL_STATIC_FIXTURE_FREEZE_COMPLETION_FACT,
            mainline_completion_fact(task=fixture_task, execution_id="d" * 64),
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": MARGINAL_STATIC_FIXTURE_FREEZE_TASK_KEY,
            "execution_artifact_digest": "e" * 64,
            "registered_artifact_count": 7,
            "actual_fold_count": 0,
            "marginal_static_measurement_contract_digest": "f" * 64,
            "marginal_static_fixture_bundle_digest": "a" * 64,
            "fixture_count": 4,
            "positive_fixture_count": 1,
            "negative_fixture_count": 3,
            "runtime_state": (
                "issue_count plus ordered signed_int64[33] number-event counts"
            ),
            "estimator_id": "EXPANDING_LEGAL_MARGINAL_ALPHA_1",
            "identifiability_preflight_status": "PASS",
        },
    )
    projection = status["measurement_system_v2"]

    assert projection["phase"] == "MARGINAL_STATIC_HEALTH_DESIGN"
    assert projection["live_mainline_status"] == (
        "MARGINAL_STATIC_FIXTURES_VALIDATED_IN_MAINLINE"
    )
    assert projection["next_consumer"] == MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY
    fixtures = projection["marginal_static_fixture_freeze"]
    assert fixtures["completed"] is True
    assert fixtures["fixture_count"] == 4
    assert fixtures["database_reads_during_replicate"] == 0
    assert fixtures["csv_materialized"] is False
    assert fixtures["duplicate_raw_replay"] is False
    assert fixtures["routine_physical_checkpoint_scan"] is False
    assert fixtures["evidence_progress_increment"] == 0


def test_supervisor_registers_marginal_static_fixture_capability() -> None:
    supervisor = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    assert MARGINAL_STATIC_FIXTURE_FREEZE_CAPABILITY in supervisor.capabilities
