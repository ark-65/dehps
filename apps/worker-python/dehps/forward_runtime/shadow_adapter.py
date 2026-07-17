from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

from dehps.ranking_contract import normalize_ranking_contract
from dehps.scoring_kernel import CandidateStore, KernelResult, ShadowOperationalEvidence
from dehps.scoring_kernel.packing import target_lex_id


class ForwardShadowViolation(ValueError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "context": dict(self.context)}


@dataclass(frozen=True)
class OfficialCandidateArtifactCheck:
    status: str
    candidate_count: int
    id_mismatch_count: int
    score_mismatch_count: int


@dataclass(frozen=True)
class ForwardEvaluationCheck:
    status: str
    mismatch_count: int


def compare_official_candidate_artifact(
    *,
    candidate_store: CandidateStore,
    official_result: KernelResult,
    stored_candidates: Sequence[Mapping[str, Any]],
) -> OfficialCandidateArtifactCheck:
    if official_result.top_candidate_ids.ndim != 2 or official_result.top_candidate_ids.shape[0] != 1:
        raise ForwardShadowViolation(
            "forward_shadow_config_count_mismatch",
            "one forward prediction run must map to exactly one scoring configuration",
        )
    expected_ids = official_result.top_candidate_ids[0]
    expected_scores = official_result.top_scores[0]
    stored_ids = np.full(len(stored_candidates), -1, dtype=np.int64)
    stored_scores = np.empty(len(stored_candidates), dtype=np.float64)
    for offset, row in enumerate(stored_candidates):
        expected_rank = offset + 1
        if int(row.get("rank") or 0) != expected_rank:
            raise ForwardShadowViolation(
                "forward_shadow_candidate_rank_gap",
                "stored official candidates must have contiguous one-based ranks",
                expected_rank=expected_rank,
                stored_rank=row.get("rank"),
            )
        numbers = tuple(int(value) for value in row.get("red_numbers") or ())
        if len(numbers) != 6:
            raise ForwardShadowViolation(
                "forward_shadow_candidate_shape_mismatch",
                "stored official candidate must contain six red numbers",
                rank=expected_rank,
            )
        row_index = target_lex_id(candidate_store, numbers)
        if row_index < len(candidate_store) and np.array_equal(
            candidate_store.numbers[row_index],
            np.asarray(numbers, dtype=np.uint8),
        ):
            stored_ids[offset] = row_index
        stored_scores[offset] = float(row["score"])

    shared = min(len(stored_ids), len(expected_ids))
    id_mismatches = abs(len(stored_ids) - len(expected_ids))
    score_mismatches = abs(len(stored_scores) - len(expected_scores))
    if shared:
        id_mismatches += int(np.count_nonzero(stored_ids[:shared] != expected_ids[:shared]))
        score_mismatches += int(
            np.count_nonzero(stored_scores[:shared] != expected_scores[:shared])
        )
    status = "matched" if id_mismatches == 0 and score_mismatches == 0 else "mismatch"
    return OfficialCandidateArtifactCheck(
        status=status,
        candidate_count=len(stored_candidates),
        id_mismatch_count=id_mismatches,
        score_mismatch_count=score_mismatches,
    )


def compare_forward_evaluation(
    *,
    official_result: KernelResult,
    evaluation_row: Mapping[str, Any] | None,
) -> ForwardEvaluationCheck:
    if evaluation_row is None:
        return ForwardEvaluationCheck(status="pending", mismatch_count=0)
    if evaluation_row.get("forward_evaluation_status") != "completed" or evaluation_row.get(
        "status"
    ) != "evaluated":
        return ForwardEvaluationCheck(status="failed", mismatch_count=1)
    summary = evaluation_row.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}
    ranking_audit = summary.get("ranking_audit")
    ranking_audit = ranking_audit if isinstance(ranking_audit, Mapping) else {}
    mismatch_count = 0
    if int(evaluation_row.get("candidate_count") or 0) != int(
        evaluation_row.get("top_n") or 0
    ):
        mismatch_count += 1
    if summary.get("leakage_passed") is not True:
        mismatch_count += 1
    if ranking_audit.get("model_score_rank") is None or int(
        ranking_audit["model_score_rank"]
    ) != int(official_result.exact_ranks[0]):
        mismatch_count += 1
    if ranking_audit.get("model_score") is None or float(
        ranking_audit["model_score"]
    ) != float(official_result.target_scores[0]):
        mismatch_count += 1
    return ForwardEvaluationCheck(
        status="passed" if mismatch_count == 0 else "failed",
        mismatch_count=mismatch_count,
    )


def forward_operational_evidence(
    *,
    prediction_run: Mapping[str, Any],
    artifact_check: OfficialCandidateArtifactCheck,
    evaluation_check: ForwardEvaluationCheck,
    source_code_commit: str,
    replay_code_commit: str,
    capture_mode: str,
    restart_recovery_result: str,
    watchdog_result: str,
) -> ShadowOperationalEvidence:
    return ShadowOperationalEvidence(
        capture_mode=capture_mode,
        prediction_run_key=str(prediction_run.get("prediction_run_key") or ""),
        source_prediction_ranking_contract=normalize_ranking_contract(
            prediction_run.get("ranking_contract")
        ),
        source_code_commit=source_code_commit,
        replay_code_commit=replay_code_commit,
        official_candidate_artifact_status=artifact_check.status,
        official_candidate_id_mismatch_count=artifact_check.id_mismatch_count,
        official_candidate_score_mismatch_count=artifact_check.score_mismatch_count,
        evaluation_status=evaluation_check.status,
        evaluation_mismatch_count=evaluation_check.mismatch_count,
        restart_recovery_result=restart_recovery_result,
        watchdog_result=watchdog_result,
    )
