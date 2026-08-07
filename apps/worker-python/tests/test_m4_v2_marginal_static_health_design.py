from __future__ import annotations

import json
import shutil
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

import pytest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_fixtures import (
    FIXTURE_ORDER,
    MARGINAL_STATIC_FIXTURE_FREEZE_COMPLETION_FACT,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_health_design import (
    MARGINAL_STATIC_HEALTH_DESIGN_CAPABILITY,
    MARGINAL_STATIC_HEALTH_DESIGN_COMPLETION_FACT,
    MARGINAL_STATIC_HEALTH_DESIGN_SOURCE_CONTRACT_PATH,
    MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY,
    MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY,
    MarginalStaticHealthDesignError,
    build_marginal_static_health_design_artifacts,
    load_marginal_static_health_design_source_contract,
    verify_marginal_static_health_design_source_bytes,
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
    M4MarginalStaticHealthDesignCapability,
    ResearchEvidenceSupervisor,
)

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "configs/research-os/m4-information-theory-evidence-v1.json"
SOURCE_CONTRACT_PATH = ROOT / MARGINAL_STATIC_HEALTH_DESIGN_SOURCE_CONTRACT_PATH


def _copy_source_contract_tree(target_root: Path) -> dict:
    contract = load_marginal_static_health_design_source_contract(SOURCE_CONTRACT_PATH)
    for entry in contract["source_entries"]:
        relative = Path(entry["path"])
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    target_contract = target_root / MARGINAL_STATIC_HEALTH_DESIGN_SOURCE_CONTRACT_PATH
    target_contract.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_CONTRACT_PATH, target_contract)
    return contract


def _inputs() -> tuple[dict, tuple[dict, ...], dict, dict]:
    source = load_marginal_static_health_design_source_contract(SOURCE_CONTRACT_PATH)
    fixtures = tuple(
        {
            "artifact_type": "m4_v2_marginal_static_measurement_fixture",
            "artifact_digest": str(index) * 64,
            "fixture_id": fixture_id,
        }
        for index, fixture_id in enumerate(FIXTURE_ORDER, start=1)
    )
    fixture_digests = [item["artifact_digest"] for item in fixtures]
    bundle = {
        "artifact_type": "m4_v2_marginal_static_fixture_bundle",
        "artifact_digest": "5" * 64,
        "fixture_digests": fixture_digests,
        "sampled_workload_status": "NOT_FROZEN",
    }
    completion = {
        "artifact_type": "m4_v2_marginal_static_fixture_freeze_completion",
        "artifact_digest": "6" * 64,
        "completion_fact": MARGINAL_STATIC_FIXTURE_FREEZE_COMPLETION_FACT,
        "fixture_bundle_digest": bundle["artifact_digest"],
        "generated_issues": 0,
        "synthetic_replicates": 0,
        "historical_outcomes_read": False,
    }
    return source, fixtures, bundle, completion


def _build_run() -> object:
    source, fixtures, bundle, completion = _inputs()
    return build_marginal_static_health_design_artifacts(
        source_contract=source,
        fixture_execution_artifact_digest="7" * 64,
        fixture_contracts=fixtures,
        fixture_bundle=bundle,
        fixture_completion=completion,
        execution_id="8" * 64,
        git_commit="9" * 40,
    )


def test_health_design_freezes_smaller_batched_zero_work_program() -> None:
    first = _build_run()
    second = _build_run()

    assert first == second
    assert len(first.artifacts) == 3
    workload = first.workload["workload"]
    assert workload["total_replicates"] == 7168
    assert workload["total_generated_issues_if_executed"] == 15_920_128
    assert workload["total_outer_evaluation_issues_if_executed"] == 9_468_928
    assert workload["execution_shard_size"] == 64
    assert workload["execution_shards"] == 112
    assert workload["comparison_to_legacy_p2_6_1"]["legacy_replicates"] == 31_000
    assert workload["comparison_to_legacy_p2_6_1"]["legacy_probe_fits_reused"] is False
    assert first.inference["inference"]["bootstrap_replicates"] == 511
    assert first.inference["inference"]["sensitivity_block_sizes"] == [3, 8, 13]
    assert first.completion["generated_issues"] == 0
    assert first.completion["synthetic_replicates"] == 0
    assert first.completion["bootstrap_replicates_executed"] == 0
    assert first.completion["historical_outcomes_read"] is False
    assert first.completion["evidence_created"] is False
    assert (
        first.completion["next_consumer"] == MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY
    )


