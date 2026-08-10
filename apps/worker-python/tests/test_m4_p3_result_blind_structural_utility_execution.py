from __future__ import annotations

import copy
import json
from collections.abc import Mapping

import pytest
from dehps.config import ROOT_DIR
from dehps.contracts import canonical_digest
from dehps.input_contracts.candidate_abi import (
    CandidateUniverseManifest,
    candidate_unrank,
)
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory.progress import (
    build_m4_status,
    load_m4_manifest,
)
from dehps.research_os.structural_utility import m4_p3_result_blind_execution as blind
from dehps.research_os.structural_utility.m4_p3_result_blind_execution import (
    COORDINATE_ORDER,
    FOLD_COUNT,
    PARENT_PREREGISTRATION_DIGEST,
    RESEARCH_CONTEXT_FINGERPRINT,
    RESEARCH_CONTRACT_DOMAIN,
    RESEARCH_EXECUTION_ID,
    RESEARCH_PARENT_REQUEST_ID,
    RESEARCH_REQUEST_ID,
    RESEARCH_REQUEST_KEY,
    BlindStructuralUtilityFoldRunner,
    M4P3ResultBlindStructuralUtilityExecutionError,
    build_completion,
    build_result_index,
    calculate_structural_metrics,
    load_m4_p3_result_blind_structural_utility_execution_source_contract,
    replay_result_blind_walk_forward_artifacts,
    sample_uniform_legal_lex_ids,
    target_issues,
    validate_research_execution_contract,
    verify_m4_p3_result_blind_structural_utility_execution_source_bytes,
)
from dehps.research_os.supervisor import (
    M4P3ResultBlindStructuralUtilityExecutionCapability,
    ResearchEvidenceSupervisor,
)
from scripts.build_m4_p3_result_blind_structural_utility_execution_manifest import (
    _source_payload,
)

MANIFEST_PATH = ROOT_DIR / "configs/research-os/m4-information-theory-evidence-v1.json"
INDEX_PATH = (
    ROOT_DIR / "configs/research-os/m4-information-theory-artifact-index-v1.json"
)


def _research_inputs(contract: dict) -> tuple[dict, dict]:
    return (
        {
            "id": RESEARCH_REQUEST_ID,
            "request_key": RESEARCH_REQUEST_KEY,
            "request_type": "research_scheduler_request",
            "status": "completed",
            "parent_request_id": RESEARCH_PARENT_REQUEST_ID,
            "payload": {
                "context_fingerprint": RESEARCH_CONTEXT_FINGERPRINT,
                "execution_contract": contract,
            },
            "metadata": {
                "result_blind": True,
                "result_aware": False,
                "new_model_authorized": False,
            },
        },
        {
            "id": RESEARCH_EXECUTION_ID,
            "request_id": RESEARCH_REQUEST_ID,
            "status": "completed",
            "result": {
                "contract_status": "FROZEN_BEFORE_IMPLEMENTATION",
                "fold_count": 90,
                "portfolios_generated": 0,
                "folds_executed": 0,
                "target_draw_rows_read": 0,
                "metric_results_read": 0,
                "bootstrap_resamples_executed": 0,
                "candidate_abi_lex_id_origin": 0,
                "engineering_authorized": False,
                "mainline_execution_authorized": False,
            },
        },
    )


def test_research_contract_is_exact_and_result_blind(monkeypatch) -> None:
    contract = {"status": "FROZEN_BEFORE_IMPLEMENTATION", "result_blind": True}
    monkeypatch.setattr(
        blind,
        "RESEARCH_EXECUTION_CONTRACT_DIGEST",
        canonical_digest(contract, domain=RESEARCH_CONTRACT_DOMAIN),
    )
    request, execution = _research_inputs(contract)
    assert validate_research_execution_contract(request, execution) == contract
    mutated = copy.deepcopy(request)
    mutated["payload"]["execution_contract"]["result_blind"] = False
    with pytest.raises(
        M4P3ResultBlindStructuralUtilityExecutionError,
        match="research_identity_changed",
    ):
        validate_research_execution_contract(mutated, execution)


