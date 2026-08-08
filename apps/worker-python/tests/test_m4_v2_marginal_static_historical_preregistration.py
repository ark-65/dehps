from __future__ import annotations

import json
import shutil
from copy import deepcopy
from dataclasses import asdict
from datetime import date, timedelta
from itertools import pairwise
from pathlib import Path

import pytest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2 import (
    marginal_static_historical_preregistration as preregistration_module,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_historical_preregistration import (
    EVALUATION_FOLD_COUNT,
    HISTORICAL_ISSUE_COUNT,
    MARGINAL_STATIC_HISTORICAL_EXECUTION_TASK_KEY,
    MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_CAPABILITY,
    MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_COMPLETION_FACT,
    MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_SOURCE_CONTRACT_PATH,
    MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY,
    RESAMPLING_CHILD_COUNT,
    ROOT_REPLICATES,
    MarginalStaticHistoricalPreregistrationError,
    build_marginal_static_historical_preregistration_artifacts,
    load_marginal_static_historical_preregistration_source_contract,
    verify_marginal_static_historical_preregistration_source_bytes,
)
from dehps.research_os.information_theory.measurement_system_v2.migration import (
    build_additive_m4_v2_manifest,
)
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest, TaskStatus
from dehps.research_os.supervisor import (
    M4MarginalStaticHistoricalPreregistrationCapability,
    ResearchEvidenceSupervisor,
)

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "configs/research-os/m4-information-theory-evidence-v1.json"
INDEX_PATH = ROOT / "configs/research-os/m4-information-theory-artifact-index-v1.json"
SOURCE_PATH = ROOT / MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_SOURCE_CONTRACT_PATH


def _copy_source_tree(target_root: Path) -> dict:
    contract = load_marginal_static_historical_preregistration_source_contract(
        SOURCE_PATH
    )
    for entry in contract["source_entries"]:
        relative = Path(entry["path"])
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    target_contract = (
        target_root / MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_SOURCE_CONTRACT_PATH
    )
    target_contract.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_PATH, target_contract)
    return contract


def _task():
    manifest = load_m4_manifest(MANIFEST_PATH)
    return next(
        task
        for task in manifest.tasks
        if task.task_key == MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY
    )


def _parents() -> dict[str, dict]:
    return {
        "execution": {
            "artifact_type": "research_os_mainline_execution",
            "artifact_digest": (
                preregistration_module.MARGINAL_STATIC_HISTORICAL_DESIGN_EXECUTION_DIGEST
            ),
            "execution_id": (
                preregistration_module.MARGINAL_STATIC_HISTORICAL_DESIGN_EXECUTION_ID
            ),
            "task_key": (
                preregistration_module.MARGINAL_STATIC_HISTORICAL_DESIGN_TASK_KEY
            ),
            "task_digest": (
                preregistration_module.MARGINAL_STATIC_HISTORICAL_DESIGN_TASK_DIGEST
            ),
            "status": "COMPLETE",
            "completion_classification": "VALIDATED_IN_MAINLINE",
            "registered_artifact_count": 5,
            "formal_historical_folds_executed": 0,
            "historical_scores_computed": 0,
            "evidence_created": False,
        },
        "m4_v2_marginal_static_historical_dataset_boundary": {
            "artifact_type": "m4_v2_marginal_static_historical_dataset_boundary",
            "artifact_digest": preregistration_module.HISTORICAL_DATASET_BOUNDARY_DIGEST,
        },
        "m4_v2_marginal_static_historical_walk_forward_design": {
            "artifact_type": ("m4_v2_marginal_static_historical_walk_forward_design"),
            "artifact_digest": (
                preregistration_module.HISTORICAL_WALK_FORWARD_DESIGN_DIGEST
            ),
        },
        "m4_v2_marginal_static_historical_inference_design": {
            "artifact_type": "m4_v2_marginal_static_historical_inference_design",
            "artifact_digest": (
                preregistration_module.HISTORICAL_INFERENCE_DESIGN_DIGEST
            ),
        },
        "m4_v2_marginal_static_historical_measurement_design_completion": {
            "artifact_type": (
                "m4_v2_marginal_static_historical_measurement_design_completion"
            ),
            "artifact_digest": preregistration_module.HISTORICAL_DESIGN_COMPLETION_DIGEST,
        },
    }


def _interpolated_issue(index: int) -> str:
    anchors = sorted(
        (ordinal - 1, int(issue))
        for ordinal, issue in preregistration_module.EXPECTED_ORDINAL_ISSUES.items()
    )
    for (left_index, left_issue), (right_index, right_issue) in pairwise(anchors):
        if left_index <= index <= right_index:
            span = right_index - left_index
            offset = index - left_index
            return f"{left_issue + (right_issue - left_issue) * offset // span:07d}"
    raise AssertionError(index)


