from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from dehps.config import ROOT_DIR
from dehps.contracts import canonical_digest
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory.progress import build_m4_status
from dehps.research_os.mainline import mainline_completion_fact
from dehps.research_os.models import ControlPlaneManifest
from dehps.research_os.structural_utility import m4_p3_evidence_compiler as compiler
from dehps.research_os.structural_utility.m4_p3_evidence_compiler import (
    M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_COMPLETION_FACT,
    M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_SOURCE_CONTRACT_PATH,
    M4P3StructuralEvidenceCompilerError,
    compile_structural_evidence,
    load_m4_p3_structural_evidence_compiler_source_contract,
    replay_structural_evidence,
    validate_research_contract,
    verify_m4_p3_structural_evidence_compiler_source_bytes,
)
from dehps.research_os.structural_utility.m4_p3_result_blind_execution import (
    M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY,
    M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY,
)
from dehps.research_os.supervisor import M4P3StructuralEvidenceCompilerCapability
from scripts.build_m4_p3_structural_evidence_compiler_manifest import (
    _source_payload,
)

MANIFEST_PATH = ROOT_DIR / "apps/worker-python/tests/fixtures/research_os/m4-information-theory-evidence-head-b6c03ba.json"
RESULT_INDEX_DOMAIN = (
    "dehps.m4-p3.result-blind-structural-utility.result-index.v1"
)


