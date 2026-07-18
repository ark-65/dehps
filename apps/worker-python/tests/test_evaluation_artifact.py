from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import date
import itertools

import pytest

from dehps.evaluation import (
    ActualOutcomeArtifactV1,
    CompiledEvaluationArtifactV1,
    EvaluationArtifactCompilerV1,
    EvaluationArtifactVerifier,
    EvaluationArtifactViolation,
    EvaluationCompileRequestV1,
    PredictionEvidenceArtifactV1,
)
from dehps.feature_runtime import FeatureABICompiler, FeatureCompileRequest, FeatureCompiler
from dehps.feature_runtime.runtime import FeatureABIRuntime
from dehps.input_contracts import (
    EvaluationCandidateV1,
    HistorySnapshotArtifact,
    WindowMode,
    WindowSpec,
)
from dehps.optimization.walk_forward import build_ranked_universe
from dehps.runtime_envelope import RuntimeEnvelopeCompiler, RuntimeState
from dehps.scoring_kernel import candidate_store_from_matrix
from dehps.unified_runtime import UnifiedRuntimeVerifier


CODE_COMMIT = "a" * 40
SOURCE_PAYLOAD_DIGEST = "b" * 64


@pytest.fixture(scope="module")
def evaluation_runtime_case():
    combinations = list(itertools.islice(itertools.combinations(range(1, 34), 6), 100))
    matrix = build_ranked_universe(
        combinations,
        use_cache=False,
        include_hard_filter_exclusions=True,
    )
    store = candidate_store_from_matrix(matrix)
    history = [
        ("2026001", (3, 8, 12, 18, 25, 33)),
        ("2026002", (5, 9, 14, 19, 24, 29)),
        ("2026003", (6, 11, 16, 21, 26, 31)),
        ("2026004", (1, 7, 13, 20, 27, 32)),
    ]
    snapshot = HistorySnapshotArtifact.from_history(history)
    window = WindowSpec(
        mode=WindowMode.EXPANDING,
        as_of_issue="2026004",
        include_as_of=True,
        size=None,
        target_issue="2026101",
    ).materialize(snapshot)
    feature_artifact = FeatureCompiler().compile(
        FeatureCompileRequest(window=window, candidate_store=store)
    )
    feature_package = FeatureABICompiler().compile(feature_artifact)
    assert store.candidate_abi_package is not None
    runtime = FeatureABIRuntime(
        history_snapshot=snapshot,
        window_artifact=window,
        candidate_package=store.candidate_abi_package,
        feature_tiles=(feature_package,),
    )
    verified = UnifiedRuntimeVerifier().verify(runtime)
    ready = RuntimeEnvelopeCompiler().compile_kernel_ready(
        verified,
        backend="feature_abi_numpy_reference",
        code_commit=CODE_COMMIT,
    )
    source_envelope = ready.transition(RuntimeState.KERNEL_EXECUTING).produce_artifact(
        SOURCE_PAYLOAD_DIGEST
    )
    prediction = PredictionEvidenceArtifactV1.build(
        prediction_run_key="static_100:2026101:fixture",
        line_key="static_100",
        target_issue="2026101",
        candidate_package_digest=store.candidate_abi_package.package_digest,
        scoring_contract=source_envelope.scoring_contract,
        ranking_contract=source_envelope.ranking_contract,
        candidates=(
            EvaluationCandidateV1(
                rank=1,
                red_numbers=tuple(int(number) for number in store.numbers[0]),
                score=0.9,
            ),
            EvaluationCandidateV1(
                rank=2,
                red_numbers=tuple(int(number) for number in store.numbers[1]),
                score=0.8,
            ),
        ),
    )
    outcome = ActualOutcomeArtifactV1.build(
        target_issue="2026101",
        draw_date=date(2026, 8, 2),
        red_numbers=tuple(int(number) for number in store.numbers[0]),
        blue_number=16,
    )
    return {
        "store": store,
        "source_envelope": source_envelope,
        "ready_envelope": ready,
        "prediction": prediction,
        "outcome": outcome,
        "ranking_audit": {
            "generated": True,
            "passed_hard_filters": True,
            "model_score_rank": 1,
            "ranking_contract": source_envelope.ranking_contract,
        },
    }


