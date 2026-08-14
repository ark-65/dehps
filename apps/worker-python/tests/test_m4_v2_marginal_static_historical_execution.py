from __future__ import annotations

import hashlib
import json
import shutil
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pytest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2 import (
    marginal_static_historical_execution as execution_module,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_historical_execution import (
    HISTORICAL_CHECKPOINT_ORDER_MANIFEST_DIGEST,
    HISTORICAL_DATASET_CONTENT_DIGEST,
    HISTORICAL_DATASET_SNAPSHOT_DIGEST,
    HISTORICAL_EXECUTION_PLAN_DIGEST,
    HISTORICAL_FOLD_MANIFEST_DIGEST,
    HISTORICAL_PREREGISTRATION_COMPLETION_DIGEST,
    HISTORICAL_RESAMPLING_MANIFEST_DIGEST,
    MARGINAL_STATIC_HISTORICAL_EXECUTION_CAPABILITY,
    MARGINAL_STATIC_HISTORICAL_EXECUTION_COMPLETION_FACT,
    MARGINAL_STATIC_HISTORICAL_EXECUTION_TASK_KEY,
    MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY,
    MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_EXECUTION_DIGEST,
    MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_EXECUTION_ID,
    MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_DIGEST,
    MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY,
    MarginalStaticHistoricalExecutionError,
    build_marginal_static_historical_execution_artifacts,
    load_marginal_static_historical_execution_source_contract,
    score_issue,
    verify_marginal_static_historical_execution_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_historical_preregistration import (
    CHECKPOINT_PHASE_ORDER,
    EVALUATION_FOLD_COUNT,
    HISTORICAL_ISSUE_COUNT,
    INITIAL_TRAINING_ISSUES,
    RESAMPLING_CHILD_COUNT,
    RESAMPLING_SCHEMES,
    ROOT_REPLICATES,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.supervisor import (
    M4MarginalStaticHistoricalExecutionCapability,
    ResearchEvidenceSupervisor,
)

ROOT = Path(__file__).resolve().parents[3]
SOURCE_PATH = (
    ROOT / "configs/research-os/"
    "m4-v2-marginal-static-historical-execution-source-v1.json"
)
MANIFEST_PATH = ROOT / "apps/worker-python/tests/fixtures/research_os/m4-information-theory-evidence-head-b6c03ba.json"
INDEX_PATH = ROOT / "configs/research-os/m4-information-theory-artifact-index-v1.json"


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _synthetic_registered_inputs() -> dict[str, object]:
    records = []
    for index in range(HISTORICAL_ISSUE_COUNT):
        issue = (
            "2003001"
            if index == 0
            else "2026084"
            if index == HISTORICAL_ISSUE_COUNT - 1
            else f"{3000000 + index:07d}"
        )
        red_numbers = sorted(((index + offset) % 33) + 1 for offset in range(6))
        records.append(
            {
                "issue": issue,
                "draw_date": f"2020-01-{(index % 28) + 1:02d}",
                "red_numbers": red_numbers,
            }
        )
    folds = []
    orders = []
    for fold_index in range(EVALUATION_FOLD_COUNT):
        test_ordinal = INITIAL_TRAINING_ISSUES + fold_index + 1
        fold_digest = _digest(f"fold:{fold_index}")
        folds.append(
            {
                "fold_index": fold_index,
                "fold_digest": fold_digest,
                "training_start_ordinal": 1,
                "training_end_ordinal": test_ordinal - 1,
                "test_ordinal": test_ordinal,
                "test_issue": records[test_ordinal - 1]["issue"],
                "test_draw_date": records[test_ordinal - 1]["draw_date"],
            }
        )
        orders.append(
            {
                "fold_index": fold_index,
                "fold_digest": fold_digest,
                "test_ordinal": test_ordinal,
                "phase_order": list(CHECKPOINT_PHASE_ORDER),
                "order_digest": _digest(f"order:{fold_index}"),
            }
        )
    children = [
        {
            "replicate_index": replicate_index,
            "scheme_id": scheme_id,
            "root_seed": replicate_index,
            "child_digest": _digest(f"child:{replicate_index}:{scheme_id}"),
        }
        for replicate_index in range(ROOT_REPLICATES)
        for scheme_id in RESAMPLING_SCHEMES
    ]
    assert len(children) == RESAMPLING_CHILD_COUNT
    return {
        "preregistration_execution": {
            "execution_id": MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_EXECUTION_ID,
            "artifact_digest": (
                MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_EXECUTION_DIGEST
            ),
            "task_key": MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY,
            "task_digest": MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_DIGEST,
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "registered_artifact_count": 7,
        },
        "dataset_snapshot": {
            "artifact_digest": HISTORICAL_DATASET_SNAPSHOT_DIGEST,
            "dataset_content_digest": HISTORICAL_DATASET_CONTENT_DIGEST,
            "history_snapshot": {"records": records},
        },
        "fold_manifest": {
            "artifact_digest": HISTORICAL_FOLD_MANIFEST_DIGEST,
            "folds": folds,
        },
        "checkpoint_order_manifest": {
            "artifact_digest": HISTORICAL_CHECKPOINT_ORDER_MANIFEST_DIGEST,
            "entries": orders,
        },
        "resampling_manifest": {
            "artifact_digest": HISTORICAL_RESAMPLING_MANIFEST_DIGEST,
            "children": children,
        },
        "execution_plan": {
            "artifact_digest": HISTORICAL_EXECUTION_PLAN_DIGEST,
            "formal_historical_execution_authorized": False,
            "duplicate_validation": False,
        },
        "preregistration_completion": {
            "artifact_digest": HISTORICAL_PREREGISTRATION_COMPLETION_DIGEST,
        },
    }


def _execute(*, progress_dir: Path, interrupt_after_shards: int | None = None):
    inputs = _synthetic_registered_inputs()
    return build_marginal_static_historical_execution_artifacts(
        source_contract=load_marginal_static_historical_execution_source_contract(
            SOURCE_PATH
        ),
        execution_id="a" * 64,
        git_commit="b" * 40,
        progress_dir=progress_dir,
        interrupt_after_shards=interrupt_after_shards,
        **inputs,
    )


def test_source_contract_and_bound_bytes_are_exact() -> None:
    contract = load_marginal_static_historical_execution_source_contract(SOURCE_PATH)
    verify_marginal_static_historical_execution_source_bytes(
        root_dir=ROOT,
        contract=contract,
    )
    assert contract["database_queries_during_capability"] == 0
    assert contract["completion_index_loads"] == 1
    assert contract["duplicate_validation"] is False


def test_score_issue_matches_uniform_baseline_and_preserves_sum_six() -> None:
    counts = np.full(33, 2, dtype=np.int64)
    score, probabilities = score_issue(
        counts=counts,
        training_issue_count=11,
        red_numbers=(1, 2, 3, 4, 5, 6),
    )
    assert score == pytest.approx(0.0, abs=1e-15)
    assert np.sum(probabilities) == pytest.approx(6.0, abs=1e-15)
    assert probabilities.tolist() == pytest.approx([2.0 / 11.0] * 33)


def test_interrupted_execution_restores_index_and_skips_completed_folds(
    tmp_path: Path,
) -> None:
    progress_dir = tmp_path / "progress"
    with pytest.raises(
        MarginalStaticHistoricalExecutionError,
        match="synthetic_interruption",
    ):
        _execute(progress_dir=progress_dir, interrupt_after_shards=2)

    run = _execute(progress_dir=progress_dir)

    assert run.completion_index_loads == 1
    assert run.restored_shard_count == 2
    assert run.skipped_fold_count == 512
    assert run.newly_computed_fold_count == EVALUATION_FOLD_COUNT - 512
    assert len(run.fold_shards) == 11
    assert len(run.artifacts) == 16
    assert run.completion["database_queries_during_capability"] == 0
    assert run.completion["duplicate_validation"] is False
    assert run.completion["evidence_created"] is False
    assert run.completion["next_consumer"].endswith("gate-compiler")
    assert run.resampling_output["child_count"] == 16000
    assert run.inference_aggregate["formal_historical_folds_executed"] == 2581
    assert run.branch_candidate["decision"] is None

    corrupted = progress_dir / "completion-index.json"
    corrupted.write_text("{}\n", encoding="utf-8")
    with pytest.raises(
        MarginalStaticHistoricalExecutionError,
        match="operational_index_invalid",
    ):
        _execute(progress_dir=progress_dir)


def test_resampling_kernels_are_deterministic_and_finite() -> None:
    values = np.linspace(-0.2, 0.3, 101, dtype=np.float64)
    digests = [_digest(f"seed:{index}") for index in range(6)]
    moving_first = execution_module._moving_block_means(
        data=values,
        block_length=5,
        child_digests=digests,
    )
    moving_second = execution_module._moving_block_means(
        data=values,
        block_length=5,
        child_digests=digests,
    )
    stationary_first = execution_module._stationary_means(
        data=values,
        expected_block_length=5,
        child_digests=digests,
    )
    stationary_second = execution_module._stationary_means(
        data=values,
        expected_block_length=5,
        child_digests=digests,
    )
    assert np.array_equal(moving_first, moving_second)
    assert np.array_equal(stationary_first, stationary_second)
    assert np.all(np.isfinite(moving_first))
    assert np.all(np.isfinite(stationary_first))


def test_additive_migration_revises_execution_and_adds_gate() -> None:
    source_payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source_payload.pop("manifest_digest")
    source = ControlPlaneManifest.from_dict(source_payload).to_dict(
        include_digest=False
    )
    live = deepcopy(source)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"] != MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY
    ]
    live_execution = next(
        item
        for item in live["tasks"]
        if item["task_key"] == MARGINAL_STATIC_HISTORICAL_EXECUTION_TASK_KEY
    )
    live_execution["requested_capability"] = None
    live_execution["input_artifact_digests"] = []
    live_execution["metric_contract"]["engineering_complete"] = False
    live_execution["metric_contract"]["engineering_increment_percent"] = 0
    live_execution["metric_contract"]["historical_execution_authorized"] = False
    live_execution["metric_contract"]["formal_historical_folds_executed"] = 0
    live_execution["metric_contract"]["bootstrap_children_executed"] = 0
    source_contract = load_marginal_static_historical_execution_source_contract(
        SOURCE_PATH
    )
    source_fact = (
        "m4-v2-marginal-static-historical-execution-source:"
        f"{source_contract['artifact_digest']}"
    )
    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=source,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY,),
        allowlisted_revised_task_keys=(MARGINAL_STATIC_HISTORICAL_EXECUTION_TASK_KEY,),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY]
    assert dry_run["revised_task_keys"] == [
        MARGINAL_STATIC_HISTORICAL_EXECUTION_TASK_KEY
    ]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert dry_run["unallowlisted_definition_rewrites"] == 0
    assert source_fact in migrated["facts"]["artifacts"]