def _history_rows() -> tuple[tuple[str, date, tuple[int, ...]], ...]:
    first_date = date(2003, 2, 23)
    date_span = (date(2026, 7, 23) - first_date).days
    rows = []
    for index in range(HISTORICAL_ISSUE_COUNT):
        start = index % 28 + 1
        rows.append(
            (
                _interpolated_issue(index),
                first_date
                + timedelta(days=date_span * index // (HISTORICAL_ISSUE_COUNT - 1)),
                tuple(range(start, start + 6)),
            )
        )
    return tuple(rows)


def _build(*, history_rows=None, execution_id: str = "a" * 64):
    parents = _parents()
    return build_marginal_static_historical_preregistration_artifacts(
        source_contract=(
            load_marginal_static_historical_preregistration_source_contract(SOURCE_PATH)
        ),
        historical_design_execution=parents["execution"],
        dataset_boundary=parents["m4_v2_marginal_static_historical_dataset_boundary"],
        walk_forward_design=parents[
            "m4_v2_marginal_static_historical_walk_forward_design"
        ],
        inference_design=parents["m4_v2_marginal_static_historical_inference_design"],
        design_completion=parents[
            "m4_v2_marginal_static_historical_measurement_design_completion"
        ],
        history_rows=_history_rows() if history_rows is None else history_rows,
        execution_id=execution_id,
        git_commit="b" * 40,
    )


@pytest.fixture(scope="module")
def preregistration_run():
    return _build()


def test_source_contract_detects_byte_and_contract_tamper(tmp_path: Path) -> None:
    contract = _copy_source_tree(tmp_path)
    verify_marginal_static_historical_preregistration_source_bytes(
        root_dir=tmp_path,
        contract=contract,
    )
    source_path = tmp_path / contract["source_entries"][0]["path"]
    source_path.write_bytes(source_path.read_bytes() + b"\n# tampered\n")
    with pytest.raises(
        MarginalStaticHistoricalPreregistrationError, match="source_modified"
    ):
        verify_marginal_static_historical_preregistration_source_bytes(
            root_dir=tmp_path,
            contract=contract,
        )

    drifted = deepcopy(contract)
    drifted["frozen_contract"]["formal_historical_execution_authorized"] = True
    drifted["artifact_digest"] = "0" * 64
    path = tmp_path / "drifted.json"
    path.write_text(json.dumps(drifted), encoding="utf-8")
    with pytest.raises(
        MarginalStaticHistoricalPreregistrationError, match="source_invalid"
    ):
        load_marginal_static_historical_preregistration_source_contract(path)


def test_preregistration_freezes_content_folds_resampling_and_fast_resume(
    preregistration_run,
) -> None:
    run = preregistration_run
    snapshot = run.dataset_snapshot
    assert snapshot["historical_issue_count"] == HISTORICAL_ISSUE_COUNT
    assert snapshot["database_queries_during_capability"] == 1
    assert snapshot["historical_rows_content_hashed"] == HISTORICAL_ISSUE_COUNT
    assert snapshot["historical_outcomes_hashed"] is True
    assert (
        snapshot["historical_outcomes_exposed_to_research_or_decision_logic"] is False
    )
    assert snapshot["legacy_identity_role"] == "lineage_only_not_content_digest"
    assert run.fold_manifest["fold_count"] == EVALUATION_FOLD_COUNT
    assert (
        len({item["fold_digest"] for item in run.fold_manifest["folds"]})
        == EVALUATION_FOLD_COUNT
    )
    assert run.checkpoint_order_manifest["entry_count"] == EVALUATION_FOLD_COUNT
    assert run.resampling_manifest["root_replicate_count"] == ROOT_REPLICATES
    assert run.resampling_manifest["child_count"] == RESAMPLING_CHILD_COUNT
    assert (
        len({item["child_digest"] for item in run.resampling_manifest["children"]})
        == RESAMPLING_CHILD_COUNT
    )
    execution = run.execution_plan["execution"]
    assert execution["dataset_loads"] == 1
    assert execution["database_reads_per_fold"] == 0
    assert execution["database_writes_per_fold"] == 0
    assert execution["completion_index_loads"] == 1
    assert execution["completed_fold_action"].startswith("skip_verified")
    assert execution["duplicate_validation"] is False
    assert run.completion["formal_historical_folds_executed"] == 0
    assert run.completion["bootstrap_children_executed"] == 0
    assert run.completion["evidence_created"] is False
    assert run.completion["next_consumer"] == (
        MARGINAL_STATIC_HISTORICAL_EXECUTION_TASK_KEY
    )


def test_dataset_content_digest_changes_with_a_red_outcome(
    preregistration_run,
) -> None:
    rows = list(_history_rows())
    issue, draw_date, _ = rows[1000]
    rows[1000] = (issue, draw_date, (1, 2, 3, 4, 5, 33))
    changed = _build(history_rows=rows, execution_id="c" * 64)
    assert (
        changed.dataset_snapshot["dataset_content_digest"]
        != (preregistration_run.dataset_snapshot["dataset_content_digest"])
    )
    assert (
        changed.fold_manifest["artifact_digest"]
        != (preregistration_run.fold_manifest["artifact_digest"])
    )


def test_dataset_rejects_duplicate_reds_and_boundary_drift() -> None:
    rows = list(_history_rows())
    issue, draw_date, _ = rows[1]
    rows[1] = (issue, draw_date, (1, 1, 2, 3, 4, 5))
    with pytest.raises(
        MarginalStaticHistoricalPreregistrationError, match="dataset_invalid"
    ):
        _build(history_rows=rows)

    with pytest.raises(
        MarginalStaticHistoricalPreregistrationError, match="dataset_boundary_invalid"
    ):
        _build(history_rows=_history_rows()[:-1])


def test_capability_and_replay_use_snapshot_without_requery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _copy_source_tree(tmp_path)
    task = _task()
    parents = _parents()
    original_load_registered_type = supervisor_module._load_registered_type

    def load_execution(**_):
        return {}, parents["execution"], "design-registrations"

    def load_registered_type(**kwargs):
        if kwargs["registrations"] == "design-registrations":
            return parents[kwargs["artifact_type"]]
        return original_load_registered_type(**kwargs)

    query_calls = 0

    def load_rows():
        nonlocal query_calls
        query_calls += 1
        return _history_rows()

    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        load_execution,
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type",
        load_registered_type,
    )
    monkeypatch.setattr(supervisor_module, "load_canonical_historical_rows", load_rows)
    result = M4MarginalStaticHistoricalPreregistrationCapability(
        repository=object(),
        root_dir=tmp_path,
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="d" * 64,
        git_commit="e" * 40,
    )
    execution = result.execution_artifact
    assert query_calls == 1
    assert result.completion_facts == (
        MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_COMPLETION_FACT,
    )
    assert len(result.registrations) == 7
    assert execution["historical_rows_content_hashed"] == HISTORICAL_ISSUE_COUNT
    assert execution["formal_historical_folds_executed"] == 0
    assert execution["bootstrap_children_executed"] == 0
    assert execution["duplicate_validation"] is False
    assert execution["evidence_created"] is False

    class ReplayRepository:
        def list_mainline_execution_events(self, **_: object) -> list[dict]:
            return [
                {
                    "event_type": "completed",
                    "execution_id": "d" * 64,
                    "payload": [
                        [
                            "execution_artifact_path",
                            result.execution_artifact_path.relative_to(
                                tmp_path
                            ).as_posix(),
                        ],
                        ["registered_artifact_count", 7],
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
        task_key=MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY,
        execution_id="d" * 64,
    )
    assert query_calls == 1
    capability_replay = replay["capability_replay"]
    assert capability_replay["status"] == "REPLAY_VERIFIED"
    assert capability_replay["preregistration_only"] is True
    assert capability_replay["database_queries_during_replay"] == 0
    assert capability_replay["formal_historical_folds_executed"] == 0
    assert capability_replay["duplicate_validation"] is False


def test_additive_migration_revises_one_task_and_adds_execution() -> None:
    source = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source.pop("manifest_digest")
    normalized = ControlPlaneManifest.from_dict(source).to_dict(include_digest=False)
    live = deepcopy(normalized)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"] != MARGINAL_STATIC_HISTORICAL_EXECUTION_TASK_KEY
    ]
    live_preregistration = next(
        item
        for item in live["tasks"]
        if item["task_key"] == MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY
    )
    live_preregistration.pop("requested_capability")
    live_preregistration.pop("input_artifact_digests")
    live_preregistration["metric_contract"]["engineering_complete"] = False
    live_preregistration["metric_contract"]["engineering_increment_percent"] = 0
    source_fact = next(
        fact
        for fact in live["facts"]["artifacts"]
        if fact.startswith("m4-v2-marginal-static-historical-preregistration-source:")
    )
    live["facts"]["artifacts"].remove(source_fact)

    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=normalized,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(MARGINAL_STATIC_HISTORICAL_EXECUTION_TASK_KEY,),
        allowlisted_revised_task_keys=(
            MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY,
        ),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )
    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [MARGINAL_STATIC_HISTORICAL_EXECUTION_TASK_KEY]
    assert dry_run["revised_task_keys"] == [
        MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY
    ]
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert dry_run["unallowlisted_definition_rewrites"] == 0
    assert source_fact in migrated["facts"]["artifacts"]


