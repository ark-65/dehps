from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

from dehps.contracts import ContractRef, canonical_digest
from dehps.seven_red.diversified import (
    SEVEN_RED_DIVERSIFIED_TOP10_CONTRACT_V1,
    DiversifiedSevenRedTop10Snapshot,
    SevenRedDiversificationWeights,
)
from dehps.seven_red.domain import LINE_KEY, RESEARCH_ONLY
from dehps.seven_red.portfolio import (
    EQUAL_COST_PORTFOLIO_CONTRACT_V1,
    EqualCostPortfolioSettlement,
    EqualCostPortfolioSource,
    EqualCostPortfolioVerifier,
    EqualCostSixRedPortfolio70,
)
from dehps.seven_red.raw_top10 import (
    SEVEN_RED_RAW_TOP10_CONTRACT_V1,
    RawSevenRedTop10Snapshot,
)
from dehps.seven_red.scoring import (
    SEVEN_RED_SCORE_POOL_CONTRACT_V1,
    SevenRedScorePoolConfig,
    SevenRedScorePoolVerifier,
    SevenRedScoredCandidatePoolSnapshot,
)


SEVEN_RED_PARAMETER_GRID_VERSION = "seven_red_parameter_grid.v1"
SEVEN_RED_PARAMETER_ISSUE_EVALUATION_VERSION = (
    "seven_red_parameter_issue_evaluation.v1"
)
SEVEN_RED_INNER_SELECTION_PROTOCOL_VERSION = "seven_red_inner_selection_protocol.v1"
SEVEN_RED_INNER_SELECTION_SNAPSHOT_VERSION = "seven_red_inner_selection_snapshot.v1"
SEVEN_RED_INNER_SELECTION_METRIC = (
    "unique_ticket.lexicographic_exact6_issues_red5plus_issues_"
    "sum_best_match_unique_red5_tickets.v1"
)
SEVEN_RED_INNER_SELECTION_TIE_BREAK = "lower_parameter_digest.v1"


class SevenRedStrategyKind(str, Enum):
    RAW = "raw"
    DIVERSIFIED = "diversified"


SEVEN_RED_INNER_SELECTION_NORMATIVE_DEFINITION = {
    "contract": "seven-red-inner-selection.v1.0.0",
    "line_key": LINE_KEY,
    "research_only": RESEARCH_ONLY,
    "dependencies": {
        "score_pool": SEVEN_RED_SCORE_POOL_CONTRACT_V1.normative_identity(),
        "raw_top10": SEVEN_RED_RAW_TOP10_CONTRACT_V1.normative_identity(),
        "diversified_top10": (
            SEVEN_RED_DIVERSIFIED_TOP10_CONTRACT_V1.normative_identity()
        ),
        "equal_cost_portfolio": EQUAL_COST_PORTFOLIO_CONTRACT_V1.normative_identity(),
    },
    "parameter_grid": {
        "families": [kind.value for kind in SevenRedStrategyKind],
        "minimum_per_family": 2,
        "raw_weights": "forbidden",
        "diversified_weights": "one_explicit_primitive_vector",
        "defaults": None,
    },
    "issue_evaluation": {
        "source": "verified_score_pool_portfolio_and_settlement",
        "metric_source": "unique_ticket_hit_histogram_only",
        "paid_duplicate_amplification": "excluded",
    },
    "inner_window": {
        "minimum_issues": 20,
        "matrix": "complete_same_strictly_prior_issues_for_every_parameter",
        "metric": SEVEN_RED_INNER_SELECTION_METRIC,
        "tie_break": SEVEN_RED_INNER_SELECTION_TIE_BREAK,
    },
    "selection": {
        "families_selected_independently": True,
        "global_winner": None,
        "outer_outcome_input": None,
        "random_control_outcome_input": None,
    },
    "non_goals": [
        "no_recommended_or_default_grid",
        "no_outer_walk_forward_execution",
        "no_statistical_or_predictive_claim",
        "no_production_integration",
    ],
}

