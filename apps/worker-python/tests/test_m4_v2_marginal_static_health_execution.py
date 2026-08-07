from __future__ import annotations

import hashlib
import json
import math
import shutil
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from dataclasses import asdict
from math import comb
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from dehps.research_os import supervisor as supervisor_module
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_fixtures import (
    J1_FIXTURE_ID,
    T1_FIXTURE_ID,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_health_decision import (
    MARGINAL_STATIC_HEALTH_DECISION_CAPABILITY,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_health_design import (
    MARGINAL_STATIC_HEALTH_DESIGN_COMPLETION_FACT,
)
from dehps.research_os.information_theory.measurement_system_v2.marginal_static_health_execution import (
    BOOTSTRAP_REPLICATES,
    IS4_WEIGHTS,
    LEGAL_COMBINATION_COUNT,
    MARGINAL_STATIC_HEALTH_DECISION_TASK_KEY,
    MARGINAL_STATIC_HEALTH_EXECUTION_CAPABILITY,
    MARGINAL_STATIC_HEALTH_EXECUTION_COMPLETION_FACT,
    MARGINAL_STATIC_HEALTH_EXECUTION_SOURCE_CONTRACT_PATH,
    MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY,
    MARGINAL_STATIC_HEALTH_PROGRESS_PATH,
    REPLICATES_PER_CELL,
    T1_PARTITION,
    TOTAL_CELLS,
    TOTAL_GENERATED_ISSUES,
    TOTAL_OUTER_EVALUATION_ISSUES,
    TOTAL_REPLICATES,
    HealthExecutionRun,
    MarginalStaticHealthExecutionError,
    ReplicateSpec,
    _group_count_masses,
    _initialize_worker,
    _moving_block_inference,
    _persist_summary_and_build_entry,
    append_completion_entries,
    build_health_cells,
    build_replicate_specs,
    load_completion_index,
    load_marginal_static_health_execution_source_contract,
    run_replicate,
    verify_marginal_static_health_execution_source_bytes,
)
from dehps.research_os.information_theory.progress import load_m4_manifest
from dehps.research_os.supervisor import (
    M4MarginalStaticHealthExecutionCapability,
    ResearchEvidenceSupervisor,
)

ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = ROOT / "configs/research-os/m4-information-theory-evidence-v1.json"
DESIGN_SOURCE_PATH = (
    ROOT / "configs/research-os/m4-v2-marginal-static-health-design-source-v1.json"
)
SOURCE_CONTRACT_PATH = ROOT / MARGINAL_STATIC_HEALTH_EXECUTION_SOURCE_CONTRACT_PATH


def _workload() -> dict:
    return json.loads(DESIGN_SOURCE_PATH.read_text(encoding="utf-8"))[
        "frozen_contract"
    ]["workload"]


def _source() -> dict:
    return load_marginal_static_health_execution_source_contract(SOURCE_CONTRACT_PATH)


def _copy_source_tree(target_root: Path) -> None:
    contract = _source()
    for entry in contract["source_entries"]:
        relative = Path(entry["path"])
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    contract_target = (
        target_root / MARGINAL_STATIC_HEALTH_EXECUTION_SOURCE_CONTRACT_PATH
    )
    contract_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_CONTRACT_PATH, contract_target)


def _task():
    manifest = load_m4_manifest(MANIFEST_PATH)
    return next(
        item
        for item in manifest.tasks
        if item.task_key == MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY
    )


def test_source_contract_and_exact_work_partition_are_frozen() -> None:
    source = _source()
    verify_marginal_static_health_execution_source_bytes(
        root_dir=ROOT,
        contract=source,
    )
    cells = build_health_cells(_workload())
    specs = build_replicate_specs(
        workload=_workload(),
        source_contract_digest=source["artifact_digest"],
    )

    assert len(cells) == TOTAL_CELLS == 14
    assert len(specs) == TOTAL_REPLICATES == 7_168
    assert len({item.replicate_digest for item in specs}) == TOTAL_REPLICATES
    assert sum(cell.sequence_issues for cell in cells) * REPLICATES_PER_CELL == (
        TOTAL_GENERATED_ISSUES
    )
    assert sum(cell.evaluation_issues for cell in cells) * REPLICATES_PER_CELL == (
        TOTAL_OUTER_EVALUATION_ISSUES
    )
    assert source["frozen_contract"]["duplicate_raw_replay"] == "forbidden"
    assert source["frozen_contract"]["routine_physical_checkpoint_scan"] == (
        "forbidden"
    )


def test_exact_t1_and_j1_generators_preserve_frozen_marginals() -> None:
    t1_masses = np.asarray(
        [comb(6, k) * comb(27, 6 - k) * 2**k / T1_PARTITION for k in range(7)]
    )
    assert math.fsum(t1_masses) == pytest.approx(1.0, abs=1e-15)
    assert sum(comb(6, k) * comb(27, 6 - k) * 2**k for k in range(7)) == (T1_PARTITION)

    base = np.asarray(
        [comb(16, k) * comb(17, 6 - k) / LEGAL_COMBINATION_COUNT for k in range(7)]
    )
    for sign in (-1, 1):
        transition = np.asarray(
            [base[k] * (1.0 + sign * 0.5 * float(IS4_WEIGHTS[k])) for k in range(7)]
        )
        assert math.fsum(transition) == pytest.approx(1.0, abs=1e-15)
        assert float(np.dot(np.arange(7), transition)) == pytest.approx(
            32 / 11,
            abs=1e-15,
        )

    uniform = _group_count_masses(16, 17, 1.0)
    assert math.fsum(uniform) == pytest.approx(1.0, abs=1e-15)
    assert float(np.dot(np.arange(7), uniform)) == pytest.approx(32 / 11)


@pytest.mark.parametrize("fixture_id", [T1_FIXTURE_ID, J1_FIXTURE_ID])
def test_long_stateful_replicates_are_exact_deterministic_and_compact(
    fixture_id: str,
) -> None:
    source = _source()
    cell = next(
        item
        for item in build_health_cells(_workload())
        if item.fixture_id == fixture_id and item.scale_id == "HISTORICAL_2581"
    )
    spec = ReplicateSpec(
        cell=cell,
        replicate_index=17,
        source_contract_digest=source["artifact_digest"],
    )

    first = run_replicate(spec)
    second = run_replicate(spec)

    assert first == second
    assert first["legal_draw_count"] == 3_481
    assert first["illegal_draw_count"] == 0
    assert first["database_reads_during_replicate"] == 0
    assert first["database_writes_during_replicate"] == 0
    assert first["csv_materialized"] is False
    assert first["raw_draws_retained"] is False
    assert set(first["block_inference"]) == {"3", "5", "8", "13"}


def test_process_executor_preserves_worker_independent_identities() -> None:
    source = _source()
    specs = [
        ReplicateSpec(
            cell=cell,
            replicate_index=index,
            source_contract_digest=source["artifact_digest"],
        )
        for index, cell in enumerate(
            item
            for item in build_health_cells(_workload())
            if item.scale_id == "HISTORICAL_2581"
            and item.fixture_id in {T1_FIXTURE_ID, J1_FIXTURE_ID}
        )
    ]
    expected = [run_replicate(item) for item in specs]

    with ProcessPoolExecutor(max_workers=2, initializer=_initialize_worker) as pool:
        actual = list(pool.map(run_replicate, specs, chunksize=1))

    assert actual == expected


def test_bootstrap_matches_the_frozen_centered_circular_reference() -> None:
    values = np.asarray([0.4, -0.1, 0.2, 0.8, -0.3, 0.5, 0.1], dtype=np.float64)
    seed_digest = "a" * 64
    actual = _moving_block_inference(values, block_size=3, seed_digest=seed_digest)

    observed = float(np.mean(values))
    centered = values - observed
    extended = np.concatenate((centered, centered[:2]))
    cumulative = np.concatenate(([0.0], np.cumsum(extended)))
    starts = np.arange(values.size)
    block_sums = cumulative[starts + 3] - cumulative[starts]
    rng = np.random.Generator(np.random.PCG64DXSM(int(seed_digest, 16)))
    chosen = rng.integers(0, values.size, size=(BOOTSTRAP_REPLICATES, 3))
    deviations = (
        block_sums[chosen[:, 0]]
        + block_sums[chosen[:, 1]]
        + (cumulative[chosen[:, 2] + 1] - cumulative[chosen[:, 2]])
    ) / values.size
    q025, q975 = np.quantile(deviations, [0.025, 0.975], method="linear")

    assert actual["interval_lower"] == observed - q975
    assert actual["interval_upper"] == observed - q025
    assert (
        actual["upper_tail_p"]
        == (1 + int(np.count_nonzero(deviations >= observed))) / 512
    )


def test_compact_index_resumes_by_digest_and_fails_closed_on_tamper(
    tmp_path: Path,
) -> None:
    source = _source()
    spec = build_replicate_specs(
        workload=_workload(),
        source_contract_digest=source["artifact_digest"],
    )[0]
    summary = run_replicate(spec)
    checkpoint_root = tmp_path / "task" / "checkpoints"
    context_digest = "b" * 64
    entry = _persist_summary_and_build_entry(
        checkpoint_root=checkpoint_root,
        context_digest=context_digest,
        spec=spec,
        summary=summary,
    )
    index_path = checkpoint_root / "completion-index.jsonl"
    append_completion_entries(index_path, (entry,))

    loaded = load_completion_index(
        index_path,
        context_digest=context_digest,
        expected_specs={spec.replicate_digest: spec},
    )
    assert tuple(loaded) == (spec.replicate_digest,)
    assert loaded[spec.replicate_digest]["summary"] == summary

    tampered = deepcopy(entry)
    tampered["summary"]["observed_endpoint_bits_per_issue"] += 1.0
    index_path.write_text(json.dumps(tampered) + "\n", encoding="utf-8")
    with pytest.raises(MarginalStaticHealthExecutionError, match="identity_changed"):
        load_completion_index(
            index_path,
            context_digest=context_digest,
            expected_specs={spec.replicate_digest: spec},
        )


def test_execution_capability_materializes_only_compact_registered_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _copy_source_tree(tmp_path)
    task = _task()
    expected = task.input_artifact_digests
    workload = {
        "artifact_type": "m4_v2_marginal_static_health_workload",
        "artifact_digest": expected[2],
        "workload": _workload(),
    }
    inference = {
        "artifact_type": "m4_v2_marginal_static_health_inference",
        "artifact_digest": expected[3],
    }
    design_completion = {
        "artifact_type": "m4_v2_marginal_static_health_design_completion",
        "artifact_digest": expected[4],
    }
    design_execution = {
        "execution_id": "1" * 64,
        "artifact_digest": expected[1],
        "completion_fact": MARGINAL_STATIC_HEALTH_DESIGN_COMPLETION_FACT,
        "generated_issues": 0,
        "synthetic_replicates": 0,
        "historical_outcomes_read": False,
        "evidence_created": False,
        "duplicate_raw_replay": False,
        "routine_physical_checkpoint_scan": False,
    }
    registered_by_type = {
        "m4_v2_marginal_static_health_workload": workload,
        "m4_v2_marginal_static_health_inference": inference,
        "m4_v2_marginal_static_health_design_completion": design_completion,
    }
    monkeypatch.setattr(
        supervisor_module,
        "_load_single_completed_execution",
        lambda **_: ({}, design_execution, "design-registrations"),
    )
    monkeypatch.setattr(
        supervisor_module,
        "_load_registered_type",
        lambda **kwargs: registered_by_type[kwargs["artifact_type"]],
    )

    def artifact(artifact_type: str, digest: str, **body: object) -> dict:
        return {
            "schema_version": f"test-{artifact_type}.v1",
            "artifact_type": artifact_type,
            "artifact_digest": digest,
            **body,
            "parent_digests": list(expected),
        }

    run = HealthExecutionRun(
        index_artifact=artifact(
            "m4_v2_marginal_static_health_completion_index",
            "2" * 64,
            index_path="runtime/fake-health-index.jsonl",
        ),
        health_result=artifact(
            "m4_v2_marginal_static_measurement_health_result",
            "3" * 64,
            measurement_health="PASS",
            replicate_count=TOTAL_REPLICATES,
            generated_issues=TOTAL_GENERATED_ISSUES,
            outer_evaluation_issues=TOTAL_OUTER_EVALUATION_ISSUES,
        ),
        completion=artifact(
            "m4_v2_marginal_static_health_execution_completion", "4" * 64
        ),
        runtime_seconds=7.5,
        completed_before_run=128,
        completed_during_run=7_040,
        worker_count=22,
    )
    monkeypatch.setattr(supervisor_module, "execute_health_program", lambda **_: run)

    result = M4MarginalStaticHealthExecutionCapability(
        repository=object(),
        root_dir=tmp_path,
    ).execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="5" * 64,
        git_commit="6" * 40,
    )

    assert result.completion_facts == (
        MARGINAL_STATIC_HEALTH_EXECUTION_COMPLETION_FACT,
    )
    assert len(result.registrations) == 4
    assert result.execution_artifact["measurement_health"] == "PASS"
    assert result.execution_artifact["completed_replicates_before_run"] == 128
    assert result.execution_artifact["completed_replicates_during_run"] == 7_040
    assert result.execution_artifact["completion_index_loads"] == 1
    assert result.execution_artifact["duplicate_raw_replay"] is False
    assert result.execution_artifact["routine_physical_checkpoint_scan"] is False
    assert result.execution_artifact["downstream_consumer"] == (
        MARGINAL_STATIC_HEALTH_DECISION_TASK_KEY
    )

    registered_by_type.update(
        {
            str(run.index_artifact["artifact_type"]): dict(run.index_artifact),
            str(run.health_result["artifact_type"]): dict(run.health_result),
            str(run.completion["artifact_type"]): dict(run.completion),
        }
    )
    sentinel = {"sentinel": True}
    raw_index_path = tmp_path / str(run.index_artifact["index_path"])
    raw_index_path.parent.mkdir(parents=True, exist_ok=True)
    raw_index_path.write_text(
        json.dumps({"summary": sentinel}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        supervisor_module,
        "rebuild_health_artifacts_from_index",
        lambda **_: (
            dict(run.index_artifact),
            dict(run.health_result),
            dict(run.completion),
        ),
    )
    monkeypatch.setattr(
        supervisor_module,
        "build_replicate_specs",
        lambda **_: (object(),),
    )
    monkeypatch.setattr(supervisor_module, "run_replicate", lambda _: sentinel)

    class ReplayRepository:
        def list_mainline_execution_events(self, **_: object) -> list[dict]:
            return [
                {
                    "event_type": "completed",
                    "execution_id": "5" * 64,
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
        task_key=MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY,
        execution_id="5" * 64,
    )
    capability_replay = replay["capability_replay"]
    assert capability_replay["aggregate_rebuilt_from_compact_index"] is True
    assert capability_replay["sentinel_replicates_recomputed"] == 1
    assert capability_replay["duplicate_raw_replay"] is False


def test_supervisor_status_embeds_matching_live_progress(tmp_path: Path) -> None:
    supervisor = ResearchEvidenceSupervisor(
        repository=object(),
        root_dir=tmp_path,
        require_clean_tree=False,
    )
    state = {
        "schema_version": "dehps-research-evidence-supervisor-state.v1",
        "status": "RUNNING",
        "execution_id": "7" * 64,
        "task_digest": "8" * 64,
        "progress_projection_path": str(MARGINAL_STATIC_HEALTH_PROGRESS_PATH),
    }
    progress = {
        "execution_id": state["execution_id"],
        "task_digest": state["task_digest"],
        "completed_replicates": 640,
        "total_replicates": 7_168,
        "replicates_per_second": 12.5,
        "eta_seconds": 522.24,
    }
    supervisor.state_path.parent.mkdir(parents=True, exist_ok=True)
    supervisor.state_path.write_text(json.dumps(state), encoding="utf-8")
    progress_path = tmp_path / MARGINAL_STATIC_HEALTH_PROGRESS_PATH
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    progress_path.write_text(json.dumps(progress), encoding="utf-8")

    assert supervisor.status()["progress"] == progress


def test_manifest_declares_execution_and_separate_decision_consumer() -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    tasks = {item.task_key: item for item in manifest.tasks}
    execution = tasks[MARGINAL_STATIC_HEALTH_EXECUTION_TASK_KEY]
    decision = tasks[MARGINAL_STATIC_HEALTH_DECISION_TASK_KEY]

    assert execution.requested_capability == MARGINAL_STATIC_HEALTH_EXECUTION_CAPABILITY
    metrics = json.loads(execution.metric_contract)
    assert metrics["formal_execution_allowed"] is True
    assert metrics["duplicate_raw_replay"] is False
    assert len(execution.input_artifact_digests) == 5
    assert decision.requested_capability == MARGINAL_STATIC_HEALTH_DECISION_CAPABILITY
    assert len(decision.input_artifact_digests) == 5
    assert any(
        item.target_key == MARGINAL_STATIC_HEALTH_EXECUTION_COMPLETION_FACT
        for item in decision.dependencies
    )
    assert (
        MARGINAL_STATIC_HEALTH_EXECUTION_CAPABILITY
        in ResearchEvidenceSupervisor(
            repository=SimpleNamespace(),
            require_clean_tree=False,
        ).capabilities
    )


def test_source_contract_detects_execution_kernel_tamper(tmp_path: Path) -> None:
    _copy_source_tree(tmp_path)
    source = load_marginal_static_health_execution_source_contract(
        tmp_path / MARGINAL_STATIC_HEALTH_EXECUTION_SOURCE_CONTRACT_PATH
    )
    relative = Path(source["source_entries"][0]["path"])
    target = tmp_path / relative
    target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert (
        hashlib.sha256(target.read_bytes()).hexdigest()
        != source["source_entries"][0]["content_sha256"]
    )
    with pytest.raises(MarginalStaticHealthExecutionError, match="source_modified"):
        verify_marginal_static_health_execution_source_bytes(
            root_dir=tmp_path,
            contract=source,
        )