def _compile(case, **overrides):
    request = EvaluationCompileRequestV1(
        source_runtime_envelope=overrides.get(
            "source_runtime_envelope", case["source_envelope"]
        ),
        candidate_package=overrides.get(
            "candidate_package", case["store"].candidate_abi_package
        ),
        prediction=overrides.get("prediction", case["prediction"]),
        outcome=overrides.get("outcome", case["outcome"]),
        ranking_audit=overrides.get("ranking_audit", case["ranking_audit"]),
        evaluation_code_commit=overrides.get("evaluation_code_commit", CODE_COMMIT),
    )
    return EvaluationArtifactCompilerV1().compile(request)


def test_evaluation_artifact_binds_every_parent_without_copying_prediction(
    evaluation_runtime_case,
) -> None:
    first = _compile(evaluation_runtime_case)
    second = _compile(evaluation_runtime_case)

    assert first.prediction is evaluation_runtime_case["prediction"]
    assert first.artifact_digest == second.artifact_digest
    assert first.envelope.source_runtime_envelope_digest == evaluation_runtime_case[
        "source_envelope"
    ].envelope_digest
    assert first.envelope.source_runtime_artifact_payload_digest == SOURCE_PAYLOAD_DIGEST
    assert first.metrics.exact_rank == 1
    assert first.metrics.red5_rank == 2
    assert first.metrics.as_dict()["blue_scored"] is False
    EvaluationArtifactVerifier().verify(
        first,
        candidate_package=evaluation_runtime_case["store"].candidate_abi_package,
    )


def test_evaluation_artifact_detached_round_trip_is_digest_stable(
    evaluation_runtime_case,
) -> None:
    artifact = _compile(evaluation_runtime_case)
    restored = CompiledEvaluationArtifactV1.from_dict(deepcopy(artifact.as_dict()))

    assert restored.artifact_digest == artifact.artifact_digest
    assert restored.as_dict() == artifact.as_dict()


def test_evaluation_artifact_identity_changes_with_each_parent(
    evaluation_runtime_case,
) -> None:
    baseline = _compile(evaluation_runtime_case)
    prediction = PredictionEvidenceArtifactV1.build(
        prediction_run_key=evaluation_runtime_case["prediction"].prediction_run_key,
        line_key=evaluation_runtime_case["prediction"].line_key,
        target_issue=evaluation_runtime_case["prediction"].target_issue,
        candidate_package_digest=evaluation_runtime_case[
            "prediction"
        ].candidate_package_digest,
        scoring_contract=evaluation_runtime_case["prediction"].scoring_contract,
        ranking_contract=evaluation_runtime_case["prediction"].ranking_contract,
        candidates=(
            replace(evaluation_runtime_case["prediction"].candidates[0], score=0.89),
            *evaluation_runtime_case["prediction"].candidates[1:],
        ),
    )
    outcome = ActualOutcomeArtifactV1.build(
        target_issue=evaluation_runtime_case["outcome"].target_issue,
        draw_date=evaluation_runtime_case["outcome"].draw_date,
        red_numbers=evaluation_runtime_case["outcome"].red_numbers,
        blue_number=15,
    )
    source = evaluation_runtime_case["ready_envelope"].transition(
        RuntimeState.KERNEL_EXECUTING
    ).produce_artifact("c" * 64)

    variants = (
        _compile(evaluation_runtime_case, prediction=prediction),
        _compile(evaluation_runtime_case, outcome=outcome),
        _compile(
            evaluation_runtime_case,
            ranking_audit={**evaluation_runtime_case["ranking_audit"], "model_score_rank": 2},
        ),
        _compile(evaluation_runtime_case, source_runtime_envelope=source),
        _compile(evaluation_runtime_case, evaluation_code_commit="d" * 40),
    )

    assert all(variant.artifact_digest != baseline.artifact_digest for variant in variants)
    assert len({variant.artifact_digest for variant in variants}) == len(variants)


def test_evaluation_artifact_detached_mutation_fails_closed(evaluation_runtime_case) -> None:
    artifact = _compile(evaluation_runtime_case)
    payload = deepcopy(artifact.as_dict())
    payload["metrics"]["exact_rank"] = 2

    with pytest.raises(EvaluationArtifactViolation) as exc_info:
        CompiledEvaluationArtifactV1.from_dict(payload)
    assert exc_info.value.code in {
        "evaluation_metrics_serialization_mismatch",
        "evaluation_metrics_mismatch",
    }

    payload = deepcopy(artifact.as_dict())
    payload["ranking_audit"]["model_score_rank"] = 2
    with pytest.raises(EvaluationArtifactViolation) as exc_info:
        CompiledEvaluationArtifactV1.from_dict(payload)
    assert exc_info.value.code in {
        "evaluation_stage_binding_mismatch",
        "evaluation_artifact_serialization_mismatch",
    }