SEVEN_RED_INNER_SELECTION_GOLDEN_SUITE = {
    "suite": "seven_red_inner_selection_golden.v1",
    "metric_order": [
        "exact_red6_covered_issue_count",
        "red5_or_better_covered_issue_count",
        "sum_best_unique_matched_red_count",
        "total_unique_red5_ticket_count",
        "lower_parameter_digest",
    ],
    "minimum_inner_window_size": 20,
    "stochastic": False,
}

SEVEN_RED_INNER_SELECTION_CONTRACT_V1 = ContractRef.from_definition(
    family="seven-red-inner-selection",
    semantic_version="1.0.0",
    schema_version="dehps.seven-red-inner-selection.schema.v1",
    normative_definition=SEVEN_RED_INNER_SELECTION_NORMATIVE_DEFINITION,
    golden_suite=SEVEN_RED_INNER_SELECTION_GOLDEN_SUITE,
)


class SevenRedInnerSelectionViolation(ValueError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "context": dict(self.context)}


def _reject(code: str, message: str, **context: Any) -> None:
    raise SevenRedInnerSelectionViolation(code, message, **context)


def _require_digest(value: object, *, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _reject(
            "seven_red_inner_selection_digest_invalid",
            f"{field_name} must be a lowercase sha256 digest",
            field=field_name,
        )
    return value


def _require_issue(value: object, *, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 7
        or not value.isascii()
        or not value.isdigit()
    ):
        _reject(
            "seven_red_inner_selection_issue_invalid",
            f"{field_name} must be a seven-digit issue string",
            field=field_name,
        )
    return value


@dataclass(frozen=True)
class SevenRedStrategyParameter:
    strategy_kind: SevenRedStrategyKind
    score_pool_config: SevenRedScorePoolConfig
    diversification_weights: SevenRedDiversificationWeights | None
    parameter_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.strategy_kind, SevenRedStrategyKind):
            _reject("seven_red_parameter_kind_invalid", "strategy kind is invalid")
        if not isinstance(self.score_pool_config, SevenRedScorePoolConfig):
            _reject("seven_red_parameter_score_pool_config_invalid", "score-pool config is invalid")
        if self.strategy_kind is SevenRedStrategyKind.RAW:
            if self.diversification_weights is not None:
                _reject(
                    "seven_red_parameter_raw_weights_forbidden",
                    "Raw parameters cannot contain diversification weights",
                )
        elif not isinstance(self.diversification_weights, SevenRedDiversificationWeights):
            _reject(
                "seven_red_parameter_diversified_weights_required",
                "Diversified parameters require one primitive weight vector",
            )
        object.__setattr__(
            self,
            "parameter_digest",
            canonical_digest(
                self.identity_payload(), domain="dehps.seven-red.strategy-parameter.v1"
            ),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": SEVEN_RED_PARAMETER_GRID_VERSION,
            "strategy_kind": self.strategy_kind.value,
            "score_pool_config": self.score_pool_config.as_dict(),
            "diversification_weights": (
                None
                if self.diversification_weights is None
                else self.diversification_weights.as_dict()
            ),
            "default_policy": None,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "parameter_digest": self.parameter_digest}


