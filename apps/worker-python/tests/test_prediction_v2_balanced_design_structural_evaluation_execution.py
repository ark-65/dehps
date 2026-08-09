from __future__ import annotations

import json
from itertools import combinations

import numpy as np
import pytest
from dehps.config import ROOT_DIR
from dehps.research_os.information_theory.measurement_system_v2.prediction_v2_balanced_design_structural_evaluation_execution import (
    BLOCK_COUNT,
    DIAGNOSTIC_REPLICATES,
    NULL_OUTCOME,
    POSITIVE_OUTCOME,
    PRIMARY_NULL,
    PRIMARY_REPLICATES,
    REGRESSION_OUTCOME,
    REPETITION_SCAN,
    SECONDARY_REPLICATES,
    CollisionDiagnostics,
    PredictionV2BalancedDesignStructuralEvaluationExecutionError,
    Shake256CounterRandomBelow,
    _checkpoint_family_outputs,
    _checkpoint_record,
    _inference,
    _load_checkpoint_chunks,
    batch_pair_intersection_diagnostics,
    block_to_mask,
    build_prediction_v2_balanced_design_structural_evaluation_artifacts,
    direct_triple_collision_mass,
    load_prediction_v2_balanced_design_structural_evaluation_execution_source_contract,
    pair_intersection_collision_diagnostics,
    replay_prediction_v2_balanced_design_structural_evaluation_execution,
    sparse_partial_fisher_yates_prefix,
    verify_prediction_v2_balanced_design_structural_evaluation_execution_source_bytes,
)


def _legal_blocks() -> list[tuple[int, ...]]:
    return list(combinations(range(33), 6))[:BLOCK_COUNT]


def _diagnostic(triple: int) -> dict[str, object]:
    return {
        "triple_collision_mass": triple,
        "quadruple_collision_mass": 0,
        "quintuple_collision_mass": 0,
        "block_intersection_histogram_0_through_5": [15400, 0, 0, 0, 0, 0],
        "maximum_block_intersection": 0,
        "minimum_replacement_distance": 6,
    }


def _parents() -> tuple[dict[str, str], ...]:
    return tuple({"artifact_digest": character * 64} for character in "abcdefgh")


def test_source_contract_pins_execution_and_reused_inventory_bytes() -> None:
    path = (
        ROOT_DIR
        / "configs/research-os/"
        "prediction-v2-balanced-design-structural-evaluation-execution-source-v1.json"
    )
    contract = load_prediction_v2_balanced_design_structural_evaluation_execution_source_contract(
        path
    )

    verify_prediction_v2_balanced_design_structural_evaluation_execution_source_bytes(
        root_dir=ROOT_DIR,
        contract=contract,
    )
    assert contract["research_request_id"] == 435
    assert contract["engineering_request_id"] == 436
    assert contract["source_set_digest"] == (
        "4d6921ffd5dd6de2c45dbc8176e56769bd02049428057992583ff8ca35cc8a2b"
    )


def test_pair_intersection_identity_matches_direct_triple_count() -> None:
    blocks = _legal_blocks()
    masks = [block_to_mask(block) for block in blocks]
    direct = direct_triple_collision_mass(blocks)
    pairwise = pair_intersection_collision_diagnostics(masks)

    assert pairwise.triple_collision_mass == direct
    assert sum(pairwise.block_intersection_histogram_0_through_5) == 15_400


def test_numba_pair_kernel_is_thread_count_invariant() -> None:
    blocks = _legal_blocks()
    masks = np.asarray(
        [[block_to_mask(block) for block in blocks]],
        dtype=np.uint64,
    )

    one = batch_pair_intersection_diagnostics(masks, thread_count=1)
    two = batch_pair_intersection_diagnostics(masks, thread_count=2)

    assert one == two
    assert one[0].triple_collision_mass == direct_triple_collision_mass(blocks)


def test_shake_counter_random_below_has_frozen_vectors() -> None:
    random = Shake256CounterRandomBelow("known-vector")

    assert [
        random.random_below(bound)
        for bound in (2, 3, 5, 17, 256, 1_107_568)
    ] == [1, 2, 0, 13, 126, 401_770]
    assert random.counter == 7


def test_sparse_partial_fisher_yates_has_frozen_vector() -> None:
    random = Shake256CounterRandomBelow("known-sample")

    selected = sparse_partial_fisher_yates_prefix(
        population_size=20,
        sample_size=8,
        random=random,
    )

    assert selected == (13, 4, 11, 2, 18, 6, 14, 1)
    assert random.counter == 11


def test_primary_domain_vector_is_frozen() -> None:
    random = Shake256CounterRandomBelow(
        "dehps|prediction-v2|balanced-design|structural-evaluation|v1|"
        f"{PRIMARY_NULL}|replicate=0|stream"
    )

    assert [
        random.random_below(bound)
        for bound in (33_561, 33_560, 33_559, 33_558, 33_557)
    ] == [15_851, 6_322, 29_074, 22_411, 5_829]
    assert random.counter == 10


