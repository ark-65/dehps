from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable

from dehps.contracts import ContractRef, canonical_digest
from dehps.seven_red.diversified import (
    DiversifiedSevenRedTop10Snapshot,
)
from dehps.seven_red.domain import LINE_KEY, RESEARCH_ONLY, SixRedCombination
from dehps.seven_red.inner_selection import (
    SEVEN_RED_INNER_SELECTION_CONTRACT_V1,
    SevenRedInnerSelectionSnapshot,
    SevenRedInnerSelectionVerifier,
    SevenRedStrategyKind,
)
from dehps.seven_red.portfolio import (
    EQUAL_COST_PORTFOLIO_CONTRACT_V1,
    EQUAL_COST_TICKET_BUDGET,
    EqualCostPortfolioSettlement,
    EqualCostPortfolioVerifier,
    EqualCostSixRedPortfolio70,
)
from dehps.seven_red.random_control import (
    RANDOM_CONTROL_CONTRACT_V1,
    RandomControlCohortSettlement,
    RandomControlCohortSnapshot,
    RandomControlCohortVerifier,
    RandomControlKind,
    RandomControlSeedPolicy,
)
from dehps.seven_red.raw_top10 import RawSevenRedTop10Snapshot
from dehps.seven_red.scoring import (
    SevenRedScorePoolVerifier,
    SevenRedScoredCandidatePoolSnapshot,
)


SEVEN_RED_OUTER_TRIAL_VERSION = "seven_red_outer_trial.v1"
SEVEN_RED_WALK_FORWARD_PROTOCOL_VERSION = "seven_red_walk_forward_protocol.v1"
SEVEN_RED_WALK_FORWARD_SNAPSHOT_VERSION = "seven_red_walk_forward_snapshot.v1"
SEVEN_RED_MATCHED_RANDOM_POLICY = "family_selected_score_pool_matched.v1"
SEVEN_RED_COMPLETE_ARM_POLICY = (
    "raw_diversified_six_top70_and_two_controls_per_family_seed.v1"
)
SEVEN_RED_OUTER_EVIDENCE_POLICY = "per_target_per_arm_unaggregated_histograms.v1"
MINIMUM_OUTER_TARGET_COUNT = 30


class SevenRedOuterArmKind(str, Enum):
    RAW_TOP10 = "raw_top10"
    DIVERSIFIED_TOP10 = "diversified_top10"
    SIX_RED_TOP70 = "six_red_top70"


SEVEN_RED_WALK_FORWARD_NORMATIVE_DEFINITION = {
    "contract": "seven-red-walk-forward.v1.0.0",
    "line_key": LINE_KEY,
    "research_only": RESEARCH_ONLY,
    "dependencies": {
        "inner_selection": SEVEN_RED_INNER_SELECTION_CONTRACT_V1.normative_identity(),
        "equal_cost": EQUAL_COST_PORTFOLIO_CONTRACT_V1.normative_identity(),
        "random_control": RANDOM_CONTROL_CONTRACT_V1.normative_identity(),
    },
    "protocol": {
        "minimum_outer_targets": MINIMUM_OUTER_TARGET_COUNT,
        "target_order": "explicit_strictly_increasing_unique_issue_tuple",
        "paid_ticket_budget_per_portfolio": EQUAL_COST_TICKET_BUDGET,
        "random_control_policy": SEVEN_RED_MATCHED_RANDOM_POLICY,
        "complete_arm_policy": SEVEN_RED_COMPLETE_ARM_POLICY,
        "evidence_policy": SEVEN_RED_OUTER_EVIDENCE_POLICY,
        "defaults": None,
    },
    "source_binding": {
        "selected_parameters": "independent_raw_and_diversified_inner_winners",
        "score_vector": "exactly_shared_by_raw_diversified_and_six_top70",
        "history": "strictly_pre_target",
        "random_controls": "one_complete_cohort_per_selected_family_score_pool",
    },
    "outcome_binding": {
        "stage": "post_outcome_outer_trial",
        "common_actual": "same_issue_and_six_red_outcome_for_every_arm",
        "pre_outcome_interfaces": "do_not_accept_actual",
    },
    "snapshot": {
        "target_matrix": "exactly_one_complete_trial_per_protocol_target",
        "cross_target_aggregation": None,
        "winner": None,
        "statistical_conclusion": None,
    },
    "non_goals": [
        "no_actual_historical_run",
        "no_statistical_test_or_effect_claim",
        "no_seed_selection_or_row_pooling",
        "no_evidence_or_hypothesis_decision",
        "no_betting_or_production_action",
    ],
}