@dataclass(frozen=True)
class SevenRedParameterGrid:
    parameters: tuple[SevenRedStrategyParameter, ...]
    grid_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.parameters, tuple)
            or any(
                not isinstance(parameter, SevenRedStrategyParameter)
                for parameter in self.parameters
            )
        ):
            _reject("seven_red_parameter_grid_invalid", "grid parameters are invalid")
        canonical = tuple(sorted(self.parameters, key=lambda row: row.parameter_digest))
        if self.parameters != canonical:
            _reject(
                "seven_red_parameter_grid_order_invalid",
                "grid parameters must be in canonical digest order",
            )
        digests = tuple(parameter.parameter_digest for parameter in self.parameters)
        if len(set(digests)) != len(digests):
            _reject("seven_red_parameter_grid_duplicate", "parameter digests must be unique")
        for kind in SevenRedStrategyKind:
            count = sum(parameter.strategy_kind is kind for parameter in self.parameters)
            if count < 2:
                _reject(
                    "seven_red_parameter_grid_family_underrepresented",
                    "grid requires at least two parameters per family",
                    strategy_kind=kind.value,
                    actual=count,
                )
        object.__setattr__(
            self,
            "grid_digest",
            canonical_digest(
                self.identity_payload(), domain="dehps.seven-red.parameter-grid.v1"
            ),
        )

    @classmethod
    def build(
        cls, parameters: Iterable[SevenRedStrategyParameter]
    ) -> SevenRedParameterGrid:
        return cls(tuple(sorted(tuple(parameters), key=lambda row: row.parameter_digest)))

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": SEVEN_RED_PARAMETER_GRID_VERSION,
            "line_key": LINE_KEY,
            "research_only": RESEARCH_ONLY,
            "contract": SEVEN_RED_INNER_SELECTION_CONTRACT_V1.normative_identity(),
            "parameters": [parameter.as_dict() for parameter in self.parameters],
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "grid_digest": self.grid_digest}


