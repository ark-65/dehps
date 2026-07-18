from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Integral, Real
from typing import Any, Sequence

from dehps.contracts import ContractRef, canonical_digest
from dehps.input_contracts.candidate_abi import (
    CANDIDATE_CONTRACT_V1,
    CandidateContractViolation,
    CandidateUniverseManifest,
    candidate_rank,
    validate_candidate_numbers,
)
from dehps.ranking_contract import (
    CANDIDATE_IDENTITY_REGRESSION,
    LEGACY_RANKING_CONTRACT,
    RANKING_COMPARISON_EXACT,
    RANKING_CONTRACT_DIFFERENCE,
    SCORE_REGRESSION,
    STRICT_RANKING_CONTRACT,
    normalize_ranking_contract,
)


EVALUATION_CONTRACT_VERSION = "evaluation.v1.0.0"
EVALUATION_SCHEMA_VERSION = "dehps.evaluation.schema.v1"
EVALUATION_CUTOFFS: tuple[int, ...] = (100, 1_000, 10_000)
EVALUATION_SCORING_CONTRACT = "dehps-scoring-strict-v1"
EVALUATION_EVIDENCE_STATUS_VALUES: tuple[str, ...] = (
    "evaluated",
    "missing_actual_draw",
    "missing_prediction_snapshot",
    "prediction_snapshot_mismatch",
    "leakage_guard_failed",
)

EVALUATION_CONTRACT_DIFFERENCE = "evaluation-contract difference"
SCORING_CONTRACT_DIFFERENCE = "scoring-contract difference"
EVALUATION_METRIC_REGRESSION = "evaluation metric regression"

_UNIVERSE = CandidateUniverseManifest(domain_size=33, pick_count=6)


@dataclass(frozen=True)
class EvaluationCandidateV1:
    rank: int
    red_numbers: tuple[int, ...]
    score: float

    @property
    def lex_id(self) -> int:
        return candidate_rank(self.red_numbers, universe=_UNIVERSE)


@dataclass(frozen=True)
class EvaluationMetricsV1:
    actual_red_numbers: tuple[int, ...]
    exact_rank: int | None
    exact_score: float | None
    red5_rank: int | None
    red5_score: float | None
    red5_numbers: tuple[int, ...] | None
    matched_red_count_by_cutoff: tuple[tuple[int, int, int], ...]

    def as_dict(self) -> dict[str, Any]:
        cutoff_counts = {
            f"top_{cutoff}": {"6": exact_count, "5": red5_count}
            for cutoff, exact_count, red5_count in self.matched_red_count_by_cutoff
        }
        payload: dict[str, Any] = {
            "actual_red_numbers": list(self.actual_red_numbers),
            "exact_rank": self.exact_rank,
            "exact_score": self.exact_score,
            "red5_rank": self.red5_rank,
            "red5_score": self.red5_score,
            "red5_numbers": None if self.red5_numbers is None else list(self.red5_numbers),
            "matched_red_count_by_cutoff": cutoff_counts,
            "blue_scored": False,
        }
        for cutoff in EVALUATION_CUTOFFS:
            payload[f"hit_top_{cutoff}"] = (
                self.exact_rank is not None and self.exact_rank <= cutoff
            )
            payload[f"hit_red5_top_{cutoff}"] = (
                self.red5_rank is not None and self.red5_rank <= cutoff
            )
        return payload