def test_status_projects_preregistration_completion_to_execution() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    task = next(
        task
        for task in manifest.tasks
        if task.task_key == MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY
    )
    for item in payload["tasks"]:
        if item["task_key"] == MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY:
            item["status"] = "completed"
            item["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        (
            MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_COMPLETION_FACT,
            mainline_completion_fact(task=task, execution_id="f" * 64),
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": (MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY),
            "execution_artifact_digest": "1" * 64,
            "registered_artifact_count": 7,
            "historical_dataset_snapshot_digest": "2" * 64,
            "historical_dataset_content_digest": "3" * 64,
            "historical_fold_manifest_digest": "4" * 64,
            "historical_checkpoint_order_manifest_digest": "5" * 64,
            "historical_resampling_manifest_digest": "6" * 64,
            "historical_execution_plan_digest": "7" * 64,
            "historical_preregistration_completion_digest": "8" * 64,
            "historical_issue_count": 3481,
            "fold_identity_count": 2581,
            "checkpoint_order_entry_count": 2581,
            "root_seed_count": 2000,
            "resampling_scheme_count": 8,
            "resampling_child_count": 16000,
            "fold_shard_count": 11,
            "database_queries_during_capability": 1,
            "historical_rows_content_hashed": 3481,
            "historical_outcomes_hashed": True,
            "historical_outcomes_read": True,
            "historical_outcomes_exposed_to_research_or_decision_logic": False,
            "historical_scores_computed": 0,
            "formal_historical_folds_executed": 0,
            "bootstrap_children_executed": 0,
            "historical_evidence": "NOT_RUN",
        },
    )
    projection = status["measurement_system_v2"]
    assert projection["phase"] == "MARGINAL_STATIC_HISTORICAL_MEASUREMENT_EXECUTION"
    assert projection["live_mainline_status"] == (
        "MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_VALIDATED_IN_MAINLINE"
    )
    preregistration = projection[
        "marginal_static_historical_measurement_preregistration"
    ]
    assert preregistration["completed"] is True
    assert preregistration["historical_rows_content_hashed"] == 3481
    assert preregistration["historical_outcomes_hashed"] is True
    assert (
        preregistration["historical_outcomes_exposed_to_research_or_decision_logic"]
        is False
    )
    assert preregistration["historical_scores_computed"] == 0
    assert preregistration["formal_historical_folds_executed"] == 0
    assert preregistration["duplicate_validation"] is False
    assert projection["next_consumer"] == MARGINAL_STATIC_HISTORICAL_EXECUTION_TASK_KEY