@dataclass(frozen=True)
class SevenRedParameterIssueEvaluation:
    parameter: SevenRedStrategyParameter
    target_issue: str
    source_history_latest_issue: str
    score_pool_snapshot_digest: str
    source_candidate_pool_digest: str
    source_strategy_artifact_digest: str
    portfolio_digest: str
    settlement_digest: str
    unique_ticket_hit_histogram: tuple[int, ...]
    exact_red6_covered: bool = field(init=False)
    red5_or_better_covered: bool = field(init=False)
    best_unique_matched_red_count: int = field(init=False)
    unique_red5_ticket_count: int = field(init=False)
    unique_ticket_count: int = field(init=False)
    evaluation_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.parameter, SevenRedStrategyParameter):
            _reject("seven_red_issue_evaluation_parameter_invalid", "parameter is invalid")
        target = _require_issue(self.target_issue, field_name="target_issue")
        latest = _require_issue(
            self.source_history_latest_issue, field_name="source_history_latest_issue"
        )
        if int(latest) >= int(target):
            _reject(
                "seven_red_issue_evaluation_chronology_invalid",
                "source history must end strictly before the evaluated issue",
            )
        for field_name in (
            "score_pool_snapshot_digest",
            "source_candidate_pool_digest",
            "source_strategy_artifact_digest",
            "portfolio_digest",
            "settlement_digest",
        ):
            _require_digest(getattr(self, field_name), field_name=field_name)
        histogram = self.unique_ticket_hit_histogram
        if (
            not isinstance(histogram, tuple)
            or len(histogram) != 7
            or any(
                not isinstance(value, int) or isinstance(value, bool) or value < 0
                for value in histogram
            )
            or not 1 <= sum(histogram) <= 70
        ):
            _reject(
                "seven_red_issue_evaluation_histogram_invalid",
                "unique-ticket histogram must contain seven non-negative counts totaling 1..70",
            )
        best = max(index for index, count in enumerate(histogram) if count)
        object.__setattr__(self, "exact_red6_covered", histogram[6] > 0)
        object.__setattr__(
            self, "red5_or_better_covered", histogram[5] + histogram[6] > 0
        )
        object.__setattr__(self, "best_unique_matched_red_count", best)
        object.__setattr__(self, "unique_red5_ticket_count", histogram[5])
        object.__setattr__(self, "unique_ticket_count", sum(histogram))
        object.__setattr__(
            self,
            "evaluation_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.seven-red.parameter-issue-evaluation.v1",
            ),
        )

    @classmethod
    def compile_raw(
        cls,
        *,
        parameter: SevenRedStrategyParameter,
        score_pool: SevenRedScoredCandidatePoolSnapshot,
        portfolio: EqualCostSixRedPortfolio70,
        settlement: EqualCostPortfolioSettlement,
    ) -> SevenRedParameterIssueEvaluation:
        if parameter.strategy_kind is not SevenRedStrategyKind.RAW:
            _reject("seven_red_issue_evaluation_family_mismatch", "expected a Raw parameter")
        cls._verify_common(parameter, score_pool, portfolio, settlement)
        raw_top10 = RawSevenRedTop10Snapshot.build(score_pool.candidate_pool)
        if portfolio.source_kind is not EqualCostPortfolioSource.RAW_SEVEN_RED_TOP10:
            _reject("seven_red_issue_evaluation_source_mismatch", "portfolio is not Raw Top10")
        EqualCostPortfolioVerifier().verify_raw(
            portfolio, score_pool=score_pool, raw_top10=raw_top10
        )
        return cls._from_verified_sources(
            parameter=parameter,
            score_pool=score_pool,
            source_strategy_artifact_digest=raw_top10.snapshot_digest,
            portfolio=portfolio,
            settlement=settlement,
        )

    @classmethod
    def compile_diversified(
        cls,
        *,
        parameter: SevenRedStrategyParameter,
        score_pool: SevenRedScoredCandidatePoolSnapshot,
        diversified_top10: DiversifiedSevenRedTop10Snapshot,
        portfolio: EqualCostSixRedPortfolio70,
        settlement: EqualCostPortfolioSettlement,
    ) -> SevenRedParameterIssueEvaluation:
        if parameter.strategy_kind is not SevenRedStrategyKind.DIVERSIFIED:
            _reject(
                "seven_red_issue_evaluation_family_mismatch",
                "expected a Diversified parameter",
            )
        cls._verify_common(parameter, score_pool, portfolio, settlement)
        if not isinstance(diversified_top10, DiversifiedSevenRedTop10Snapshot):
            _reject(
                "seven_red_issue_evaluation_diversified_source_invalid",
                "diversified source is invalid",
            )
        if diversified_top10.weights != parameter.diversification_weights:
            _reject(
                "seven_red_issue_evaluation_weight_mismatch",
                "diversified source weights do not match the parameter",
            )
        if (
            diversified_top10.source_audit.source_candidate_pool.artifact_digest
            != score_pool.candidate_pool.artifact_digest
        ):
            _reject(
                "seven_red_issue_evaluation_candidate_pool_mismatch",
                "diversified source does not bind the score-pool candidate list",
            )
        if portfolio.source_kind is not EqualCostPortfolioSource.DIVERSIFIED_SEVEN_RED_TOP10:
            _reject(
                "seven_red_issue_evaluation_source_mismatch",
                "portfolio is not Diversified Top10",
            )
        EqualCostPortfolioVerifier().verify_diversified(
            portfolio,
            score_pool=score_pool,
            diversified_top10=diversified_top10,
        )
        return cls._from_verified_sources(
            parameter=parameter,
            score_pool=score_pool,
            source_strategy_artifact_digest=diversified_top10.snapshot_digest,
            portfolio=portfolio,
            settlement=settlement,
        )

    @staticmethod
    def _verify_common(
        parameter: SevenRedStrategyParameter,
        score_pool: SevenRedScoredCandidatePoolSnapshot,
        portfolio: EqualCostSixRedPortfolio70,
        settlement: EqualCostPortfolioSettlement,
    ) -> None:
        if not isinstance(score_pool, SevenRedScoredCandidatePoolSnapshot):
            _reject("seven_red_issue_evaluation_score_pool_invalid", "score pool is invalid")
        SevenRedScorePoolVerifier().verify(score_pool)
        if score_pool.configuration != parameter.score_pool_config:
            _reject(
                "seven_red_issue_evaluation_config_mismatch",
                "score-pool M/P do not match the parameter",
            )
        if not isinstance(portfolio, EqualCostSixRedPortfolio70):
            _reject("seven_red_issue_evaluation_portfolio_invalid", "portfolio is invalid")
        if not isinstance(settlement, EqualCostPortfolioSettlement):
            _reject("seven_red_issue_evaluation_settlement_invalid", "settlement is invalid")
        if portfolio.target_issue != score_pool.target_issue:
            _reject(
                "seven_red_issue_evaluation_target_mismatch",
                "portfolio and score pool target issues differ",
            )
        if settlement.portfolio.portfolio_digest != portfolio.portfolio_digest:
            _reject(
                "seven_red_issue_evaluation_settlement_mismatch",
                "settlement does not bind the verified portfolio",
            )
        if settlement.actual_issue != score_pool.target_issue:
            _reject(
                "seven_red_issue_evaluation_settlement_issue_mismatch",
                "settlement issue does not match the score-pool target",
            )

    @classmethod
    def _from_verified_sources(
        cls,
        *,
        parameter: SevenRedStrategyParameter,
        score_pool: SevenRedScoredCandidatePoolSnapshot,
        source_strategy_artifact_digest: str,
        portfolio: EqualCostSixRedPortfolio70,
        settlement: EqualCostPortfolioSettlement,
    ) -> SevenRedParameterIssueEvaluation:
        return cls(
            parameter=parameter,
            target_issue=score_pool.target_issue,
            source_history_latest_issue=score_pool.source_vector.source_history_latest_issue,
            score_pool_snapshot_digest=score_pool.snapshot_digest,
            source_candidate_pool_digest=score_pool.candidate_pool.artifact_digest,
            source_strategy_artifact_digest=source_strategy_artifact_digest,
            portfolio_digest=portfolio.portfolio_digest,
            settlement_digest=settlement.settlement_digest,
            unique_ticket_hit_histogram=settlement.unique_ticket_hit_histogram,
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": SEVEN_RED_PARAMETER_ISSUE_EVALUATION_VERSION,
            "line_key": LINE_KEY,
            "research_only": RESEARCH_ONLY,
            "contract": SEVEN_RED_INNER_SELECTION_CONTRACT_V1.normative_identity(),
            "parameter_digest": self.parameter.parameter_digest,
            "strategy_kind": self.parameter.strategy_kind.value,
            "target_issue": self.target_issue,
            "source_history_latest_issue": self.source_history_latest_issue,
            "score_pool_snapshot_digest": self.score_pool_snapshot_digest,
            "source_candidate_pool_digest": self.source_candidate_pool_digest,
            "source_strategy_artifact_digest": self.source_strategy_artifact_digest,
            "portfolio_digest": self.portfolio_digest,
            "settlement_digest": self.settlement_digest,
            "metric_source": "unique_ticket_hit_histogram_only",
            "unique_ticket_hit_histogram": list(self.unique_ticket_hit_histogram),
            "exact_red6_covered": self.exact_red6_covered,
            "red5_or_better_covered": self.red5_or_better_covered,
            "best_unique_matched_red_count": self.best_unique_matched_red_count,
            "unique_red5_ticket_count": self.unique_red5_ticket_count,
            "unique_ticket_count": self.unique_ticket_count,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "evaluation_digest": self.evaluation_digest}