def evaluation_metric_manifest() -> dict[str, Any]:
    return {
        "contract": EVALUATION_CONTRACT_VERSION,
        "dependencies": {
            "candidate_contract": CANDIDATE_CONTRACT_V1.as_dict(),
            "scoring_contract": EVALUATION_SCORING_CONTRACT,
            "accepted_ranking_contracts": [
                LEGACY_RANKING_CONTRACT,
                STRICT_RANKING_CONTRACT,
            ],
        },
        "outcome": {
            "red_numbers": "six_unique_strictly_increasing_integers_in_[1,33]",
            "blue_number": "recorded_as_provenance_but_never_scored",
        },
        "candidate_rows": {
            "identity": "canonical_red_numbers_under_candidate.v1.0.0",
            "rank": "positive_one_based_strictly_increasing_source_rank",
            "score": "finite_float64_compatible_value",
            "duplicates": "reject",
            "ordering": "preserve_source_ranking_contract_without_reranking",
        },
        "rank_namespaces": {
            "export_rank": "rank_within_the_persisted_candidate_artifact",
            "model_score_rank": "full_legal_universe_rank_from_the_scoring_audit",
            "rule_filter_rank": "rank_within_the_named_ranking_audit_stage",
            "rule": "rank_namespaces_must_never_be_substituted_or_compared_as_one_field",
        },
        "metrics": {
            "exact": "candidate_red_numbers_equal_actual_red_numbers",
            "red5": "set_intersection_cardinality_is_exactly_5",
            "best_red5": "minimum_source_rank_among_exactly_5_candidates",
            "cutoffs": list(EVALUATION_CUTOFFS),
            "cutoff_boundary": "inclusive_rank_less_than_or_equal_to_cutoff",
            "cutoff_counts": "count_exactly_6_and_exactly_5_candidates_separately",
            "missing_match": "null_rank_and_score_not_zero_or_sentinel",
        },
        "statuses": {
            "evidence": list(EVALUATION_EVIDENCE_STATUS_VALUES),
            "evaluation_run_lifecycle": ["running", "completed", "failed"],
            "prediction_evaluation_lifecycle": [
                "pending",
                "evaluating",
                "evaluated",
                "evaluation_failed",
            ],
            "rule": "evidence_status_and_execution_lifecycle_are_distinct_namespaces",
        },
        "comparison_precedence": [
            EVALUATION_CONTRACT_DIFFERENCE,
            SCORING_CONTRACT_DIFFERENCE,
            SCORE_REGRESSION,
            RANKING_CONTRACT_DIFFERENCE,
            CANDIDATE_IDENTITY_REGRESSION,
            EVALUATION_METRIC_REGRESSION,
            RANKING_COMPARISON_EXACT,
        ],
    }


EVALUATION_METRIC_MANIFEST_DIGEST = canonical_digest(
    evaluation_metric_manifest(),
    domain="dehps.evaluation-metric-manifest.v1",
)

EVALUATION_NORMATIVE_DEFINITION = {
    "contract": EVALUATION_CONTRACT_VERSION,
    "evaluation_function": "Evaluation = E(PredictionArtifact, ActualOutcome, RankingAudit)",
    "metric_manifest_digest": EVALUATION_METRIC_MANIFEST_DIGEST,
    "prediction_identity": "prediction_run_plus_target_issue_plus_source_contracts",
    "rank_semantics": "one_based_source_rank_with_explicit_namespace",
    "red5_semantics": "exactly_five_red_numbers_not_at_least_five",
    "blue_ball_policy": "record_only_never_scored",
    "comparison_policy": "contract_differences_precede_regression_classification",
    "dependencies": {
        "candidate_contract": CANDIDATE_CONTRACT_V1.normative_identity(),
        "scoring_contract": EVALUATION_SCORING_CONTRACT,
        "ranking_contracts": [LEGACY_RANKING_CONTRACT, STRICT_RANKING_CONTRACT],
    },
    "non_goals": [
        "no_evaluation_abi",
        "no_runtime_or_database_migration",
        "no_objective_or_promotion_policy",
        "no_historical_backfill",
    ],
}

EVALUATION_GOLDEN_SUITE = {
    "suite": "evaluation_contract_golden.v1",
    "source_scoring_contract": EVALUATION_SCORING_CONTRACT,
    "source_ranking_contract": STRICT_RANKING_CONTRACT,
    "actual_red_numbers": [1, 2, 3, 4, 5, 6],
    "actual_blue_number": 16,
    "candidate_rows": [
        {"rank": 1, "red_numbers": [1, 2, 3, 4, 5, 7], "score": 0.9},
        {"rank": 2, "red_numbers": [1, 2, 3, 4, 5, 6], "score": 0.8},
        {"rank": 100, "red_numbers": [1, 2, 3, 4, 6, 8], "score": 0.7},
        {"rank": 101, "red_numbers": [1, 2, 3, 5, 6, 9], "score": 0.6},
        {"rank": 1_000, "red_numbers": [1, 2, 4, 5, 6, 10], "score": 0.5},
        {"rank": 1_001, "red_numbers": [7, 8, 9, 10, 11, 12], "score": 0.45},
        {"rank": 10_000, "red_numbers": [2, 3, 4, 5, 6, 11], "score": 0.4},
        {"rank": 10_001, "red_numbers": [1, 2, 3, 4, 5, 12], "score": 0.3},
    ],
    "expected": {
        "actual_red_numbers": [1, 2, 3, 4, 5, 6],
        "exact_rank": 2,
        "exact_score": 0.8,
        "red5_rank": 1,
        "red5_score": 0.9,
        "red5_numbers": [1, 2, 3, 4, 5, 7],
        "matched_red_count_by_cutoff": {
            "top_100": {"6": 1, "5": 2},
            "top_1000": {"6": 1, "5": 4},
            "top_10000": {"6": 1, "5": 5},
        },
        "blue_scored": False,
        "hit_top_100": True,
        "hit_red5_top_100": True,
        "hit_top_1000": True,
        "hit_red5_top_1000": True,
        "hit_top_10000": True,
        "hit_red5_top_10000": True,
    },
}