def test_random_sampler_has_frozen_zero_based_golden_vector() -> None:
    expected = (
        301378,
        280353,
        746270,
        86476,
        726954,
        312649,
        920650,
        1066917,
        879966,
        980682,
    )
    first = sample_uniform_legal_lex_ids(target_issue="2026002", replicate_index=0)
    repeated = sample_uniform_legal_lex_ids(target_issue="2026002", replicate_index=0)
    next_replicate = sample_uniform_legal_lex_ids(
        target_issue="2026002", replicate_index=1
    )
    assert first[:10] == expected
    assert first == repeated
    assert first != next_replicate
    assert len(first) == len(set(first)) == 100
    assert min(first) >= 0
    assert max(first) < 1_107_568


def test_structural_metrics_are_ticket_only_and_recomputable() -> None:
    universe = CandidateUniverseManifest(domain_size=33, pick_count=6)
    tickets = [candidate_unrank(index, universe=universe) for index in range(100)]
    metrics = calculate_structural_metrics(tickets)
    sufficient = metrics["sufficient_statistics"]
    assert tuple(metrics["coordinates"]) == COORDINATE_ORDER
    assert sufficient["distinct_pair_count"] == 222
    assert sufficient["distinct_triple_count"] == 578
    assert sufficient["high_overlap_ticket_pair_count"] == 4950
    assert sum(sufficient["pair_use_counts"]) == 1500
    assert sum(sufficient["family_counts"].values()) == 100
    assert metrics["coordinates"] == pytest.approx(
        {
            "pair_coverage_ratio": 222 / 528,
            "triple_coverage_ratio": 578 / 5456,
            "high_overlap_ticket_pair_rate": 1.0,
            "normalized_pair_usage_entropy": 0.6715016180323102,
            "largest_similarity_cluster_fraction": 1.0,
            "family_concentration_hhi": 1.0,
        }
    )
    with pytest.raises(
        M4P3ResultBlindStructuralUtilityExecutionError,
        match="portfolio_identity_invalid",
    ):
        calculate_structural_metrics(tickets[:-1])


def test_fold_runner_rejects_target_or_missing_prior_boundary_before_scoring() -> None:
    runner = object.__new__(BlindStructuralUtilityFoldRunner)
    history = [
        (str(2_025_000 + index), None, (1, 2, 3, 4, 5, 6)) for index in range(900)
    ]
    with pytest.raises(
        M4P3ResultBlindStructuralUtilityExecutionError,
        match="history_boundary_invalid",
    ):
        runner.execute_fold(
            target_issue="2026002",
            history=history,
            preregistration={"artifact_digest": PARENT_PREREGISTRATION_DIGEST},
            source_contract_digest="a" * 64,
        )


def _fake_fold(issue: str, ordinal: int) -> dict:
    candidate = {key: float(ordinal + 2) for key in COORDINATE_ORDER}
    legacy = {key: float(ordinal + 1) for key in COORDINATE_ORDER}
    random = {key: float(ordinal) for key in COORDINATE_ORDER}
    return blind._artifact(
        schema_version="dehps-m4-p3-result-blind-structural-utility-fold.v1",
        artifact_type="m4_p3_result_blind_structural_utility_fold",
        body={
            "status": "COMPLETE",
            "target_issue": issue,
            "as_of_issue": str(int(issue) - 1),
            "fold_ordinal": ordinal,
            "result_blind": True,
            "arms": {
                "prediction_v2_structural_selection_100": {
                    "metrics": {"coordinates": candidate}
                },
                "legacy_structural_top100": {"metrics": {"coordinates": legacy}},
                "uniform_random_without_replacement": {"fold_coordinate_means": random},
            },
            "target_draw_rows_read": 0,
            "winning_labels_read": 0,
            "payout_or_reward_values_read": 0,
            "outcome_rank_values_read": 0,
            "bootstrap_resamples_executed": 0,
            "portfolios_generated": 34,
            "random_replicates_executed": 32,
            "metric_portfolios_evaluated": 34,
        },
        parent_digests=(
            "a" * 64,
            blind.PARENT_PREREGISTRATION_DIGEST,
            blind.PARENT_HANDOFF_DIGEST,
            blind.PARENT_COMPLETION_DIGEST,
        ),
        domain=blind._FOLD_DOMAIN,
    )