@dataclass(frozen=True)
class SevenRedInnerSelectionProtocol:
    inner_window_size: int
    metric_contract: str
    tie_break_contract: str
    protocol_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.inner_window_size, int)
            or isinstance(self.inner_window_size, bool)
            or self.inner_window_size < 20
        ):
            _reject(
                "seven_red_inner_window_size_invalid",
                "inner window size must be an explicit integer of at least 20",
            )
        if self.metric_contract != SEVEN_RED_INNER_SELECTION_METRIC:
            _reject("seven_red_inner_metric_invalid", "selection metric is not the frozen contract")
        if self.tie_break_contract != SEVEN_RED_INNER_SELECTION_TIE_BREAK:
            _reject("seven_red_inner_tie_break_invalid", "tie break is not the frozen contract")
        object.__setattr__(
            self,
            "protocol_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.seven-red.inner-selection-protocol.v1",
            ),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": SEVEN_RED_INNER_SELECTION_PROTOCOL_VERSION,
            "inner_window_size": self.inner_window_size,
            "window_policy": "explicit_complete_rolling_strictly_prior",
            "metric_contract": self.metric_contract,
            "tie_break_contract": self.tie_break_contract,
            "adaptive_stopping": None,
            "default_policy": None,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "protocol_digest": self.protocol_digest}