def test_supervisor_capability_executes_synthetic_registered_inputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_contract = load_marginal_static_historical_execution_source_contract(
        SOURCE_PATH
    )
    for entry in source_contract["source_entries"]:
        relative = Path(entry["path"])
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    target_contract = (
        tmp_path / "configs/research-os/"
        "m4-v2-marginal-static-historical-execution-source-v1.json"
    )
    target_contract.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_PATH, target_contract)
    inputs = _synthetic_registered_inputs()
    artifact_by_type = {
        "m4_v2_marginal_static_historical_dataset_snapshot": inputs["dataset_snapshot"],
        "m4_v2_marginal_static_historical_fold_manifest": inputs["fold_manifest"],
        "m4_v2_marginal_static_historical_checkpoint_order_manifest": inputs[
            "checkpoint_order_manifest"
        ],
        "m4_v2_marginal_static_historical_resampling_manifest": inputs[
            "resampling_manifest"
        ],
        "m4_v2_marginal_static_historical_execution_plan": inputs["execution_plan"],
        "m4_v2_marginal_static_historical_preregistration_completion": inputs[
            "preregistration_completion"
        ],
    }
    original_load_registered_type = supervisor_module._load_registered_type
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_: ({}, inputs["preregistration_execution"], []),
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type",
        lambda *, artifact_type, **kwargs: (
            artifact_by_type[artifact_type]
            if artifact_type in artifact_by_type
            else original_load_registered_type(
                artifact_type=artifact_type,
                **kwargs,
            )
        ),
    )
    task = next(
        item
        for item in load_m4_manifest(MANIFEST_PATH).tasks
        if item.task_key == MARGINAL_STATIC_HISTORICAL_EXECUTION_TASK_KEY
    )
    result = M4MarginalStaticHistoricalExecutionCapability(
        repository=object(),
        root_dir=tmp_path,
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="a" * 64,
        git_commit="b" * 40,
    )
    assert len(result.registrations) == 17
    assert result.execution_artifact["formal_historical_folds_executed"] == 2581
    assert result.execution_artifact["bootstrap_children_executed"] == 16000
    assert result.execution_artifact["database_queries_during_capability"] == 0
    assert result.execution_artifact["completion_index_loads"] == 1
    assert result.execution_artifact["duplicate_validation"] is False
    assert result.execution_artifact["evidence_created"] is False
    assert result.completion_facts == (
        MARGINAL_STATIC_HISTORICAL_EXECUTION_COMPLETION_FACT,
    )

    class ReplayRepository:
        def list_mainline_execution_events(self, **_: object) -> list[dict]:
            return [
                {
                    "event_type": "completed",
                    "execution_id": "a" * 64,
                    "payload": [
                        [
                            "execution_artifact_path",
                            result.execution_artifact_path.relative_to(
                                tmp_path
                            ).as_posix(),
                        ],
                        ["registered_artifact_count", 17],
                    ],
                }
            ]

        def list_mainline_artifacts(self, **_: object) -> list[dict]:
            return [asdict(item) for item in result.registrations]

    replay = ResearchEvidenceSupervisor(
        repository=ReplayRepository(),
        root_dir=tmp_path,
        require_clean_tree=False,
    ).replay(
        task_key=MARGINAL_STATIC_HISTORICAL_EXECUTION_TASK_KEY,
        execution_id="a" * 64,
    )
    capability_replay = replay["capability_replay"]
    assert capability_replay["status"] == "REPLAY_VERIFIED"
    assert capability_replay["database_queries_during_replay"] == 0
    assert capability_replay["formal_historical_folds_replayed"] == 2581
    assert capability_replay["bootstrap_children_replayed"] == 16000
    assert capability_replay["duplicate_validation"] is False