def test_complete_result_index_replays_without_bootstrap_or_workload_rerun() -> None:
    folds = tuple(
        _fake_fold(issue, ordinal) for ordinal, issue in enumerate(target_issues())
    )
    index = build_result_index(folds, source_contract_digest="b" * 64)
    completion = build_completion(
        result_index=index,
        fold_artifacts=folds,
        source_contract_digest="b" * 64,
    )
    assert len(folds) == FOLD_COUNT
    assert len(index["favorable_difference_series"]) == 12
    assert index["bootstrap_resamples_executed"] == 0
    assert index["holm_executed"] is False
    assert completion["registered_child_count"] == 92
    replay = replay_result_blind_walk_forward_artifacts(
        fold_artifacts=folds,
        result_index=index,
        completion=completion,
        source_contract_digest="b" * 64,
    )
    assert replay["status"] == "REPLAY_VERIFIED"
    assert replay["workload_rerun"] is False
    assert replay["target_draw_rows_read"] == 0


def test_complete_fold_resume_skips_scoring_and_checkpoints_every_five() -> None:
    folds = tuple(
        _fake_fold(issue, ordinal) for ordinal, issue in enumerate(target_issues())
    )
    by_issue = {str(item["target_issue"]): item for item in folds}
    checkpoints: list[tuple[Mapping[str, object], ...]] = []

    run = blind.execute_result_blind_walk_forward(
        history_loader=lambda _issue: (_ for _ in ()).throw(
            AssertionError("reused folds must not load history")
        ),
        preregistration={"artifact_digest": blind.PARENT_PREREGISTRATION_DIGEST},
        source_contract_digest="a" * 64,
        code_commit="1" * 40,
        load_fold=by_issue.get,
        persist_checkpoint=lambda items: checkpoints.append(tuple(items)),
    )

    assert run.fold_artifacts == folds
    assert [len(items) for items in checkpoints] == list(range(5, 91, 5))


def test_source_contract_pins_execution_module() -> None:
    source = load_m4_p3_result_blind_structural_utility_execution_source_contract(
        ROOT_DIR / blind.M4_P3_STRUCTURAL_UTILITY_EXECUTION_SOURCE_CONTRACT_PATH
    )
    verify_m4_p3_result_blind_structural_utility_execution_source_bytes(
        root_dir=ROOT_DIR, contract=source
    )
    assert source["research_execution_contract_digest"] == (
        blind.RESEARCH_EXECUTION_CONTRACT_DIGEST
    )


def test_manifest_status_index_and_supervisor_bind_blind_execution() -> None:
    source = load_m4_p3_result_blind_structural_utility_execution_source_contract(
        ROOT_DIR / blind.M4_P3_STRUCTURAL_UTILITY_EXECUTION_SOURCE_CONTRACT_PATH
    )
    manifest = load_m4_manifest(MANIFEST_PATH)
    tasks = {item.task_key: item for item in manifest.tasks}
    task = tasks[blind.M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY]
    assert (
        task.requested_capability == blind.M4_P3_STRUCTURAL_UTILITY_EXECUTION_CAPABILITY
    )
    assert task.input_artifact_digests == (
        source["artifact_digest"],
        blind.RESEARCH_EXECUTION_CONTRACT_DIGEST,
        blind.PARENT_PREREGISTRATION_EXECUTION_DIGEST,
        blind.PARENT_PREREGISTRATION_DIGEST,
        blind.PARENT_HANDOFF_DIGEST,
        blind.PARENT_COMPLETION_DIGEST,
    )
    evidence_compiler = tasks[blind.M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY]
    assert evidence_compiler.requested_capability is None
    resolutions = {
        item.task_key: item.status.value
        for item in ResearchOSControlPlane().resolve(manifest).resolutions
    }
    assert resolutions[blind.M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY] == (
        "dependency_wait"
    )
    assert resolutions[blind.M4_P3_STRUCTURAL_UTILITY_EVIDENCE_COMPILER_TASK_KEY] == (
        "external_wait"
    )
    projection = build_m4_status(manifest)["structural_utility"]
    assert projection["m4_p3_result_blind_execution"]["execution_authorized"] is True
    assert projection["m4_p3_result_blind_execution"]["folds_executed"] == 0
    assert projection["m4_p3_result_blind_execution"]["integration_answer"] == (
        "NO — INTEGRATION_PENDING"
    )
    assert projection["integration_answer"] == "NO — INTEGRATION_PENDING"
    artifacts = json.loads(INDEX_PATH.read_text())["artifacts"]
    assert artifacts[source["artifact_digest"]]["path"] == (
        blind.M4_P3_STRUCTURAL_UTILITY_EXECUTION_SOURCE_CONTRACT_PATH.as_posix()
    )
    supervisor = ResearchEvidenceSupervisor(
        repository=object(), require_clean_tree=False
    )
    assert (
        blind.M4_P3_STRUCTURAL_UTILITY_EXECUTION_CAPABILITY in supervisor.capabilities
    )