@dataclass(frozen=True)
class SevenRedParameterAggregate:
    parameter: SevenRedStrategyParameter
    inner_issues: tuple[str, ...]
    issue_evaluation_digests: tuple[str, ...]
    exact_red6_covered_issue_count: int
    red5_or_better_covered_issue_count: int
    sum_best_unique_matched_red_count: int
    total_unique_red5_ticket_count: int
    aggregate_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.parameter, SevenRedStrategyParameter):
            _reject("seven_red_parameter_aggregate_parameter_invalid", "parameter is invalid")
        if not self.inner_issues or len(self.inner_issues) != len(self.issue_evaluation_digests):
            _reject("seven_red_parameter_aggregate_rows_invalid", "aggregate rows are invalid")
        for digest in self.issue_evaluation_digests:
            _require_digest(digest, field_name="issue_evaluation_digest")
        values = self.metric_vector
        if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in values):
            _reject("seven_red_parameter_aggregate_metric_invalid", "aggregate metrics are invalid")
        object.__setattr__(
            self,
            "aggregate_digest",
            canonical_digest(
                self.identity_payload(), domain="dehps.seven-red.parameter-aggregate.v1"
            ),
        )

    @property
    def metric_vector(self) -> tuple[int, int, int, int]:
        return (
            self.exact_red6_covered_issue_count,
            self.red5_or_better_covered_issue_count,
            self.sum_best_unique_matched_red_count,
            self.total_unique_red5_ticket_count,
        )

    @classmethod
    def build(
        cls,
        parameter: SevenRedStrategyParameter,
        rows: tuple[SevenRedParameterIssueEvaluation, ...],
    ) -> SevenRedParameterAggregate:
        return cls(
            parameter=parameter,
            inner_issues=tuple(row.target_issue for row in rows),
            issue_evaluation_digests=tuple(row.evaluation_digest for row in rows),
            exact_red6_covered_issue_count=sum(row.exact_red6_covered for row in rows),
            red5_or_better_covered_issue_count=sum(
                row.red5_or_better_covered for row in rows
            ),
            sum_best_unique_matched_red_count=sum(
                row.best_unique_matched_red_count for row in rows
            ),
            total_unique_red5_ticket_count=sum(
                row.unique_red5_ticket_count for row in rows
            ),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "parameter_digest": self.parameter.parameter_digest,
            "strategy_kind": self.parameter.strategy_kind.value,
            "inner_issues": list(self.inner_issues),
            "issue_evaluation_digests": list(self.issue_evaluation_digests),
            "metric_vector": list(self.metric_vector),
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "aggregate_digest": self.aggregate_digest}


@dataclass(frozen=True)
class SevenRedFamilySelection:
    strategy_kind: SevenRedStrategyKind
    selected_parameter_digest: str
    winning_metric_vector: tuple[int, int, int, int]
    tied_parameter_digests: tuple[str, ...]
    selection_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.strategy_kind, SevenRedStrategyKind):
            _reject("seven_red_family_selection_kind_invalid", "strategy kind is invalid")
        selected = _require_digest(
            self.selected_parameter_digest, field_name="selected_parameter_digest"
        )
        if (
            not isinstance(self.tied_parameter_digests, tuple)
            or not self.tied_parameter_digests
            or tuple(sorted(self.tied_parameter_digests)) != self.tied_parameter_digests
            or len(set(self.tied_parameter_digests)) != len(self.tied_parameter_digests)
        ):
            _reject("seven_red_family_selection_ties_invalid", "tie evidence is invalid")
        for digest in self.tied_parameter_digests:
            _require_digest(digest, field_name="tied_parameter_digest")
        if selected != self.tied_parameter_digests[0]:
            _reject(
                "seven_red_family_selection_tie_break_invalid",
                "selected parameter must be the lower digest among metric ties",
            )
        object.__setattr__(
            self,
            "selection_digest",
            canonical_digest(
                self.identity_payload(), domain="dehps.seven-red.family-selection.v1"
            ),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "strategy_kind": self.strategy_kind.value,
            "selected_parameter_digest": self.selected_parameter_digest,
            "winning_metric_vector": list(self.winning_metric_vector),
            "tied_parameter_digests": list(self.tied_parameter_digests),
            "tie_break_contract": SEVEN_RED_INNER_SELECTION_TIE_BREAK,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "selection_digest": self.selection_digest}