EVALUATION_CONTRACT_V1 = ContractRef.from_definition(
    family="evaluation",
    semantic_version="1.0.0",
    schema_version=EVALUATION_SCHEMA_VERSION,
    normative_definition=EVALUATION_NORMATIVE_DEFINITION,
    golden_suite=EVALUATION_GOLDEN_SUITE,
)


class EvaluationContractViolation(ValueError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "context": dict(self.context)}


class EvaluationContractVerifier:
    def verify_manifest(self, manifest: dict[str, Any] | None = None) -> None:
        payload = evaluation_metric_manifest() if manifest is None else manifest
        if payload.get("contract") != EVALUATION_CONTRACT_VERSION:
            self._reject("evaluation_contract_mismatch", "unexpected evaluation contract")
        if payload.get("metrics", {}).get("cutoffs") != list(EVALUATION_CUTOFFS):
            self._reject("evaluation_cutoff_contract_mismatch", "cutoff definition changed")
        digest = canonical_digest(payload, domain="dehps.evaluation-metric-manifest.v1")
        if digest != EVALUATION_METRIC_MANIFEST_DIGEST:
            self._reject("evaluation_manifest_digest_mismatch", "metric manifest changed")

    def verify_outcome(self, actual_red_numbers: Sequence[object]) -> tuple[int, ...]:
        try:
            return validate_candidate_numbers(actual_red_numbers, universe=_UNIVERSE)
        except CandidateContractViolation as exc:
            self._reject(
                "evaluation_outcome_invalid",
                "actual red numbers are not a legal canonical outcome",
                cause=exc.code,
            )

    def verify_candidates(
        self,
        candidates: Sequence[EvaluationCandidateV1],
        *,
        ranking_contract: object,
    ) -> str:
        try:
            normalized_contract = normalize_ranking_contract(ranking_contract)
        except ValueError as exc:
            self._reject(
                "evaluation_ranking_contract_invalid",
                "source ranking contract is unknown",
                value=str(ranking_contract),
            )
            raise AssertionError("unreachable") from exc
        previous_rank = 0
        previous_score = math.inf
        previous_lex_id = -1
        identities: set[tuple[int, ...]] = set()
        for index, candidate in enumerate(candidates):
            if (
                not isinstance(candidate.rank, int)
                or isinstance(candidate.rank, bool)
                or candidate.rank <= previous_rank
            ):
                self._reject(
                    "evaluation_rank_order_invalid",
                    "candidate ranks must be positive and strictly increasing",
                    row=index,
                    rank=candidate.rank,
                )
            if not isinstance(candidate.red_numbers, tuple):
                self._reject(
                    "evaluation_candidate_type_invalid",
                    "candidate red numbers must use the frozen tuple value representation",
                    row=index,
                )
            try:
                canonical = validate_candidate_numbers(candidate.red_numbers, universe=_UNIVERSE)
            except CandidateContractViolation as exc:
                self._reject(
                    "evaluation_candidate_invalid",
                    "candidate red numbers are not canonical",
                    row=index,
                    cause=exc.code,
                )
            if canonical in identities:
                self._reject(
                    "evaluation_candidate_duplicate",
                    "candidate identities must be unique",
                    row=index,
                )
            if (
                not isinstance(candidate.score, Real)
                or isinstance(candidate.score, bool)
                or not math.isfinite(float(candidate.score))
            ):
                self._reject(
                    "evaluation_score_invalid",
                    "candidate score must be finite",
                    row=index,
                )
            score = float(candidate.score)
            lex_id = candidate_rank(canonical, universe=_UNIVERSE)
            if normalized_contract == STRICT_RANKING_CONTRACT:
                if score > previous_score:
                    self._reject(
                        "evaluation_strict_score_order_invalid",
                        "strict_v1 candidate scores must be non-increasing",
                        row=index,
                    )
                if score == previous_score and lex_id <= previous_lex_id:
                    self._reject(
                        "evaluation_strict_tie_order_invalid",
                        "strict_v1 equal-score candidates must use ascending lex_id",
                        row=index,
                    )
            identities.add(canonical)
            previous_rank = candidate.rank
            previous_score = score
            previous_lex_id = lex_id
        return normalized_contract

    @staticmethod
    def _reject(code: str, message: str, **context: Any) -> None:
        raise EvaluationContractViolation(code, message, **context)