def test_checkpoint_resume_skips_only_digest_verified_contiguous_chunks(
    tmp_path,
) -> None:
    path = tmp_path / "checkpoint.jsonl"
    diagnostics = (
        CollisionDiagnostics(3, 0, 0, (15400, 0, 0, 0, 0, 0), 0, 6),
        CollisionDiagnostics(4, 0, 0, (15400, 0, 0, 0, 0, 0), 0, 6),
    )
    record = _checkpoint_record(family="primary", start=0, diagnostics=diagnostics)
    path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")

    loaded = _load_checkpoint_chunks(path)
    masses, rebuilt = _checkpoint_family_outputs(chunks=loaded, family="primary")

    assert masses == [3, 4]
    assert [item["triple_collision_mass"] for item in rebuilt] == [3, 4]
    assert loaded[0]["duplicate_membership_uniqueness_or_repetition_scans"] == 0
    assert loaded[0]["repetition_scan"] == REPETITION_SCAN


def test_checkpoint_tamper_and_gap_fail_closed(tmp_path) -> None:
    path = tmp_path / "checkpoint.jsonl"
    diagnostic = CollisionDiagnostics(
        3,
        0,
        0,
        (15400, 0, 0, 0, 0, 0),
        0,
        6,
    )
    first = _checkpoint_record(family="primary", start=0, diagnostics=(diagnostic,))
    second = _checkpoint_record(family="primary", start=2, diagnostics=(diagnostic,))
    path.write_text(
        json.dumps(first, sort_keys=True)
        + "\n"
        + json.dumps(second, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(
        PredictionV2BalancedDesignStructuralEvaluationExecutionError,
        match="checkpoint_sequence_invalid",
    ):
        _load_checkpoint_chunks(path)

    changed = dict(first)
    changed["triple_collision_masses"] = [99]
    path.write_text(json.dumps(changed) + "\n", encoding="utf-8")
    with pytest.raises(
        PredictionV2BalancedDesignStructuralEvaluationExecutionError,
        match="artifact_digest_invalid",
    ):
        _load_checkpoint_chunks(path)


def test_exact_plus_one_outcome_mapping() -> None:
    positive = _inference(
        candidate_mass=0,
        primary_masses=[1] * PRIMARY_REPLICATES,
        secondary_masses=[1] * SECONDARY_REPLICATES,
    )
    regression = _inference(
        candidate_mass=2,
        primary_masses=[1] * PRIMARY_REPLICATES,
        secondary_masses=[1] * SECONDARY_REPLICATES,
    )
    null = _inference(
        candidate_mass=1,
        primary_masses=[1] * PRIMARY_REPLICATES,
        secondary_masses=[1] * SECONDARY_REPLICATES,
    )

    assert positive["primary_lower_tail_numerator"] == 1
    assert positive["outcome"] == POSITIVE_OUTCOME
    assert regression["primary_upper_tail_numerator"] == 1
    assert regression["outcome"] == REGRESSION_OUTCOME
    assert null["outcome"] == NULL_OUTCOME


def test_registered_arrays_replay_inference_without_workload() -> None:
    (
        source,
        preregistration_execution,
        preregistration,
        handoff,
        preregistration_completion,
        feasibility_execution,
        inventory,
        search_result,
    ) = _parents()
    candidate = _diagnostic(10)
    primary = [20] * PRIMARY_REPLICATES
    secondary = [30] * SECONDARY_REPLICATES
    primary_diagnostics = [_diagnostic(20) for _ in range(DIAGNOSTIC_REPLICATES)]
    secondary_diagnostics = [
        _diagnostic(30) for _ in range(DIAGNOSTIC_REPLICATES)
    ]

    run = build_prediction_v2_balanced_design_structural_evaluation_artifacts(
        source_contract=source,
        preregistration_mainline_execution=preregistration_execution,
        preregistration=preregistration,
        execution_handoff=handoff,
        preregistration_completion=preregistration_completion,
        feasibility_mainline_execution=feasibility_execution,
        orbit_inventory_artifact=inventory,
        search_result_artifact=search_result,
        candidate=candidate,
        primary_masses=primary,
        secondary_masses=secondary,
        primary_diagnostics=primary_diagnostics,
        secondary_diagnostics=secondary_diagnostics,
        checkpoint_chunk_count=28,
        terminal_checkpoint_digest="f" * 64,
    )
    replay = replay_prediction_v2_balanced_design_structural_evaluation_execution(
        result_artifact=run.result,
        diagnostics_artifact=run.diagnostics,
        completion_artifact=run.completion,
    )

    assert run.result["outcome"] == POSITIVE_OUTCOME
    assert run.result["duplicate_membership_uniqueness_or_repetition_scans"] == 0
    assert run.result["repetition_scan"] == REPETITION_SCAN
    assert replay == {
        "schema_version": (
            "dehps-prediction-v2-balanced-design-structural-evaluation-"
            "execution-replay.v1"
        ),
        "status": "REPLAY_VERIFIED",
        "same_registered_content": True,
        "workload_rerun": False,
        "sample_regeneration": False,
        "manual_input_assembly": False,
        "inference_recomputed_from_registered_arrays": True,
        "candidate_evaluations_replayed": 0,
        "null_replicates_replayed": 0,
        "database_queries_during_replay": 0,
        "historical_rows_read": 0,
        "folds_replayed": 0,
        "duplicate_membership_uniqueness_or_repetition_scans": 0,
        "repetition_scan": REPETITION_SCAN,
        "outcome": POSITIVE_OUTCOME,
        "next_consumer": (
            "prediction-v2-balanced-design-structural-evaluation-result-decision"
        ),
    }