@dataclass(frozen=True)
class SevenRedInnerSelectionSnapshot:
    outer_target_issue: str
    parameter_grid: SevenRedParameterGrid
    protocol: SevenRedInnerSelectionProtocol
    inner_issues: tuple[str, ...]
    evaluations: tuple[SevenRedParameterIssueEvaluation, ...]
    aggregates: tuple[SevenRedParameterAggregate, ...]
    family_selections: tuple[SevenRedFamilySelection, ...]
    snapshot_digest: str = field(init=False)

    def __post_init__(self) -> None:
        outer = _require_issue(self.outer_target_issue, field_name="outer_target_issue")
        if not isinstance(self.parameter_grid, SevenRedParameterGrid):
            _reject("seven_red_inner_snapshot_grid_invalid", "parameter grid is invalid")
        if not isinstance(self.protocol, SevenRedInnerSelectionProtocol):
            _reject("seven_red_inner_snapshot_protocol_invalid", "protocol is invalid")
        if (
            not isinstance(self.inner_issues, tuple)
            or len(self.inner_issues) != self.protocol.inner_window_size
            or tuple(sorted(set(self.inner_issues), key=int)) != self.inner_issues
        ):
            _reject(
                "seven_red_inner_snapshot_issue_window_invalid",
                "inner issues must be the explicit strictly increasing window",
            )
        for issue in self.inner_issues:
            _require_issue(issue, field_name="inner_issue")
            if int(issue) >= int(outer):
                _reject(
                    "seven_red_inner_snapshot_chronology_invalid",
                    "every inner issue must be strictly before the outer target",
                )
        expected_cells = {
            (parameter.parameter_digest, issue)
            for parameter in self.parameter_grid.parameters
            for issue in self.inner_issues
        }
        actual_cells = [
            (row.parameter.parameter_digest, row.target_issue) for row in self.evaluations
        ]
        if len(set(actual_cells)) != len(actual_cells):
            _reject("seven_red_inner_snapshot_duplicate_cell", "evaluation matrix has duplicate cells")
        if set(actual_cells) != expected_cells:
            _reject(
                "seven_red_inner_snapshot_incomplete_matrix",
                "evaluation matrix must contain every parameter on exactly the common issues",
                missing=len(expected_cells - set(actual_cells)),
                extra=len(set(actual_cells) - expected_cells),
            )
        canonical_evaluations = tuple(
            sorted(
                self.evaluations,
                key=lambda row: (row.parameter.parameter_digest, int(row.target_issue)),
            )
        )
        if self.evaluations != canonical_evaluations:
            _reject("seven_red_inner_snapshot_row_order_invalid", "evaluation rows are not canonical")
        expected_aggregates = _build_aggregates(
            self.parameter_grid, self.inner_issues, self.evaluations
        )
        if self.aggregates != expected_aggregates:
            _reject("seven_red_inner_snapshot_aggregate_mismatch", "aggregate rows do not replay")
        expected_selections = _build_family_selections(expected_aggregates)
        if self.family_selections != expected_selections:
            _reject("seven_red_inner_snapshot_selection_mismatch", "family selections do not replay")
        object.__setattr__(
            self,
            "snapshot_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.seven-red.inner-selection-snapshot.v1",
            ),
        )

    @classmethod
    def build(
        cls,
        *,
        outer_target_issue: str,
        parameter_grid: SevenRedParameterGrid,
        protocol: SevenRedInnerSelectionProtocol,
        inner_issues: Iterable[str],
        evaluations: Iterable[SevenRedParameterIssueEvaluation],
    ) -> SevenRedInnerSelectionSnapshot:
        issues = tuple(inner_issues)
        rows = tuple(
            sorted(
                tuple(evaluations),
                key=lambda row: (row.parameter.parameter_digest, int(row.target_issue)),
            )
        )
        aggregates = _build_aggregates(parameter_grid, issues, rows)
        selections = _build_family_selections(aggregates)
        return cls(
            outer_target_issue=outer_target_issue,
            parameter_grid=parameter_grid,
            protocol=protocol,
            inner_issues=issues,
            evaluations=rows,
            aggregates=aggregates,
            family_selections=selections,
        )

    def selected_parameter_digest(self, kind: SevenRedStrategyKind) -> str:
        for selection in self.family_selections:
            if selection.strategy_kind is kind:
                return selection.selected_parameter_digest
        raise AssertionError("family selection invariant violated")

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": SEVEN_RED_INNER_SELECTION_SNAPSHOT_VERSION,
            "line_key": LINE_KEY,
            "research_only": RESEARCH_ONLY,
            "contract": SEVEN_RED_INNER_SELECTION_CONTRACT_V1.normative_identity(),
            "outer_target_issue": self.outer_target_issue,
            "outer_outcome": None,
            "random_control_outcomes": None,
            "parameter_grid_digest": self.parameter_grid.grid_digest,
            "protocol": self.protocol.as_dict(),
            "inner_issues": list(self.inner_issues),
            "evaluations": [row.as_dict() for row in self.evaluations],
            "aggregates": [row.as_dict() for row in self.aggregates],
            "family_selections": [row.as_dict() for row in self.family_selections],
            "global_winner": None,
            "promotion_status": None,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "snapshot_digest": self.snapshot_digest}