SEVEN_RED_WALK_FORWARD_GOLDEN_SUITE = {
    "suite": "seven_red_walk_forward_golden.v1",
    "minimum_outer_targets": MINIMUM_OUTER_TARGET_COUNT,
    "strategy_arm_order": [kind.value for kind in SevenRedOuterArmKind],
    "matched_family_order": [
        SevenRedStrategyKind.RAW.value,
        SevenRedStrategyKind.DIVERSIFIED.value,
    ],
    "stochastic": False,
}

SEVEN_RED_WALK_FORWARD_CONTRACT_V1 = ContractRef.from_definition(
    family="seven-red-walk-forward",
    semantic_version="1.0.0",
    schema_version="dehps.seven-red-walk-forward.schema.v1",
    normative_definition=SEVEN_RED_WALK_FORWARD_NORMATIVE_DEFINITION,
    golden_suite=SEVEN_RED_WALK_FORWARD_GOLDEN_SUITE,
)


class SevenRedWalkForwardViolation(ValueError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "context": dict(self.context)}


def _reject(code: str, message: str, **context: Any) -> None:
    raise SevenRedWalkForwardViolation(code, message, **context)


def _require_digest(value: object, *, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _reject(
            "seven_red_walk_forward_digest_invalid",
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
            "seven_red_walk_forward_issue_invalid",
            f"{field_name} must be a seven-digit issue string",
            field=field_name,
        )
    return value


def _require_histogram(
    value: object,
    *,
    field_name: str,
    expected_total: int,
) -> tuple[int, ...]:
    if (
        not isinstance(value, tuple)
        or len(value) != 7
        or any(
            not isinstance(item, int) or isinstance(item, bool) or item < 0
            for item in value
        )
        or sum(value) != expected_total
    ):
        _reject(
            "seven_red_walk_forward_histogram_invalid",
            f"{field_name} must contain seven counts with the expected total",
            field=field_name,
            expected_total=expected_total,
        )
    return value


@dataclass(frozen=True)
class SevenRedWalkForwardProtocol:
    outer_target_issues: tuple[str, ...]
    seed_policy: RandomControlSeedPolicy
    paid_ticket_budget: int
    matched_random_policy: str
    complete_arm_policy: str
    evidence_policy: str
    protocol_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.outer_target_issues, tuple)
            or len(self.outer_target_issues) < MINIMUM_OUTER_TARGET_COUNT
        ):
            _reject(
                "seven_red_walk_forward_target_count_invalid",
                "protocol requires at least 30 explicit outer targets",
            )
        for issue in self.outer_target_issues:
            _require_issue(issue, field_name="outer_target_issue")
        if tuple(sorted(set(self.outer_target_issues), key=int)) != self.outer_target_issues:
            _reject(
                "seven_red_walk_forward_target_order_invalid",
                "outer targets must be unique and strictly increasing",
            )
        if not isinstance(self.seed_policy, RandomControlSeedPolicy):
            _reject("seven_red_walk_forward_seed_policy_invalid", "seed policy is invalid")
        if self.paid_ticket_budget != EQUAL_COST_TICKET_BUDGET:
            _reject(
                "seven_red_walk_forward_budget_invalid",
                "paid ticket budget must equal the frozen 70-slot contract",
            )
        if self.matched_random_policy != SEVEN_RED_MATCHED_RANDOM_POLICY:
            _reject(
                "seven_red_walk_forward_random_policy_invalid",
                "matched random policy is not the frozen contract",
            )
        if self.complete_arm_policy != SEVEN_RED_COMPLETE_ARM_POLICY:
            _reject(
                "seven_red_walk_forward_arm_policy_invalid",
                "complete arm policy is not the frozen contract",
            )
        if self.evidence_policy != SEVEN_RED_OUTER_EVIDENCE_POLICY:
            _reject(
                "seven_red_walk_forward_evidence_policy_invalid",
                "evidence policy is not the frozen contract",
            )
        object.__setattr__(
            self,
            "protocol_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.seven-red.walk-forward-protocol.v1",
            ),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": SEVEN_RED_WALK_FORWARD_PROTOCOL_VERSION,
            "outer_target_issues": list(self.outer_target_issues),
            "seed_policy": self.seed_policy.as_dict(),
            "paid_ticket_budget": self.paid_ticket_budget,
            "matched_random_policy": self.matched_random_policy,
            "complete_arm_policy": self.complete_arm_policy,
            "evidence_policy": self.evidence_policy,
            "statistical_method": None,
            "decision_threshold": None,
            "default_policy": None,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "protocol_digest": self.protocol_digest}