def test_execution_manifest_builder_reuses_exact_migrated_source() -> None:
    source = json.loads(MANIFEST_PATH.read_text())
    contract = load_m4_p3_result_blind_structural_utility_execution_source_contract(
        ROOT_DIR / blind.M4_P3_STRUCTURAL_UTILITY_EXECUTION_SOURCE_CONTRACT_PATH
    )
    assert _source_payload(source, contract["artifact_digest"]) == source


def test_supervisor_capability_persists_exact_92_child_boundary(
    monkeypatch, tmp_path
) -> None:
    manifest = load_m4_manifest(MANIFEST_PATH)
    task = next(
        item
        for item in manifest.tasks
        if item.task_key == blind.M4_P3_STRUCTURAL_UTILITY_EXECUTION_TASK_KEY
    )
    source = load_m4_p3_result_blind_structural_utility_execution_source_contract(
        ROOT_DIR / blind.M4_P3_STRUCTURAL_UTILITY_EXECUTION_SOURCE_CONTRACT_PATH
    )
    folds = tuple(
        _fake_fold(issue, ordinal) for ordinal, issue in enumerate(target_issues())
    )
    index = build_result_index(folds, source_contract_digest=source["artifact_digest"])
    completion = build_completion(
        result_index=index,
        fold_artifacts=folds,
        source_contract_digest=source["artifact_digest"],
    )
    run = blind.M4P3ResultBlindStructuralUtilityExecutionRun(
        fold_artifacts=folds,
        result_index=index,
        completion=completion,
    )

    class ConnectionContext:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, traceback):
            return False

    class Repository:
        @staticmethod
        def connection_factory():
            return ConnectionContext()

    def fake_execute(**kwargs):
        completed = []
        for fold in folds:
            kwargs["persist_fold"](fold)
            completed.append(fold)
            if len(completed) % 5 == 0:
                kwargs["persist_checkpoint"](tuple(completed))
        return run

    monkeypatch.setattr(
        "dehps.research_os.supervisor."
        "load_m4_p3_result_blind_structural_utility_execution_source_contract",
        lambda _path: source,
    )
    monkeypatch.setattr(
        "dehps.research_os.supervisor."
        "verify_m4_p3_result_blind_structural_utility_execution_source_bytes",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        "dehps.research_os.supervisor."
        "_load_m4_p3_result_blind_structural_utility_execution_inputs",
        lambda **_kwargs: (
            {},
            {},
            {"event_digest": "e" * 64},
            ({}, {}, {}, {}),
            {"artifact_digest": blind.PARENT_PREREGISTRATION_DIGEST},
        ),
    )
    monkeypatch.setattr(
        "dehps.research_os.supervisor.validate_research_execution_contract",
        lambda *_args: {},
    )
    monkeypatch.setattr(
        "dehps.research_os.supervisor.execute_result_blind_walk_forward",
        fake_execute,
    )
    capability = M4P3ResultBlindStructuralUtilityExecutionCapability(
        repository=Repository(),
        root_dir=tmp_path,
        agent_repository=object(),
    )
    result = capability.execute(
        control_plane_key="m4-information-theory-mainline",
        task=task,
        execution_id="fixture-execution",
        git_commit="1" * 40,
    )
    assert len(result.registrations) == 93
    assert result.execution_artifact["actual_fold_count"] == 90
    assert result.execution_artifact["registered_artifact_count"] == 93
    assert result.execution_artifact["checkpoint_count"] == 18
    assert (
        len(
            tuple(
                (
                    tmp_path
                    / "runtime/research-os/mainline/tasks"
                    / task.task_key
                    / "fixture-execution/checkpoints"
                ).glob("*.json")
            )
        )
        == 18
    )
    assert result.execution_artifact["target_draw_rows_read"] == 0
    assert result.execution_artifact["bootstrap_resamples_executed"] == 0
    assert result.completion_facts == (
        blind.M4_P3_STRUCTURAL_UTILITY_EXECUTION_COMPLETION_FACT,
    )