def _build_aggregates(
    grid: SevenRedParameterGrid,
    inner_issues: tuple[str, ...],
    evaluations: tuple[SevenRedParameterIssueEvaluation, ...],
) -> tuple[SevenRedParameterAggregate, ...]:
    by_cell = {
        (row.parameter.parameter_digest, row.target_issue): row for row in evaluations
    }
    return tuple(
        SevenRedParameterAggregate.build(
            parameter,
            tuple(by_cell[(parameter.parameter_digest, issue)] for issue in inner_issues),
        )
        for parameter in grid.parameters
        if all((parameter.parameter_digest, issue) in by_cell for issue in inner_issues)
    )


def _build_family_selections(
    aggregates: tuple[SevenRedParameterAggregate, ...],
) -> tuple[SevenRedFamilySelection, ...]:
    selections: list[SevenRedFamilySelection] = []
    for kind in SevenRedStrategyKind:
        family = tuple(row for row in aggregates if row.parameter.strategy_kind is kind)
        if not family:
            continue
        winning_metric = max(row.metric_vector for row in family)
        tied = tuple(
            sorted(
                row.parameter.parameter_digest
                for row in family
                if row.metric_vector == winning_metric
            )
        )
        selections.append(
            SevenRedFamilySelection(
                strategy_kind=kind,
                selected_parameter_digest=tied[0],
                winning_metric_vector=winning_metric,
                tied_parameter_digests=tied,
            )
        )
    return tuple(selections)


class SevenRedInnerSelectionVerifier:
    def verify(self, snapshot: SevenRedInnerSelectionSnapshot) -> None:
        if not isinstance(snapshot, SevenRedInnerSelectionSnapshot):
            _reject("seven_red_inner_snapshot_type_invalid", "snapshot is invalid")
        replay = SevenRedInnerSelectionSnapshot.build(
            outer_target_issue=snapshot.outer_target_issue,
            parameter_grid=snapshot.parameter_grid,
            protocol=snapshot.protocol,
            inner_issues=snapshot.inner_issues,
            evaluations=snapshot.evaluations,
        )
        if replay.snapshot_digest != snapshot.snapshot_digest:
            _reject(
                "seven_red_inner_snapshot_replay_mismatch",
                "snapshot does not match deterministic replay",
                expected=replay.snapshot_digest,
                actual=snapshot.snapshot_digest,
            )