@dataclass(frozen=True)
class SevenRedOuterStrategyArmEvidence:
    arm_kind: SevenRedOuterArmKind
    parameter_digest: str | None
    source_vector_digest: str
    source_score_pool_snapshot_digest: str | None
    source_strategy_artifact_digest: str
    portfolio_digest: str
    settlement_digest: str
    paid_ticket_count: int
    unique_ticket_count: int
    duplicate_slot_count: int
    slot_hit_histogram: tuple[int, ...]
    unique_ticket_hit_histogram: tuple[int, ...]
    arm_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.arm_kind, SevenRedOuterArmKind):
            _reject("seven_red_outer_arm_kind_invalid", "strategy arm kind is invalid")
        _require_digest(self.source_vector_digest, field_name="source_vector_digest")
        if self.arm_kind is SevenRedOuterArmKind.SIX_RED_TOP70:
            if self.parameter_digest is not None or self.source_score_pool_snapshot_digest is not None:
                _reject(
                    "seven_red_outer_arm_parameter_binding_invalid",
                    "six-red Top70 cannot bind a seven-red parameter or score pool",
                )
            if self.unique_ticket_count != 70 or self.duplicate_slot_count != 0:
                _reject(
                    "seven_red_outer_arm_unique70_invalid",
                    "six-red Top70 must contain 70 unique paid tickets",
                )
        else:
            _require_digest(self.parameter_digest, field_name="parameter_digest")
            _require_digest(
                self.source_score_pool_snapshot_digest,
                field_name="source_score_pool_snapshot_digest",
            )
            if self.arm_kind is SevenRedOuterArmKind.DIVERSIFIED_TOP10 and (
                self.unique_ticket_count != 70 or self.duplicate_slot_count != 0
            ):
                _reject(
                    "seven_red_outer_arm_unique70_invalid",
                    "Diversified Top10 must contain 70 unique paid tickets",
                )
        for field_name in (
            "source_strategy_artifact_digest",
            "portfolio_digest",
            "settlement_digest",
        ):
            _require_digest(getattr(self, field_name), field_name=field_name)
        if (
            self.paid_ticket_count != EQUAL_COST_TICKET_BUDGET
            or self.unique_ticket_count < 1
            or self.unique_ticket_count > self.paid_ticket_count
            or self.duplicate_slot_count != self.paid_ticket_count - self.unique_ticket_count
        ):
            _reject(
                "seven_red_outer_arm_cost_invalid",
                "strategy arm paid, unique, and duplicate counts are inconsistent",
            )
        _require_histogram(
            self.slot_hit_histogram,
            field_name="slot_hit_histogram",
            expected_total=self.paid_ticket_count,
        )
        _require_histogram(
            self.unique_ticket_hit_histogram,
            field_name="unique_ticket_hit_histogram",
            expected_total=self.unique_ticket_count,
        )
        object.__setattr__(
            self,
            "arm_digest",
            canonical_digest(
                self.identity_payload(), domain="dehps.seven-red.outer-strategy-arm.v1"
            ),
        )

    @classmethod
    def from_verified(
        cls,
        *,
        arm_kind: SevenRedOuterArmKind,
        parameter_digest: str | None,
        source_vector_digest: str,
        source_score_pool_snapshot_digest: str | None,
        source_strategy_artifact_digest: str,
        portfolio: EqualCostSixRedPortfolio70,
        settlement: EqualCostPortfolioSettlement,
    ) -> SevenRedOuterStrategyArmEvidence:
        return cls(
            arm_kind=arm_kind,
            parameter_digest=parameter_digest,
            source_vector_digest=source_vector_digest,
            source_score_pool_snapshot_digest=source_score_pool_snapshot_digest,
            source_strategy_artifact_digest=source_strategy_artifact_digest,
            portfolio_digest=portfolio.portfolio_digest,
            settlement_digest=settlement.settlement_digest,
            paid_ticket_count=len(portfolio.slots),
            unique_ticket_count=portfolio.unique_ticket_count,
            duplicate_slot_count=portfolio.duplicate_slot_count,
            slot_hit_histogram=settlement.slot_hit_histogram,
            unique_ticket_hit_histogram=settlement.unique_ticket_hit_histogram,
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "arm_kind": self.arm_kind.value,
            "parameter_digest": self.parameter_digest,
            "source_vector_digest": self.source_vector_digest,
            "source_score_pool_snapshot_digest": self.source_score_pool_snapshot_digest,
            "source_strategy_artifact_digest": self.source_strategy_artifact_digest,
            "portfolio_digest": self.portfolio_digest,
            "settlement_digest": self.settlement_digest,
            "paid_ticket_count": self.paid_ticket_count,
            "unique_ticket_count": self.unique_ticket_count,
            "duplicate_slot_count": self.duplicate_slot_count,
            "slot_hit_histogram": list(self.slot_hit_histogram),
            "unique_ticket_hit_histogram": list(self.unique_ticket_hit_histogram),
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "arm_digest": self.arm_digest}