def test_evaluation_artifact_rejects_nonproduced_source_runtime(
    evaluation_runtime_case,
) -> None:
    with pytest.raises(EvaluationArtifactViolation) as exc_info:
        _compile(
            evaluation_runtime_case,
            source_runtime_envelope=evaluation_runtime_case["ready_envelope"],
        )
    assert exc_info.value.code == "evaluation_source_payload_digest_missing"


def test_evaluation_artifact_rejects_parent_contract_and_issue_mismatch(
    evaluation_runtime_case,
) -> None:
    prediction = PredictionEvidenceArtifactV1.build(
        prediction_run_key=evaluation_runtime_case["prediction"].prediction_run_key,
        line_key=evaluation_runtime_case["prediction"].line_key,
        target_issue=evaluation_runtime_case["prediction"].target_issue,
        candidate_package_digest="f" * 64,
        scoring_contract=evaluation_runtime_case["prediction"].scoring_contract,
        ranking_contract=evaluation_runtime_case["prediction"].ranking_contract,
        candidates=evaluation_runtime_case["prediction"].candidates,
    )
    with pytest.raises(EvaluationArtifactViolation) as exc_info:
        _compile(evaluation_runtime_case, prediction=prediction)
    assert exc_info.value.code == "evaluation_candidate_binding_mismatch"

    wrong_outcome = ActualOutcomeArtifactV1.build(
        target_issue="2026102",
        draw_date=evaluation_runtime_case["outcome"].draw_date,
        red_numbers=evaluation_runtime_case["outcome"].red_numbers,
        blue_number=evaluation_runtime_case["outcome"].blue_number,
    )
    with pytest.raises(EvaluationArtifactViolation) as exc_info:
        _compile(evaluation_runtime_case, outcome=wrong_outcome)
    assert exc_info.value.code == "evaluation_target_issue_mismatch"


def test_evaluation_artifact_rejects_source_history_leakage(
    evaluation_runtime_case,
) -> None:
    prediction = PredictionEvidenceArtifactV1.build(
        prediction_run_key="static_100:2026004:leaking",
        line_key=evaluation_runtime_case["prediction"].line_key,
        target_issue="2026004",
        candidate_package_digest=evaluation_runtime_case[
            "prediction"
        ].candidate_package_digest,
        scoring_contract=evaluation_runtime_case["prediction"].scoring_contract,
        ranking_contract=evaluation_runtime_case["prediction"].ranking_contract,
        candidates=evaluation_runtime_case["prediction"].candidates,
    )
    outcome = ActualOutcomeArtifactV1.build(
        target_issue="2026004",
        draw_date=evaluation_runtime_case["outcome"].draw_date,
        red_numbers=evaluation_runtime_case["outcome"].red_numbers,
        blue_number=evaluation_runtime_case["outcome"].blue_number,
    )

    with pytest.raises(EvaluationArtifactViolation) as exc_info:
        _compile(evaluation_runtime_case, prediction=prediction, outcome=outcome)
    assert exc_info.value.code == "evaluation_source_history_leakage"


def test_evaluation_artifact_rejects_candidate_absent_from_source_package(
    evaluation_runtime_case,
) -> None:
    prediction = PredictionEvidenceArtifactV1.build(
        prediction_run_key=evaluation_runtime_case["prediction"].prediction_run_key,
        line_key=evaluation_runtime_case["prediction"].line_key,
        target_issue=evaluation_runtime_case["prediction"].target_issue,
        candidate_package_digest=evaluation_runtime_case[
            "prediction"
        ].candidate_package_digest,
        scoring_contract=evaluation_runtime_case["prediction"].scoring_contract,
        ranking_contract=evaluation_runtime_case["prediction"].ranking_contract,
        candidates=(
            EvaluationCandidateV1(
                rank=1,
                red_numbers=(28, 29, 30, 31, 32, 33),
                score=0.9,
            ),
        ),
    )
    with pytest.raises(EvaluationArtifactViolation) as exc_info:
        _compile(evaluation_runtime_case, prediction=prediction)
    assert exc_info.value.code == "evaluation_candidate_not_in_source_package"


def test_evaluation_artifact_object_mutation_is_detected(evaluation_runtime_case) -> None:
    artifact = _compile(evaluation_runtime_case)
    mutated = replace(
        artifact,
        metrics=replace(artifact.metrics, exact_rank=2),
    )

    with pytest.raises(EvaluationArtifactViolation) as exc_info:
        EvaluationArtifactVerifier().verify(mutated)
    assert exc_info.value.code == "evaluation_metrics_mismatch"