def test_status_projects_completed_execution_to_gate_compiler() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    task = next(
        item
        for item in manifest.tasks
        if item.task_key == MARGINAL_STATIC_HISTORICAL_EXECUTION_TASK_KEY
    )
    for item in payload["tasks"]:
        if item["task_key"] == MARGINAL_STATIC_HISTORICAL_EXECUTION_TASK_KEY:
            item["status"] = "completed"
            item["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        (
            MARGINAL_STATIC_HISTORICAL_EXECUTION_COMPLETION_FACT,
            mainline_completion_fact(task=task, execution_id="f" * 64),
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": MARGINAL_STATIC_HISTORICAL_EXECUTION_TASK_KEY,
            "marginal_static_historical_execution_source_contract_digest": "1" * 64,
            "historical_completion_index_digest": "2" * 64,
            "historical_resampling_output_digest": "3" * 64,
            "historical_inference_aggregate_digest": "4" * 64,
            "historical_branch_candidate_digest": "5" * 64,
            "formal_historical_folds_executed": 2581,
            "historical_scores_computed": 2581,
            "bootstrap_children_executed": 16000,
            "fold_shard_count": 11,
            "database_queries_during_capability": 0,
            "dataset_loads": 1,
            "completion_index_loads": 1,
            "restored_shard_count": 0,
            "skipped_fold_count": 0,
            "duplicate_validation": False,
            "evidence_created": False,
            "historical_evidence": "PENDING_GATE_COMPILER",
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == (
        "MARGINAL_STATIC_HISTORICAL_MEASUREMENT_GATE_COMPILER"
    )
    assert projection["live_mainline_status"] == (
        "MARGINAL_STATIC_HISTORICAL_EXECUTION_VALIDATED_IN_MAINLINE"
    )
    execution = projection["marginal_static_historical_measurement_execution"]
    assert execution["completed"] is True
    assert execution["formal_historical_folds_executed"] == 2581
    assert execution["historical_scores_computed"] == 2581
    assert execution["bootstrap_children_executed"] == 16000
    assert execution["database_queries_during_capability"] == 0
    assert execution["completion_index_loads"] == 1
    assert execution["duplicate_validation"] is False
    gate = projection["marginal_static_historical_measurement_gate_compiler"]
    assert gate["branch_candidate_ready"] is True
    assert gate["decision_compiled"] is False
    assert projection["next_consumer"] == MARGINAL_STATIC_HISTORICAL_GATE_TASK_KEY


def test_artifact_index_and_supervisor_register_execution() -> None:
    contract = load_marginal_static_historical_execution_source_contract(SOURCE_PATH)
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["artifacts"]
    assert index[contract["artifact_digest"]]["path"] == str(
        SOURCE_PATH.relative_to(ROOT)
    )
    supervisor = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    assert MARGINAL_STATIC_HISTORICAL_EXECUTION_CAPABILITY in supervisor.capabilities