@dataclass(frozen=True)
class SevenRedOuterRandomRowEvidence:
    seed_digest: str
    control_kind: RandomControlKind
    portfolio_digest: str
    settlement_row_digest: str
    paid_ticket_count: int
    unique_ticket_count: int
    duplicate_slot_count: int
    slot_hit_histogram: tuple[int, ...]
    unique_ticket_hit_histogram: tuple[int, ...]
    evidence_digest: str = field(init=False)

    def __post_init__(self) -> None:
        for field_name in ("seed_digest", "portfolio_digest", "settlement_row_digest"):
            _require_digest(getattr(self, field_name), field_name=field_name)
        if not isinstance(self.control_kind, RandomControlKind):
            _reject("seven_red_outer_random_kind_invalid", "random control kind is invalid")
        if (
            self.paid_ticket_count != EQUAL_COST_TICKET_BUDGET
            or not 1 <= self.unique_ticket_count <= self.paid_ticket_count
            or self.duplicate_slot_count != self.paid_ticket_count - self.unique_ticket_count
        ):
            _reject(
                "seven_red_outer_random_cost_invalid",
                "random-control paid, unique, and duplicate counts are inconsistent",
            )
        if self.control_kind is RandomControlKind.UNIFORM_LEGAL and (
            self.unique_ticket_count != 70 or self.duplicate_slot_count != 0
        ):
            _reject(
                "seven_red_outer_random_unique70_invalid",
                "uniform-legal controls must contain 70 unique tickets",
            )
        _require_histogram(
            self.slot_hit_histogram,
            field_name="slot_hit_histogram",
            expected_total=self.paid_ticket_count,
        )
        _require_histogram(
            self.unique_ticket_hit_histogram,
            field_name="unique_ticket_hit_histogram",
            expected_total=self.unique_ticket_count,
        )
        object.__setattr__(
            self,
            "evidence_digest",
            canonical_digest(
                self.identity_payload(), domain="dehps.seven-red.outer-random-row.v1"
            ),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "seed_digest": self.seed_digest,
            "control_kind": self.control_kind.value,
            "portfolio_digest": self.portfolio_digest,
            "settlement_row_digest": self.settlement_row_digest,
            "paid_ticket_count": self.paid_ticket_count,
            "unique_ticket_count": self.unique_ticket_count,
            "duplicate_slot_count": self.duplicate_slot_count,
            "slot_hit_histogram": list(self.slot_hit_histogram),
            "unique_ticket_hit_histogram": list(self.unique_ticket_hit_histogram),
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "evidence_digest": self.evidence_digest}


@dataclass(frozen=True)
class SevenRedMatchedRandomEvidence:
    matched_family: SevenRedStrategyKind
    source_score_pool_snapshot_digest: str
    seed_policy: RandomControlSeedPolicy
    cohort_digest: str
    settlement_digest: str
    rows: tuple[SevenRedOuterRandomRowEvidence, ...]
    evidence_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if self.matched_family not in (
            SevenRedStrategyKind.RAW,
            SevenRedStrategyKind.DIVERSIFIED,
        ):
            _reject(
                "seven_red_matched_random_family_invalid",
                "random evidence must match Raw or Diversified",
            )
        if not isinstance(self.seed_policy, RandomControlSeedPolicy):
            _reject("seven_red_matched_random_seed_policy_invalid", "seed policy is invalid")
        for field_name in (
            "source_score_pool_snapshot_digest",
            "cohort_digest",
            "settlement_digest",
        ):
            _require_digest(getattr(self, field_name), field_name=field_name)
        expected_keys = tuple(
            (seed, kind)
            for seed in self.seed_policy.seed_digests
            for kind in (RandomControlKind.RANDOM_FROM_POOL, RandomControlKind.UNIFORM_LEGAL)
        )
        actual_keys = tuple((row.seed_digest, row.control_kind) for row in self.rows)
        if actual_keys != expected_keys:
            _reject(
                "seven_red_matched_random_coverage_invalid",
                "matched random evidence must retain every seed and both controls",
            )
        object.__setattr__(
            self,
            "evidence_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.seven-red.matched-random-evidence.v1",
            ),
        )

    @classmethod
    def from_verified(
        cls,
        *,
        matched_family: SevenRedStrategyKind,
        cohort: RandomControlCohortSnapshot,
        settlement: RandomControlCohortSettlement,
    ) -> SevenRedMatchedRandomEvidence:
        rows = tuple(
            SevenRedOuterRandomRowEvidence(
                seed_digest=portfolio.seed_digest,
                control_kind=portfolio.control_kind,
                portfolio_digest=portfolio.portfolio_digest,
                settlement_row_digest=row.row_digest,
                paid_ticket_count=len(portfolio.slots),
                unique_ticket_count=portfolio.unique_ticket_count,
                duplicate_slot_count=portfolio.duplicate_slot_count,
                slot_hit_histogram=row.slot_hit_histogram,
                unique_ticket_hit_histogram=row.unique_ticket_hit_histogram,
            )
            for portfolio, row in zip(cohort.portfolios, settlement.rows, strict=True)
        )
        return cls(
            matched_family=matched_family,
            source_score_pool_snapshot_digest=cohort.source_score_pool.snapshot_digest,
            seed_policy=cohort.seed_policy,
            cohort_digest=cohort.cohort_digest,
            settlement_digest=settlement.settlement_digest,
            rows=rows,
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "matched_family": self.matched_family.value,
            "source_score_pool_snapshot_digest": self.source_score_pool_snapshot_digest,
            "seed_policy": self.seed_policy.as_dict(),
            "cohort_digest": self.cohort_digest,
            "settlement_digest": self.settlement_digest,
            "rows": [row.as_dict() for row in self.rows],
            "selection_policy": "no_best_seed_or_control",
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "evidence_digest": self.evidence_digest}