def evaluate_ranked_candidates_v1(
    *,
    actual_red_numbers: Sequence[object],
    candidates: Sequence[EvaluationCandidateV1],
    ranking_contract: object,
) -> EvaluationMetricsV1:
    verifier = EvaluationContractVerifier()
    actual = verifier.verify_outcome(actual_red_numbers)
    verifier.verify_candidates(candidates, ranking_contract=ranking_contract)
    actual_set = set(actual)
    exact: EvaluationCandidateV1 | None = None
    red5: EvaluationCandidateV1 | None = None
    counts = {cutoff: {6: 0, 5: 0} for cutoff in EVALUATION_CUTOFFS}
    for candidate in candidates:
        overlap = len(actual_set.intersection(candidate.red_numbers))
        if candidate.red_numbers == actual and exact is None:
            exact = candidate
        if overlap == 5 and red5 is None:
            red5 = candidate
        if overlap in {5, 6}:
            for cutoff in EVALUATION_CUTOFFS:
                if candidate.rank <= cutoff:
                    counts[cutoff][overlap] += 1
    return EvaluationMetricsV1(
        actual_red_numbers=actual,
        exact_rank=None if exact is None else exact.rank,
        exact_score=None if exact is None else float(exact.score),
        red5_rank=None if red5 is None else red5.rank,
        red5_score=None if red5 is None else float(red5.score),
        red5_numbers=None if red5 is None else red5.red_numbers,
        matched_red_count_by_cutoff=tuple(
            (cutoff, counts[cutoff][6], counts[cutoff][5])
            for cutoff in EVALUATION_CUTOFFS
        ),
    )


def classify_evaluation_comparison(
    *,
    left_evaluation_contract: str,
    right_evaluation_contract: str,
    left_scoring_contract: str,
    right_scoring_contract: str,
    left_ranking_contract: object,
    right_ranking_contract: object,
    candidate_id_mismatch_count: int,
    score_mismatch_count: int,
    metric_mismatch_count: int,
) -> str:
    for name, value in (
        ("candidate_id_mismatch_count", candidate_id_mismatch_count),
        ("score_mismatch_count", score_mismatch_count),
        ("metric_mismatch_count", metric_mismatch_count),
    ):
        if not isinstance(value, Integral) or isinstance(value, bool) or int(value) < 0:
            raise EvaluationContractViolation(
                "evaluation_mismatch_count_invalid",
                "comparison mismatch counts must be non-negative integers",
                field=name,
                value=value,
            )
    for name, value in (
        ("left_evaluation_contract", left_evaluation_contract),
        ("right_evaluation_contract", right_evaluation_contract),
        ("left_scoring_contract", left_scoring_contract),
        ("right_scoring_contract", right_scoring_contract),
    ):
        if not isinstance(value, str) or not value.strip():
            raise EvaluationContractViolation(
                "evaluation_comparison_contract_missing",
                "comparison contract identities must be explicit",
                field=name,
            )
    if left_evaluation_contract != right_evaluation_contract:
        return EVALUATION_CONTRACT_DIFFERENCE
    if left_scoring_contract != right_scoring_contract:
        return SCORING_CONTRACT_DIFFERENCE
    if int(score_mismatch_count) > 0:
        return SCORE_REGRESSION
    if int(candidate_id_mismatch_count) > 0:
        if normalize_ranking_contract(left_ranking_contract) != normalize_ranking_contract(
            right_ranking_contract
        ):
            return RANKING_CONTRACT_DIFFERENCE
        return CANDIDATE_IDENTITY_REGRESSION
    if int(metric_mismatch_count) > 0:
        return EVALUATION_METRIC_REGRESSION
    return RANKING_COMPARISON_EXACT