def test_health_design_fails_closed_on_contract_or_fixture_lineage_drift() -> None:
    source, fixtures, bundle, completion = _inputs()
    drifted_source = deepcopy(source)
    drifted_source["frozen_contract"]["workload"]["total_replicates"] = 7167
    with pytest.raises(MarginalStaticHealthDesignError, match="contract_invalid"):
        build_marginal_static_health_design_artifacts(
            source_contract=drifted_source,
            fixture_execution_artifact_digest="7" * 64,
            fixture_contracts=fixtures,
            fixture_bundle=bundle,
            fixture_completion=completion,
            execution_id="8" * 64,
            git_commit="9" * 40,
        )

    drifted_bundle = deepcopy(bundle)
    drifted_bundle["fixture_digests"] = list(reversed(bundle["fixture_digests"]))
    with pytest.raises(MarginalStaticHealthDesignError, match="lineage_invalid"):
        build_marginal_static_health_design_artifacts(
            source_contract=source,
            fixture_execution_artifact_digest="7" * 64,
            fixture_contracts=fixtures,
            fixture_bundle=drifted_bundle,
            fixture_completion=completion,
            execution_id="8" * 64,
            git_commit="9" * 40,
        )


def test_health_design_source_detects_byte_and_contract_tamper(
    tmp_path: Path,
) -> None:
    contract = _copy_source_contract_tree(tmp_path)
    verify_marginal_static_health_design_source_bytes(
        root_dir=tmp_path,
        contract=contract,
    )
    source_path = tmp_path / contract["source_entries"][0]["path"]
    source_path.write_bytes(source_path.read_bytes() + b"\n# tampered\n")
    with pytest.raises(MarginalStaticHealthDesignError, match="source_modified"):
        verify_marginal_static_health_design_source_bytes(
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
    with pytest.raises(MarginalStaticHealthDesignError, match="source_invalid"):
        load_marginal_static_health_design_source_contract(drift_path)


def test_health_design_capability_materializes_four_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _copy_source_contract_tree(tmp_path)
    manifest = load_m4_manifest(MANIFEST_PATH)
    task = next(
        item
        for item in manifest.tasks
        if item.task_key == MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY
    )
    _, fixture_templates, bundle, completion = _inputs()
    expected = task.input_artifact_digests
    fixtures = tuple(
        {**item, "artifact_digest": expected[index]}
        for index, item in enumerate(fixture_templates, start=2)
    )
    bundle["artifact_digest"] = expected[6]
    bundle["fixture_digests"] = [item["artifact_digest"] for item in fixtures]
    completion["artifact_digest"] = expected[7]
    completion["fixture_bundle_digest"] = expected[6]
    fixture_execution = {
        "execution_id": "a" * 64,
        "artifact_digest": expected[1],
        "completion_fact": MARGINAL_STATIC_FIXTURE_FREEZE_COMPLETION_FACT,
        "fixture_count": 4,
        "generated_issues": 0,
        "synthetic_replicates": 0,
        "historical_outcomes_read": False,
        "evidence_created": False,
        "duplicate_raw_replay": False,
        "routine_physical_checkpoint_scan": False,
    }

    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_: ({}, fixture_execution, "fixture-registrations"),
    )

    def fake_registered_type_group(**kwargs: object) -> tuple[dict, ...]:
        assert (
            kwargs["artifact_type"]
            == "m4_v2_marginal_static_measurement_fixture"
        )
        return tuple(reversed(fixtures))

    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type_group",
        fake_registered_type_group,
    )

    def fake_registered_type(**kwargs: object) -> dict:
        return {
            "m4_v2_marginal_static_fixture_bundle": bundle,
            "m4_v2_marginal_static_fixture_freeze_completion": completion,
        }[kwargs["artifact_type"]]

    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type",
        fake_registered_type,
    )
    result = M4MarginalStaticHealthDesignCapability(
        repository=object(),
        root_dir=tmp_path,
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="b" * 64,
        git_commit="c" * 40,
    )

    assert result.completion_facts == (MARGINAL_STATIC_HEALTH_DESIGN_COMPLETION_FACT,)
    assert len(result.registrations) == 4
    assert result.execution_artifact["registered_artifact_count"] == 4
    assert result.execution_artifact["planned_total_replicates"] == 7168
    assert result.execution_artifact["planned_execution_shards"] == 112
    assert result.execution_artifact["generated_issues"] == 0
    assert result.execution_artifact["synthetic_replicates"] == 0
    assert result.execution_artifact["duplicate_raw_replay"] is False
    assert result.execution_artifact["routine_physical_checkpoint_scan"] is False

    class ReplayRepository:
        def list_mainline_execution_events(self, **_: object) -> list[dict]:
            return [
                {
                    "event_type": "completed",
                    "execution_id": "b" * 64,
                    "payload": [
                        [
                            "execution_artifact_path",
                            result.execution_artifact_path.relative_to(
                                tmp_path
                            ).as_posix(),
                        ],
                        ["registered_artifact_count", 4],
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
        task_key=MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY,
        execution_id="b" * 64,
    )
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["registered_artifact_count"] == 4
    assert replay["capability_replay"]["same_registered_content"] is True
    assert replay["capability_replay"]["generated_issues"] == 0


def test_additive_health_design_migration_preserves_live_truth() -> None:
    source = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source.pop("manifest_digest")
    normalized = ControlPlaneManifest.from_dict(source).to_dict(include_digest=False)
    live = deepcopy(normalized)
    live["tasks"] = [
        item
        for item in live["tasks"]
        if item["task_key"] != MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY
    ]
    live_design = next(
        item
        for item in live["tasks"]
        if item["task_key"] == MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY
    )
    live_design.pop("requested_capability")
    live_design.pop("input_artifact_digests")
    live_design["dependencies"] = live_design["dependencies"][:2]
    live_design["metric_contract"] = {
        "engineering_complete": False,
        "engineering_increment_percent": 0,
        "evidence_complete": False,
        "evidence_increment_percent": 0,
        "phase": "M4-V2-MARGINAL-STATIC-HEALTH-DESIGN",
        "scope": (
            "freeze_sample_sizes_seed_domains_acceptance_thresholds_and_"
            "compact_replicate_resume_contract_without_execution"
        ),
        "reason": (
            "the four exact fixtures must be paired with a separately "
            "preregistered false-positive, bias, coverage, power, and MDE "
            "design before sampling"
        ),
        "formal_execution_allowed": False,
        "synthetic_replicates": 0,
        "generated_issues": 0,
        "historical_outcomes_read": False,
        "statistical_results_read": False,
        "production_action": "none",
    }
    source_fact = next(
        item
        for item in live["facts"]["artifacts"]
        if item.startswith("m4-v2-marginal-static-health-design-source:")
    )
    live["facts"]["artifacts"].remove(source_fact)

    migrated, dry_run = build_additive_m4_v2_manifest(
        live_payload=live,
        source_payload=normalized,
        allowlisted_new_goal_keys=(),
        allowlisted_new_task_keys=(MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY,),
        allowlisted_revised_task_keys=(MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY,),
        add_artifact_facts=(source_fact,),
        add_external_events=(),
    )

    assert dry_run["status"] == "VERIFIED"
    assert dry_run["new_task_keys"] == [MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY]
    assert dry_run["revised_task_keys"] == [MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY]
    assert dry_run["existing_task_deletions"] == 0
    assert dry_run["existing_state_regressions"] == 0
    assert dry_run["existing_fact_deletions"] == 0
    assert source_fact in migrated["facts"]["artifacts"]


def test_health_design_completion_projects_only_execution_as_next() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    payload = manifest.to_dict(include_digest=False)
    health_task = next(
        item
        for item in manifest.tasks
        if item.task_key == MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY
    )
    for task in payload["tasks"]:
        if task["task_key"] == MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY:
            task["status"] = "completed"
            task["completion_classification"] = "COMPLETE"
    payload["facts"]["artifacts"].extend(
        (
            MARGINAL_STATIC_FIXTURE_FREEZE_COMPLETION_FACT,
            MARGINAL_STATIC_HEALTH_DESIGN_COMPLETION_FACT,
            mainline_completion_fact(task=health_task, execution_id="d" * 64),
        )
    )
    completed = ControlPlaneManifest.from_dict(payload)
    status = build_m4_status(
        completed,
        measurement_v2_execution={
            "execution_task_key": MARGINAL_STATIC_HEALTH_DESIGN_TASK_KEY,
            "execution_artifact_digest": "e" * 64,
            "registered_artifact_count": 4,
            "actual_fold_count": 0,
            "fixture_count": 4,
            "positive_fixture_count": 1,
            "negative_fixture_count": 3,
            "runtime_state": (
                "issue_count plus ordered signed_int64[33] number-event counts"
            ),
            "estimator_id": "EXPANDING_LEGAL_MARGINAL_ALPHA_1",
            "identifiability_preflight_status": "PASS",
            "marginal_static_health_workload_digest": "a" * 64,
            "marginal_static_health_inference_digest": "b" * 64,
            "planned_total_replicates": 7168,
            "planned_total_generated_issues": 15_920_128,
            "planned_total_outer_evaluation_issues": 9_468_928,
            "planned_execution_shards": 112,
            "execution_shard_size": 64,
        },
    )
    projection = status["measurement_system_v2"]

    assert projection["phase"] == "MARGINAL_STATIC_HEALTH_EXECUTION"
    assert projection["live_mainline_status"] == (
        "MARGINAL_STATIC_HEALTH_DESIGN_VALIDATED_IN_MAINLINE"
    )
    assert projection["next_consumer"] == MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY
    design = projection["marginal_static_health_design"]
    assert design["completed"] is True
    assert design["planned_total_replicates"] == 7168
    assert design["planned_execution_shards"] == 112
    assert design["sampled_workload_status"] == "FROZEN_NOT_EXECUTED"
    assert design["duplicate_raw_replay"] is False
    assert design["routine_physical_checkpoint_scan"] is False
    assert design["evidence_progress_increment"] == 0


def test_supervisor_registers_marginal_static_health_design_capability() -> None:
    supervisor = ResearchEvidenceSupervisor(
        repository=object(),
        require_clean_tree=False,
    )
    assert MARGINAL_STATIC_HEALTH_DESIGN_CAPABILITY in supervisor.capabilities