@dataclass(frozen=True)
class SevenRedOuterTrial:
    target_issue: str
    protocol_digest: str
    inner_selection_snapshot_digest: str
    source_history_latest_issue: str
    source_vector_digest: str
    actual: SixRedCombination
    strategy_arms: tuple[SevenRedOuterStrategyArmEvidence, ...]
    matched_random_evidence: tuple[SevenRedMatchedRandomEvidence, ...]
    trial_digest: str = field(init=False)

    def __post_init__(self) -> None:
        target = _require_issue(self.target_issue, field_name="target_issue")
        latest = _require_issue(
            self.source_history_latest_issue, field_name="source_history_latest_issue"
        )
        if int(latest) >= int(target):
            _reject(
                "seven_red_outer_trial_chronology_invalid",
                "source history must end strictly before the outer target",
            )
        for field_name in (
            "protocol_digest",
            "inner_selection_snapshot_digest",
            "source_vector_digest",
        ):
            _require_digest(getattr(self, field_name), field_name=field_name)
        if not isinstance(self.actual, SixRedCombination):
            _reject("seven_red_outer_trial_actual_invalid", "actual outcome is invalid")
        expected_arm_order = tuple(SevenRedOuterArmKind)
        if tuple(row.arm_kind for row in self.strategy_arms) != expected_arm_order:
            _reject(
                "seven_red_outer_trial_strategy_coverage_invalid",
                "trial must retain all three strategy arms in canonical order",
            )
        if any(row.source_vector_digest != self.source_vector_digest for row in self.strategy_arms):
            _reject(
                "seven_red_outer_trial_source_vector_mismatch",
                "all strategy arms must share the exact score vector",
            )
        expected_families = (
            SevenRedStrategyKind.RAW,
            SevenRedStrategyKind.DIVERSIFIED,
        )
        if tuple(row.matched_family for row in self.matched_random_evidence) != expected_families:
            _reject(
                "seven_red_outer_trial_random_coverage_invalid",
                "trial must retain both family-matched random cohorts",
            )
        if (
            self.matched_random_evidence[0].source_score_pool_snapshot_digest
            != self.strategy_arms[0].source_score_pool_snapshot_digest
            or self.matched_random_evidence[1].source_score_pool_snapshot_digest
            != self.strategy_arms[1].source_score_pool_snapshot_digest
        ):
            _reject(
                "seven_red_outer_trial_random_source_mismatch",
                "each random cohort must bind its family strategy score pool",
            )
        if (
            self.matched_random_evidence[0].seed_policy
            != self.matched_random_evidence[1].seed_policy
        ):
            _reject(
                "seven_red_outer_trial_random_seed_policy_mismatch",
                "both family-matched cohorts must share one seed policy",
            )
        object.__setattr__(
            self,
            "trial_digest",
            canonical_digest(
                self.identity_payload(), domain="dehps.seven-red.outer-trial.v1"
            ),
        )

    @classmethod
    def compile(
        cls,
        *,
        protocol: SevenRedWalkForwardProtocol,
        inner_selection: SevenRedInnerSelectionSnapshot,
        raw_score_pool: SevenRedScoredCandidatePoolSnapshot,
        diversified_score_pool: SevenRedScoredCandidatePoolSnapshot,
        diversified_top10: DiversifiedSevenRedTop10Snapshot,
        raw_portfolio: EqualCostSixRedPortfolio70,
        diversified_portfolio: EqualCostSixRedPortfolio70,
        six_red_top70_portfolio: EqualCostSixRedPortfolio70,
        raw_settlement: EqualCostPortfolioSettlement,
        diversified_settlement: EqualCostPortfolioSettlement,
        six_red_top70_settlement: EqualCostPortfolioSettlement,
        raw_random_cohort: RandomControlCohortSnapshot,
        diversified_random_cohort: RandomControlCohortSnapshot,
        raw_random_settlement: RandomControlCohortSettlement,
        diversified_random_settlement: RandomControlCohortSettlement,
    ) -> SevenRedOuterTrial:
        if not isinstance(protocol, SevenRedWalkForwardProtocol):
            _reject("seven_red_outer_trial_protocol_invalid", "protocol is invalid")
        if not isinstance(inner_selection, SevenRedInnerSelectionSnapshot):
            _reject("seven_red_outer_trial_inner_selection_invalid", "inner selection is invalid")
        SevenRedInnerSelectionVerifier().verify(inner_selection)
        target = inner_selection.outer_target_issue
        if target not in protocol.outer_target_issues:
            _reject(
                "seven_red_outer_trial_target_not_in_protocol",
                "inner-selection target is not in the walk-forward protocol",
            )
        for score_pool in (raw_score_pool, diversified_score_pool):
            if not isinstance(score_pool, SevenRedScoredCandidatePoolSnapshot):
                _reject("seven_red_outer_trial_score_pool_invalid", "score pool is invalid")
            SevenRedScorePoolVerifier().verify(score_pool)
            if score_pool.target_issue != target:
                _reject(
                    "seven_red_outer_trial_score_pool_target_mismatch",
                    "selected score-pool target does not match the trial",
                )
        raw_parameter = _selected_parameter(inner_selection, SevenRedStrategyKind.RAW)
        diversified_parameter = _selected_parameter(
            inner_selection, SevenRedStrategyKind.DIVERSIFIED
        )
        if raw_score_pool.configuration != raw_parameter.score_pool_config:
            _reject(
                "seven_red_outer_trial_raw_parameter_mismatch",
                "Raw score-pool M/P do not match the selected parameter",
            )
        if diversified_score_pool.configuration != diversified_parameter.score_pool_config:
            _reject(
                "seven_red_outer_trial_diversified_parameter_mismatch",
                "Diversified score-pool M/P do not match the selected parameter",
            )
        raw_vector = raw_score_pool.source_vector
        diversified_vector = diversified_score_pool.source_vector
        if raw_vector.vector_digest != diversified_vector.vector_digest:
            _reject(
                "seven_red_outer_trial_shared_vector_mismatch",
                "Raw and Diversified score pools must share the exact score vector",
            )
        raw_top10 = RawSevenRedTop10Snapshot.build(raw_score_pool.candidate_pool)
        if not isinstance(diversified_top10, DiversifiedSevenRedTop10Snapshot):
            _reject(
                "seven_red_outer_trial_diversified_source_invalid",
                "diversified Top10 source is invalid",
            )
        if diversified_top10.weights != diversified_parameter.diversification_weights:
            _reject(
                "seven_red_outer_trial_diversified_weight_mismatch",
                "Diversified weights do not match the selected parameter",
            )
        if (
            diversified_top10.source_audit.source_candidate_pool.artifact_digest
            != diversified_score_pool.candidate_pool.artifact_digest
        ):
            _reject(
                "seven_red_outer_trial_diversified_source_mismatch",
                "Diversified Top10 does not bind the selected score pool",
            )
        verifier = EqualCostPortfolioVerifier()
        verifier.verify_raw(raw_portfolio, score_pool=raw_score_pool, raw_top10=raw_top10)
        verifier.verify_diversified(
            diversified_portfolio,
            score_pool=diversified_score_pool,
            diversified_top10=diversified_top10,
        )
        verifier.verify_six_red_top70(
            six_red_top70_portfolio,
            source_vector=raw_vector,
            target_issue=target,
        )
        _verify_strategy_settlement(raw_portfolio, raw_settlement, target)
        _verify_strategy_settlement(
            diversified_portfolio, diversified_settlement, target
        )
        _verify_strategy_settlement(
            six_red_top70_portfolio, six_red_top70_settlement, target
        )
        actual = raw_settlement.actual
        if diversified_settlement.actual != actual or six_red_top70_settlement.actual != actual:
            _reject(
                "seven_red_outer_trial_common_outcome_mismatch",
                "all strategy settlements must use the same actual outcome",
            )
        _verify_random_sources(
            protocol=protocol,
            score_pool=raw_score_pool,
            cohort=raw_random_cohort,
            settlement=raw_random_settlement,
            target_issue=target,
            actual=actual,
        )
        _verify_random_sources(
            protocol=protocol,
            score_pool=diversified_score_pool,
            cohort=diversified_random_cohort,
            settlement=diversified_random_settlement,
            target_issue=target,
            actual=actual,
        )
        vector_digest = raw_vector.vector_digest
        strategy_arms = (
            SevenRedOuterStrategyArmEvidence.from_verified(
                arm_kind=SevenRedOuterArmKind.RAW_TOP10,
                parameter_digest=raw_parameter.parameter_digest,
                source_vector_digest=vector_digest,
                source_score_pool_snapshot_digest=raw_score_pool.snapshot_digest,
                source_strategy_artifact_digest=raw_top10.snapshot_digest,
                portfolio=raw_portfolio,
                settlement=raw_settlement,
            ),
            SevenRedOuterStrategyArmEvidence.from_verified(
                arm_kind=SevenRedOuterArmKind.DIVERSIFIED_TOP10,
                parameter_digest=diversified_parameter.parameter_digest,
                source_vector_digest=vector_digest,
                source_score_pool_snapshot_digest=diversified_score_pool.snapshot_digest,
                source_strategy_artifact_digest=diversified_top10.snapshot_digest,
                portfolio=diversified_portfolio,
                settlement=diversified_settlement,
            ),
            SevenRedOuterStrategyArmEvidence.from_verified(
                arm_kind=SevenRedOuterArmKind.SIX_RED_TOP70,
                parameter_digest=None,
                source_vector_digest=vector_digest,
                source_score_pool_snapshot_digest=None,
                source_strategy_artifact_digest=vector_digest,
                portfolio=six_red_top70_portfolio,
                settlement=six_red_top70_settlement,
            ),
        )
        random_evidence = (
            SevenRedMatchedRandomEvidence.from_verified(
                matched_family=SevenRedStrategyKind.RAW,
                cohort=raw_random_cohort,
                settlement=raw_random_settlement,
            ),
            SevenRedMatchedRandomEvidence.from_verified(
                matched_family=SevenRedStrategyKind.DIVERSIFIED,
                cohort=diversified_random_cohort,
                settlement=diversified_random_settlement,
            ),
        )
        return cls(
            target_issue=target,
            protocol_digest=protocol.protocol_digest,
            inner_selection_snapshot_digest=inner_selection.snapshot_digest,
            source_history_latest_issue=raw_vector.source_history_latest_issue,
            source_vector_digest=vector_digest,
            actual=actual,
            strategy_arms=strategy_arms,
            matched_random_evidence=random_evidence,
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": SEVEN_RED_OUTER_TRIAL_VERSION,
            "line_key": LINE_KEY,
            "research_only": RESEARCH_ONLY,
            "contract": SEVEN_RED_WALK_FORWARD_CONTRACT_V1.normative_identity(),
            "target_issue": self.target_issue,
            "protocol_digest": self.protocol_digest,
            "inner_selection_snapshot_digest": self.inner_selection_snapshot_digest,
            "source_history_latest_issue": self.source_history_latest_issue,
            "source_vector_digest": self.source_vector_digest,
            "actual": self.actual.identity_payload(),
            "strategy_arms": [row.as_dict() for row in self.strategy_arms],
            "matched_random_evidence": [
                row.as_dict() for row in self.matched_random_evidence
            ],
            "cross_target_aggregate": None,
            "winner": None,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "trial_digest": self.trial_digest}