def _load(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _result_index(*, supported: bool) -> dict:
    series = {}
    for key in compiler.HYPOTHESIS_ORDER:
        coordinate, _ = key.split(":", 1)
        value = 0.1 if supported and coordinate in compiler.PRIMARY_COORDINATES else 0.0
        series[key] = [value] * compiler.FOLD_COUNT
    payload = {
        "schema_version": (
            "dehps-m4-p3-result-blind-structural-utility-result-index.v1"
        ),
        "artifact_type": (
            "m4_p3_result_blind_structural_utility_result_index"
        ),
        "artifact_digest": "",
        "status": "COMPLETE",
        "fold_count": compiler.FOLD_COUNT,
        "coordinate_order": list(compiler.COORDINATE_ORDER),
        "control_order": list(compiler.CONTROL_ORDER),
        "favorable_difference_series": series,
        "bootstrap_resamples_executed": 0,
        "holm_executed": False,
        "evidence_created": False,
        "route_decision_created": False,
        "target_draw_rows_read": 0,
    }
    identity = dict(payload)
    identity.pop("artifact_digest")
    payload["artifact_digest"] = canonical_digest(
        identity,
        domain=RESULT_INDEX_DOMAIN,
    )
    return payload


def test_source_contract_binds_exact_compiler_bytes() -> None:
    source = load_m4_p3_structural_evidence_compiler_source_contract(
        ROOT_DIR / M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_SOURCE_CONTRACT_PATH
    )
    verify_m4_p3_structural_evidence_compiler_source_bytes(
        root_dir=ROOT_DIR,
        contract=source,
    )
    assert source["execution_authorized"] is False
    assert source["research_request_id"] == 462


def test_research_contract_is_frozen_and_zero_work(monkeypatch: pytest.MonkeyPatch) -> None:
    contract = {"status": "FROZEN_BEFORE_EVIDENCE_COMPILATION"}
    request = {
        "id": compiler.RESEARCH_REQUEST_ID,
        "request_key": compiler.RESEARCH_REQUEST_KEY,
        "status": "completed",
        "parent_request_id": compiler.RESEARCH_PARENT_REQUEST_ID,
        "payload": {"execution_contract": contract},
    }
    execution = {
        "id": compiler.RESEARCH_EXECUTION_ID,
        "request_id": compiler.RESEARCH_REQUEST_ID,
        "status": "completed",
        "result": {
            "execution_contract_digest": (
                compiler.RESEARCH_EXECUTION_CONTRACT_DIGEST
            ),
            "execution_contract": contract,
            "work": {"result_rows_read": 0, "decisions_created": 0},
        },
    }
    original = compiler.canonical_digest
    monkeypatch.setattr(
        compiler,
        "canonical_digest",
        lambda payload, *, domain: (
            compiler.RESEARCH_EXECUTION_CONTRACT_DIGEST
            if domain == compiler.RESEARCH_CONTRACT_DOMAIN
            else original(payload, domain=domain)
        ),
    )
    assert validate_research_contract(request, execution) == contract
    execution["result"]["work"]["result_rows_read"] = 1
    with pytest.raises(M4P3StructuralEvidenceCompilerError):
        validate_research_contract(request, execution)


def test_joint_circular_block_indices_are_deterministic_and_shared() -> None:
    first = compiler._bootstrap_indices("a" * 64)
    second = compiler._bootstrap_indices("a" * 64)
    assert np.array_equal(first, second)
    assert first.shape == (20_000, 90)
    first_row = first[0]
    for block_start in range(0, 90, 5):
        block = first_row[block_start : block_start + 5]
        assert np.array_equal(block, (block[0] + np.arange(5)) % 90)


@pytest.mark.parametrize(
    ("supported", "expected_decision"),
    [
        (True, "STRUCTURAL_UTILITY_SUPPORTED_WITHIN_FROZEN_SCOPE"),
        (False, "NO_STABLE_STRUCTURAL_UTILITY"),
    ],
)
def test_compiler_applies_all_twelve_gates_and_replays(
    supported: bool,
    expected_decision: str,
) -> None:
    result_index = _result_index(supported=supported)
    digest = str(result_index["artifact_digest"])
    run = compile_structural_evidence(
        result_index=result_index,
        source_contract_digest="source-contract",
        expected_result_index_digest=digest,
    )
    assert run.route_decision["decision"] == expected_decision
    assert run.evidence["all_twelve_gates_pass"] is supported
    assert len(run.evidence["hypothesis_results"]) == 12
    primary_results = [
        item
        for item in run.evidence["hypothesis_results"].values()
        if item["decision_role"] == "primary_support"
    ]
    protected_results = [
        item
        for item in run.evidence["hypothesis_results"].values()
        if item["decision_role"] == "protected_non_regression"
    ]
    assert all(item["pass"] is supported for item in primary_results)
    assert all(item["pass"] is True for item in protected_results)
    assert run.route_decision["prediction_v2_mode"] == "SHADOW_ONLY"
    assert run.route_decision["promotion_gate_opened"] is False
    replay = replay_structural_evidence(
        result_index=result_index,
        source_contract_digest="source-contract",
        artifacts=run.artifacts,
        expected_result_index_digest=digest,
    )
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["workload_rerun"] is True
    assert replay["decision"] == expected_decision


def test_manifest_migration_and_status_preserve_execution_projection() -> None:
    base = _load(MANIFEST_PATH)
    source_contract = load_m4_p3_structural_evidence_compiler_source_contract(
        ROOT_DIR / M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_SOURCE_CONTRACT_PATH
    )
    migrated = _source_payload(base, str(source_contract["artifact_digest"]))
    execution_task = next(
        item
        for item in migrated["tasks"]
        if item["task_key"] == M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY
    )
    execution_task["status"] = "completed"
    execution_task["completion_classification"] = "COMPLETE"
    execution_fact = (
        "m4-p3-result-blind-structural-utility-"
        "blind-generator-and-walk-forward:COMPLETE"
    )
    if execution_fact not in migrated["facts"]["artifacts"]:
        migrated["facts"]["artifacts"].append(execution_fact)
    migrated.pop("manifest_digest", None)
    manifest = ControlPlaneManifest.from_dict(migrated)
    execution_model = next(
        item
        for item in manifest.tasks
        if item.task_key == M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY
    )
    migrated["facts"]["artifacts"].append(
        mainline_completion_fact(task=execution_model, execution_id="a" * 64)
    )
    manifest = ControlPlaneManifest.from_dict(migrated)
    snapshot = ResearchOSControlPlane().resolve(manifest)
    resolutions = {item.task_key: item.status.value for item in snapshot.resolutions}
    assert resolutions[M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY] == "ready"

    completed = copy.deepcopy(migrated)
    completed.pop("manifest_digest", None)
    task = next(
        item
        for item in completed["tasks"]
        if item["task_key"] == M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY
    )
    task["status"] = "completed"
    task["completion_classification"] = "COMPLETE"
    completed["facts"]["artifacts"].append(
        M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_COMPLETION_FACT
    )
    completed_manifest = ControlPlaneManifest.from_dict(completed)
    compiler_model = next(
        item
        for item in completed_manifest.tasks
        if item.task_key == M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY
    )
    completed["facts"]["artifacts"].append(
        mainline_completion_fact(task=compiler_model, execution_id="b" * 64)
    )
    completed_manifest = ControlPlaneManifest.from_dict(completed)
    completed_snapshot = ResearchOSControlPlane().resolve(completed_manifest)
    status = build_m4_status(
        completed_manifest,
        snapshot=completed_snapshot,
        m4_p3_execution_summary={
            "execution_task_key": M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY,
            "execution_artifact_digest": "blind-execution",
            "actual_fold_count": 90,
            "portfolios_generated": 3060,
            "target_draw_rows_read": 0,
        },
        m4_p3_evidence_compiler_summary={
            "execution_task_key": (
                M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY
            ),
            "execution_artifact_digest": "compiler-execution",
            "bootstrap_resamples_executed": 20_000,
            "holm_hypotheses_evaluated": 12,
            "decision": "NO_STABLE_STRUCTURAL_UTILITY",
            "evidence_digest": "evidence",
            "route_decision_digest": "route",
        },
    )["structural_utility"]
    assert status["m4_p3_result_blind_execution"]["folds_executed"] == 90
    assert status["m4_p3_structural_evidence_compiler"]["decision"] == (
        "NO_STABLE_STRUCTURAL_UTILITY"
    )
    assert status["next_consumer"] == "terminal structural route record"
    assert status["integration_answer"] == (
        "YES — validated by unified mainline execution and replay"
    )


def test_supervisor_capability_registers_exact_five_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    manifest = ControlPlaneManifest.from_dict(_load(MANIFEST_PATH))
    task = next(
        item
        for item in manifest.tasks
        if item.task_key == M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY
    )
    source = load_m4_p3_structural_evidence_compiler_source_contract(
        ROOT_DIR / M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_SOURCE_CONTRACT_PATH
    )
    fixture_index = _result_index(supported=True)
    fixture_run = compile_structural_evidence(
        result_index=fixture_index,
        source_contract_digest=str(source["artifact_digest"]),
        expected_result_index_digest=str(fixture_index["artifact_digest"]),
    )
    parent_completion = {
        "artifact_digest": compiler.PARENT_EXECUTION_COMPLETION_DIGEST,
        "status": "COMPLETE",
        "result_index_digest": compiler.PARENT_RESULT_INDEX_DIGEST,
    }
    monkeypatch.setattr(
        "dehps.research_os.supervisor."
        "load_m4_p3_structural_evidence_compiler_source_contract",
        lambda _path: source,
    )
    monkeypatch.setattr(
        "dehps.research_os.supervisor."
        "verify_m4_p3_structural_evidence_compiler_source_bytes",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        "dehps.research_os.supervisor."
        "_load_m4_p3_structural_evidence_compiler_inputs",
        lambda **_kwargs: (
            {},
            {},
            {"event_digest": "e" * 64},
            tuple({} for _ in range(93)),
            fixture_index,
            parent_completion,
        ),
    )
    monkeypatch.setattr(
        "dehps.research_os.supervisor.validate_m4_p3_evidence_research_contract",
        lambda *_args: {},
    )
    monkeypatch.setattr(
        "dehps.research_os.supervisor.compile_structural_evidence",
        lambda **_kwargs: fixture_run,
    )
    capability = M4P3StructuralEvidenceCompilerCapability(
        repository=object(),
        root_dir=tmp_path,
        agent_repository=object(),
    )
    result = capability.execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="fixture-execution",
        git_commit="1" * 40,
    )
    assert len(result.registrations) == 5
    assert result.execution_artifact["registered_artifact_count"] == 5
    assert result.execution_artifact["bootstrap_resamples_executed"] == 20_000
    assert result.execution_artifact["holm_hypotheses_evaluated"] == 12
    assert result.execution_artifact["target_draw_rows_read"] == 0
    assert result.execution_artifact["decision"] == (
        "STRUCTURAL_UTILITY_SUPPORTED_WITHIN_FROZEN_SCOPE"
    )
    assert result.completion_facts == (
        M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_COMPLETION_FACT,
    )