def test_artifact_index_and_supervisor_register_preregistration() -> None:
    source = load_marginal_static_historical_preregistration_source_contract(
        SOURCE_PATH
    )
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))["artifacts"]
    entry = index[source["artifact_digest"]]
    assert entry["path"] == str(SOURCE_PATH.relative_to(ROOT))
    assert entry["identity_field"] == "artifact_digest"
    supervisor = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    assert MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_CAPABILITY in (
        supervisor.capabilities
    )


def test_latest_v2_summary_prefers_completed_preregistration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Resolution:
        task_key = MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY
        status = TaskStatus.COMPLETED

    execution = {
        "artifact_digest": "1" * 64,
        "historical_dataset_snapshot_digest": "2" * 64,
        "historical_dataset_content_digest": "3" * 64,
        "historical_fold_manifest_digest": "4" * 64,
        "historical_checkpoint_order_manifest_digest": "5" * 64,
        "historical_resampling_manifest_digest": "6" * 64,
        "historical_execution_plan_digest": "7" * 64,
        "historical_preregistration_completion_digest": "8" * 64,
        "historical_scores_computed": 0,
        "formal_historical_folds_executed": 0,
        "bootstrap_children_executed": 0,
        "statistical_results_read": False,
        "evidence_created": False,
        "duplicate_validation": False,
    }
    event = {
        "payload": [
            ["execution_artifact_digest", "1" * 64],
            ["registered_artifact_count", 7],
            ["actual_fold_count", 0],
        ]
    }
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_: (event, execution, ()),
    )
    summary = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )._latest_completed_v2_summary(
        type("Snapshot", (), {"resolutions": [Resolution()]})()
    )
    assert summary is not None
    assert summary["execution_task_key"] == (
        MARGINAL_STATIC_HISTORICAL_PREREGISTRATION_TASK_KEY
    )
    assert summary["historical_dataset_content_digest"] == "3" * 64
    assert summary["historical_execution_plan_digest"] == "7" * 64
    assert summary["registered_artifact_count"] == 7