def _selected_parameter(
    snapshot: SevenRedInnerSelectionSnapshot,
    kind: SevenRedStrategyKind,
):
    digest = snapshot.selected_parameter_digest(kind)
    return next(
        parameter
        for parameter in snapshot.parameter_grid.parameters
        if parameter.parameter_digest == digest
    )


def _verify_strategy_settlement(
    portfolio: EqualCostSixRedPortfolio70,
    settlement: EqualCostPortfolioSettlement,
    target_issue: str,
) -> None:
    if not isinstance(settlement, EqualCostPortfolioSettlement):
        _reject("seven_red_outer_trial_settlement_invalid", "strategy settlement is invalid")
    if (
        settlement.portfolio.portfolio_digest != portfolio.portfolio_digest
        or settlement.actual_issue != target_issue
    ):
        _reject(
            "seven_red_outer_trial_settlement_mismatch",
            "strategy settlement does not bind the verified portfolio and target",
        )


def _verify_random_sources(
    *,
    protocol: SevenRedWalkForwardProtocol,
    score_pool: SevenRedScoredCandidatePoolSnapshot,
    cohort: RandomControlCohortSnapshot,
    settlement: RandomControlCohortSettlement,
    target_issue: str,
    actual: SixRedCombination,
) -> None:
    if not isinstance(cohort, RandomControlCohortSnapshot):
        _reject("seven_red_outer_trial_random_cohort_invalid", "random cohort is invalid")
    RandomControlCohortVerifier().verify(cohort)
    if (
        cohort.source_score_pool.snapshot_digest != score_pool.snapshot_digest
        or cohort.seed_policy != protocol.seed_policy
    ):
        _reject(
            "seven_red_outer_trial_random_source_mismatch",
            "random cohort does not bind the selected family score pool and seed policy",
        )
    if not isinstance(settlement, RandomControlCohortSettlement):
        _reject(
            "seven_red_outer_trial_random_settlement_invalid",
            "random settlement is invalid",
        )
    if (
        settlement.cohort.cohort_digest != cohort.cohort_digest
        or settlement.actual_issue != target_issue
        or settlement.actual != actual
    ):
        _reject(
            "seven_red_outer_trial_common_outcome_mismatch",
            "random settlement does not bind its cohort and the common outcome",
        )


@dataclass(frozen=True)
class SevenRedWalkForwardSnapshot:
    protocol: SevenRedWalkForwardProtocol
    trials: tuple[SevenRedOuterTrial, ...]
    snapshot_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.protocol, SevenRedWalkForwardProtocol):
            _reject("seven_red_walk_forward_protocol_invalid", "protocol is invalid")
        if (
            not isinstance(self.trials, tuple)
            or any(not isinstance(trial, SevenRedOuterTrial) for trial in self.trials)
        ):
            _reject("seven_red_walk_forward_trials_invalid", "trial rows are invalid")
        actual_targets = tuple(trial.target_issue for trial in self.trials)
        if actual_targets != self.protocol.outer_target_issues:
            _reject(
                "seven_red_walk_forward_target_matrix_invalid",
                "snapshot requires exactly one canonical trial per protocol target",
            )
        if any(trial.protocol_digest != self.protocol.protocol_digest for trial in self.trials):
            _reject(
                "seven_red_walk_forward_protocol_binding_invalid",
                "every trial must bind the exact walk-forward protocol",
            )
        if any(
            random_evidence.seed_policy != self.protocol.seed_policy
            for trial in self.trials
            for random_evidence in trial.matched_random_evidence
        ):
            _reject(
                "seven_red_walk_forward_seed_policy_binding_invalid",
                "every matched random cohort must use the protocol seed policy",
            )
        object.__setattr__(
            self,
            "snapshot_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.seven-red.walk-forward-snapshot.v1",
            ),
        )

    @classmethod
    def build(
        cls,
        *,
        protocol: SevenRedWalkForwardProtocol,
        trials: Iterable[SevenRedOuterTrial],
    ) -> SevenRedWalkForwardSnapshot:
        rows = tuple(sorted(tuple(trials), key=lambda row: int(row.target_issue)))
        return cls(protocol=protocol, trials=rows)

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": SEVEN_RED_WALK_FORWARD_SNAPSHOT_VERSION,
            "line_key": LINE_KEY,
            "research_only": RESEARCH_ONLY,
            "contract": SEVEN_RED_WALK_FORWARD_CONTRACT_V1.normative_identity(),
            "protocol": self.protocol.as_dict(),
            "trial_count": len(self.trials),
            "trials": [trial.as_dict() for trial in self.trials],
            "cross_target_aggregate": None,
            "statistical_result": None,
            "winner": None,
            "promotion_status": None,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "snapshot_digest": self.snapshot_digest}


class SevenRedWalkForwardVerifier:
    def verify(self, snapshot: SevenRedWalkForwardSnapshot) -> None:
        if not isinstance(snapshot, SevenRedWalkForwardSnapshot):
            _reject("seven_red_walk_forward_snapshot_invalid", "snapshot is invalid")
        replay = SevenRedWalkForwardSnapshot.build(
            protocol=snapshot.protocol,
            trials=snapshot.trials,
        )
        if replay.snapshot_digest != snapshot.snapshot_digest:
            _reject(
                "seven_red_walk_forward_replay_mismatch",
                "walk-forward snapshot does not match deterministic replay",
                expected=replay.snapshot_digest,
                actual=snapshot.snapshot_digest,
            )
