from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np

from dehps.contracts import ContractRef, canonical_digest
from dehps.input_contracts.candidate_abi import candidate_unrank
from dehps.seven_red.diversified import (
    SEVEN_RED_DIVERSIFIED_TOP10_CONTRACT_V1,
    DiversifiedSevenRedTop10Snapshot,
)
from dehps.seven_red.domain import (
    LINE_KEY,
    RESEARCH_ONLY,
    SEVEN_RED_DOMAIN_CONTRACT_V1,
    SIX_RED_UNIVERSE,
    SevenRedCandidate,
    SixRedCombination,
    expand_seven_red_candidate,
)
from dehps.seven_red.raw_top10 import (
    SEVEN_RED_RAW_TOP10_CONTRACT_V1,
    RawSevenRedTop10Snapshot,
)
from dehps.seven_red.scoring import (
    SEVEN_RED_SCORE_POOL_CONTRACT_V1,
    SevenRedScorePoolVerifier,
    SevenRedScorePoolViolation,
    SevenRedScoredCandidatePoolSnapshot,
    SixRedFullScoreVector,
)


EQUAL_COST_TICKET_BUDGET = 70
EQUAL_COST_PORTFOLIO_VERSION = "equal_cost_six_red_portfolio70.v1"
EQUAL_COST_SETTLEMENT_VERSION = "equal_cost_portfolio_settlement.v1"
EQUAL_COST_PORTFOLIO_COMPILER_CONTRACT = (
    "equal_cost_six_red_portfolio70.preserve_paid_slots.v1"
)


class EqualCostPortfolioSource(str, Enum):
    RAW_SEVEN_RED_TOP10 = "raw_seven_red_top10"
    DIVERSIFIED_SEVEN_RED_TOP10 = "diversified_seven_red_top10"
    SIX_RED_TOP70 = "six_red_top70"


EQUAL_COST_PORTFOLIO_NORMATIVE_DEFINITION = {
    "contract": "seven-red-equal-cost-portfolio.v1.0.0",
    "line_key": LINE_KEY,
    "research_only": RESEARCH_ONLY,
    "dependencies": {
        "seven_red_domain": SEVEN_RED_DOMAIN_CONTRACT_V1.normative_identity(),
        "raw_top10": SEVEN_RED_RAW_TOP10_CONTRACT_V1.normative_identity(),
        "diversified_top10": (
            SEVEN_RED_DIVERSIFIED_TOP10_CONTRACT_V1.normative_identity()
        ),
        "score_pool": SEVEN_RED_SCORE_POOL_CONTRACT_V1.normative_identity(),
    },
    "portfolio": {
        "paid_ticket_slots": EQUAL_COST_TICKET_BUDGET,
        "ticket": "canonical_six_red_combination",
        "slot_order": "source_specific_and_immutable",
        "duplicates": "preserved_as_paid_slots_and_reported_separately",
        "target_issue": "explicit_pre_outcome_identity",
        "outcome_fields": "forbidden",
    },
    "sources": {
        EqualCostPortfolioSource.RAW_SEVEN_RED_TOP10.value: (
            "raw_rank_then_expansion_ordinal_preserve_duplicates"
        ),
        EqualCostPortfolioSource.DIVERSIFIED_SEVEN_RED_TOP10.value: (
            "diversified_rank_then_expansion_ordinal_require_70_unique"
        ),
        EqualCostPortfolioSource.SIX_RED_TOP70.value: (
            "score_tick_desc_then_six_red_lex_id_asc_require_70_unique"
        ),
    },
    "source_binding": {
        "raw_and_diversified": (
            "must_bind_parent_score_pool_snapshot_candidate_pool_and_chronology"
        ),
        "six_red_top70": "must_bind_full_score_vector_and_chronology",
    },
    "settlement": {
        "stage": "separate_post_outcome_artifact",
        "actual_issue": "must_equal_sealed_portfolio_target_issue",
        "metrics": [
            "slot_weighted_matched_red_histogram_0_through_6",
            "unique_ticket_matched_red_histogram_0_through_6",
            "slot_weighted_exact_red6_count",
            "unique_ticket_exact_red6_count",
        ],
        "economic_interpretation": "absent",
    },
    "non_goals": [
        "no_random_control_or_seed_policy",
        "no_parameter_selection_or_walk_forward",
        "no_statistical_or_predictive_claim",
        "no_blue_ball_prize_payout_or_expected_value",
        "no_production_integration",
    ],
}

EQUAL_COST_PORTFOLIO_GOLDEN_SUITE = {
    "suite": "seven_red_equal_cost_portfolio_golden.v1",
    "raw_duplicate_case": {
        "seven_red_candidates": [
            [1, 2, 3, 4, 5, 6, 7],
            [1, 2, 3, 4, 5, 6, 8],
        ],
        "paid_slots": 14,
        "unique_tickets": 13,
        "duplicate_slots": 1,
    },
    "settlement_case": {
        "ticket": [1, 2, 3, 4, 5, 6],
        "actual": [1, 2, 3, 4, 5, 6],
        "matched_red_count": 6,
    },
    "stochastic": False,
}

EQUAL_COST_PORTFOLIO_CONTRACT_V1 = ContractRef.from_definition(
    family="seven-red-equal-cost-portfolio",
    semantic_version="1.0.0",
    schema_version="dehps.seven-red-equal-cost-portfolio.schema.v1",
    normative_definition=EQUAL_COST_PORTFOLIO_NORMATIVE_DEFINITION,
    golden_suite=EQUAL_COST_PORTFOLIO_GOLDEN_SUITE,
)


class EqualCostPortfolioViolation(ValueError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "context": dict(self.context)}


def _reject(code: str, message: str, **context: Any) -> None:
    raise EqualCostPortfolioViolation(code, message, **context)


def _require_digest(value: object, *, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _reject(
            "equal_cost_portfolio_digest_invalid",
            f"{field_name} must be a lowercase sha256 digest",
            field=field_name,
        )
    return value


def _require_issue(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or len(value) != 7 or not value.isascii() or not value.isdigit():
        _reject(
            "equal_cost_portfolio_issue_invalid",
            f"{field_name} must be a seven-digit issue string",
            field=field_name,
        )
    return value


def _top_six_red_ids(score_ticks: np.ndarray, top_n: int) -> np.ndarray:
    count = len(score_ticks)
    if top_n < count:
        threshold = np.partition(score_ticks, count - top_n)[count - top_n]
        better = np.flatnonzero(score_ticks > threshold)
        equal = np.flatnonzero(score_ticks == threshold)
        selected = np.concatenate((better, equal[: top_n - len(better)]))
    else:
        selected = np.arange(count, dtype=np.int64)
    signed_order = score_ticks[selected].view(np.uint64) ^ np.uint64(1 << 63)
    descending_score_key = np.bitwise_not(signed_order)
    order = np.lexsort((selected, descending_score_key))
    return np.ascontiguousarray(selected[order[:top_n]], dtype=np.int64)


@dataclass(frozen=True)
class SixRedTicketSlot:
    slot_ordinal: int
    source_kind: EqualCostPortfolioSource
    six_red: SixRedCombination
    source_rank: int
    parent_candidate_id: str | None
    expansion_ordinal: int | None
    source_score_tick: int | None
    slot_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.slot_ordinal, int)
            or isinstance(self.slot_ordinal, bool)
            or not 1 <= self.slot_ordinal <= EQUAL_COST_TICKET_BUDGET
        ):
            _reject("equal_cost_slot_ordinal_invalid", "slot ordinal must be in [1,70]")
        if not isinstance(self.source_kind, EqualCostPortfolioSource):
            _reject("equal_cost_slot_source_invalid", "slot source kind is invalid")
        if not isinstance(self.six_red, SixRedCombination):
            _reject("equal_cost_slot_ticket_invalid", "slot requires a SixRedCombination")
        upper = 70 if self.source_kind is EqualCostPortfolioSource.SIX_RED_TOP70 else 10
        if (
            not isinstance(self.source_rank, int)
            or isinstance(self.source_rank, bool)
            or not 1 <= self.source_rank <= upper
        ):
            _reject("equal_cost_slot_source_rank_invalid", "slot source rank is invalid")
        if self.source_kind is EqualCostPortfolioSource.SIX_RED_TOP70:
            if self.parent_candidate_id is not None or self.expansion_ordinal is not None:
                _reject(
                    "equal_cost_slot_provenance_invalid",
                    "six-red Top70 slots cannot contain seven-red parent provenance",
                )
            if not isinstance(self.source_score_tick, int) or isinstance(
                self.source_score_tick, bool
            ):
                _reject(
                    "equal_cost_slot_score_tick_invalid",
                    "six-red Top70 slots require an exact source score tick",
                )
        else:
            _require_digest(self.parent_candidate_id, field_name="parent_candidate_id")
            if (
                not isinstance(self.expansion_ordinal, int)
                or isinstance(self.expansion_ordinal, bool)
                or not 1 <= self.expansion_ordinal <= 7
            ):
                _reject(
                    "equal_cost_slot_expansion_ordinal_invalid",
                    "seven-red slots require expansion ordinal in [1,7]",
                )
            if self.source_score_tick is not None:
                _reject(
                    "equal_cost_slot_provenance_invalid",
                    "seven-red expansion slots cannot contain a six-red source score tick",
                )
        object.__setattr__(
            self,
            "slot_digest",
            canonical_digest(self.identity_payload(), domain="dehps.equal-cost.slot.v1"),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "slot_ordinal": self.slot_ordinal,
            "source_kind": self.source_kind.value,
            "six_red": self.six_red.identity_payload(),
            "source_rank": self.source_rank,
            "parent_candidate_id": self.parent_candidate_id,
            "expansion_ordinal": self.expansion_ordinal,
            "source_score_tick": self.source_score_tick,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "slot_digest": self.slot_digest}


@dataclass(frozen=True)
class EqualCostSixRedPortfolio70:
    source_kind: EqualCostPortfolioSource
    target_issue: str
    source_artifact_digest: str
    source_score_pool_snapshot_digest: str | None
    source_candidate_pool_digest: str | None
    source_history_latest_issue: str
    slots: tuple[SixRedTicketSlot, ...]
    unique_ticket_count: int = field(init=False)
    duplicate_slot_count: int = field(init=False)
    slot_sequence_digest: str = field(init=False)
    portfolio_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.source_kind, EqualCostPortfolioSource):
            _reject("equal_cost_portfolio_source_invalid", "portfolio source kind is invalid")
        target = _require_issue(self.target_issue, field_name="target_issue")
        latest = _require_issue(
            self.source_history_latest_issue,
            field_name="source_history_latest_issue",
        )
        if int(latest) >= int(target):
            _reject(
                "equal_cost_portfolio_chronology_invalid",
                "source history must end strictly before target issue",
            )
        _require_digest(self.source_artifact_digest, field_name="source_artifact_digest")
        is_six = self.source_kind is EqualCostPortfolioSource.SIX_RED_TOP70
        if is_six:
            if self.source_score_pool_snapshot_digest is not None or self.source_candidate_pool_digest is not None:
                _reject(
                    "equal_cost_portfolio_source_binding_invalid",
                    "six-red Top70 cannot bind seven-red score-pool metadata",
                )
        else:
            _require_digest(
                self.source_score_pool_snapshot_digest,
                field_name="source_score_pool_snapshot_digest",
            )
            _require_digest(
                self.source_candidate_pool_digest,
                field_name="source_candidate_pool_digest",
            )
        if (
            not isinstance(self.slots, tuple)
            or len(self.slots) != EQUAL_COST_TICKET_BUDGET
            or any(not isinstance(slot, SixRedTicketSlot) for slot in self.slots)
        ):
            _reject(
                "equal_cost_portfolio_slot_count_invalid",
                "portfolio must contain exactly 70 immutable ticket slots",
            )
        if tuple(slot.slot_ordinal for slot in self.slots) != tuple(range(1, 71)):
            _reject(
                "equal_cost_portfolio_slot_order_invalid",
                "slot ordinals must be contiguous and canonical",
            )
        if any(slot.source_kind is not self.source_kind for slot in self.slots):
            _reject(
                "equal_cost_portfolio_mixed_source",
                "all slots must use the portfolio source kind",
            )
        unique_count = len({slot.six_red.combination_id for slot in self.slots})
        duplicate_count = len(self.slots) - unique_count
        if self.source_kind in (
            EqualCostPortfolioSource.DIVERSIFIED_SEVEN_RED_TOP10,
            EqualCostPortfolioSource.SIX_RED_TOP70,
        ) and (unique_count != 70 or duplicate_count != 0):
            _reject(
                "equal_cost_portfolio_unique70_invariant_failed",
                "Diversified and six-red Top70 portfolios require 70 unique tickets",
            )
        slot_digest = canonical_digest(
            [slot.as_dict() for slot in self.slots],
            domain="dehps.equal-cost.slot-sequence.v1",
        )
        object.__setattr__(self, "unique_ticket_count", unique_count)
        object.__setattr__(self, "duplicate_slot_count", duplicate_count)
        object.__setattr__(self, "slot_sequence_digest", slot_digest)
        object.__setattr__(
            self,
            "portfolio_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.equal-cost.portfolio70.v1",
            ),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": EQUAL_COST_PORTFOLIO_VERSION,
            "line_key": LINE_KEY,
            "research_only": RESEARCH_ONLY,
            "contract": EQUAL_COST_PORTFOLIO_CONTRACT_V1.normative_identity(),
            "compiler_contract": EQUAL_COST_PORTFOLIO_COMPILER_CONTRACT,
            "source_kind": self.source_kind.value,
            "target_issue": self.target_issue,
            "source_artifact_digest": self.source_artifact_digest,
            "source_score_pool_snapshot_digest": self.source_score_pool_snapshot_digest,
            "source_candidate_pool_digest": self.source_candidate_pool_digest,
            "source_history_latest_issue": self.source_history_latest_issue,
            "paid_ticket_slot_count": len(self.slots),
            "unique_ticket_count": self.unique_ticket_count,
            "duplicate_slot_count": self.duplicate_slot_count,
            "slot_sequence_digest": self.slot_sequence_digest,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "slots": [slot.as_dict() for slot in self.slots],
            "portfolio_digest": self.portfolio_digest,
        }


def _seven_red_slots(
    *,
    source_kind: EqualCostPortfolioSource,
    ranked_candidates: Sequence[tuple[int, SevenRedCandidate]],
) -> tuple[SixRedTicketSlot, ...]:
    slots: list[SixRedTicketSlot] = []
    for source_rank, candidate in ranked_candidates:
        for expansion in expand_seven_red_candidate(candidate):
            slots.append(
                SixRedTicketSlot(
                    slot_ordinal=len(slots) + 1,
                    source_kind=source_kind,
                    six_red=expansion.six_red,
                    source_rank=source_rank,
                    parent_candidate_id=candidate.candidate_id,
                    expansion_ordinal=expansion.ordinal,
                    source_score_tick=None,
                )
            )
    return tuple(slots)


def compile_raw_equal_cost_portfolio(
    *,
    score_pool: SevenRedScoredCandidatePoolSnapshot,
    raw_top10: RawSevenRedTop10Snapshot,
) -> EqualCostSixRedPortfolio70:
    if not isinstance(score_pool, SevenRedScoredCandidatePoolSnapshot):
        _reject("equal_cost_portfolio_score_pool_invalid", "score_pool is invalid")
    _verify_score_pool(score_pool)
    if not isinstance(raw_top10, RawSevenRedTop10Snapshot):
        _reject("equal_cost_portfolio_raw_source_invalid", "raw_top10 is invalid")
    if raw_top10.source.artifact_digest != score_pool.candidate_pool.artifact_digest:
        _reject(
            "equal_cost_portfolio_candidate_pool_mismatch",
            "Raw Top10 and score-pool candidate lists do not match",
        )
    slots = _seven_red_slots(
        source_kind=EqualCostPortfolioSource.RAW_SEVEN_RED_TOP10,
        ranked_candidates=tuple(
            (entry.raw_rank, entry.scored_candidate.candidate)
            for entry in raw_top10.entries
        ),
    )
    return EqualCostSixRedPortfolio70(
        source_kind=EqualCostPortfolioSource.RAW_SEVEN_RED_TOP10,
        target_issue=score_pool.target_issue,
        source_artifact_digest=raw_top10.snapshot_digest,
        source_score_pool_snapshot_digest=score_pool.snapshot_digest,
        source_candidate_pool_digest=score_pool.candidate_pool.artifact_digest,
        source_history_latest_issue=score_pool.source_vector.source_history_latest_issue,
        slots=slots,
    )


def compile_diversified_equal_cost_portfolio(
    *,
    score_pool: SevenRedScoredCandidatePoolSnapshot,
    diversified_top10: DiversifiedSevenRedTop10Snapshot,
) -> EqualCostSixRedPortfolio70:
    if not isinstance(score_pool, SevenRedScoredCandidatePoolSnapshot):
        _reject("equal_cost_portfolio_score_pool_invalid", "score_pool is invalid")
    _verify_score_pool(score_pool)
    if not isinstance(diversified_top10, DiversifiedSevenRedTop10Snapshot):
        _reject(
            "equal_cost_portfolio_diversified_source_invalid",
            "diversified_top10 is invalid",
        )
    source_pool = diversified_top10.source_audit.source_candidate_pool
    if source_pool.artifact_digest != score_pool.candidate_pool.artifact_digest:
        _reject(
            "equal_cost_portfolio_candidate_pool_mismatch",
            "Diversified Top10 and score-pool candidate lists do not match",
        )
    slots = _seven_red_slots(
        source_kind=EqualCostPortfolioSource.DIVERSIFIED_SEVEN_RED_TOP10,
        ranked_candidates=tuple(
            (step.diversified_rank, step.scored_candidate.candidate)
            for step in diversified_top10.steps
        ),
    )
    return EqualCostSixRedPortfolio70(
        source_kind=EqualCostPortfolioSource.DIVERSIFIED_SEVEN_RED_TOP10,
        target_issue=score_pool.target_issue,
        source_artifact_digest=diversified_top10.snapshot_digest,
        source_score_pool_snapshot_digest=score_pool.snapshot_digest,
        source_candidate_pool_digest=score_pool.candidate_pool.artifact_digest,
        source_history_latest_issue=score_pool.source_vector.source_history_latest_issue,
        slots=slots,
    )


def _verify_score_pool(score_pool: SevenRedScoredCandidatePoolSnapshot) -> None:
    try:
        SevenRedScorePoolVerifier().verify(score_pool)
    except SevenRedScorePoolViolation as exc:
        raise EqualCostPortfolioViolation(
            "equal_cost_portfolio_score_pool_verification_failed",
            "parent score-pool snapshot failed deterministic replay",
            cause=exc.code,
        ) from exc


def compile_six_red_top70_portfolio(
    *,
    source_vector: SixRedFullScoreVector,
    target_issue: str,
) -> EqualCostSixRedPortfolio70:
    if not isinstance(source_vector, SixRedFullScoreVector):
        _reject("equal_cost_portfolio_source_vector_invalid", "source_vector is invalid")
    target = _require_issue(target_issue, field_name="target_issue")
    if int(source_vector.source_history_latest_issue) >= int(target):
        _reject(
            "equal_cost_portfolio_chronology_invalid",
            "source history must end strictly before target issue",
        )
    top_ids = _top_six_red_ids(source_vector.score_ticks, EQUAL_COST_TICKET_BUDGET)
    slots = tuple(
        SixRedTicketSlot(
            slot_ordinal=rank,
            source_kind=EqualCostPortfolioSource.SIX_RED_TOP70,
            six_red=SixRedCombination(
                candidate_unrank(int(lex_id), universe=SIX_RED_UNIVERSE)
            ),
            source_rank=rank,
            parent_candidate_id=None,
            expansion_ordinal=None,
            source_score_tick=int(source_vector.score_ticks[lex_id]),
        )
        for rank, lex_id in enumerate(top_ids, start=1)
    )
    return EqualCostSixRedPortfolio70(
        source_kind=EqualCostPortfolioSource.SIX_RED_TOP70,
        target_issue=target,
        source_artifact_digest=source_vector.vector_digest,
        source_score_pool_snapshot_digest=None,
        source_candidate_pool_digest=None,
        source_history_latest_issue=source_vector.source_history_latest_issue,
        slots=slots,
    )


@dataclass(frozen=True)
class EqualCostPortfolioSettlement:
    portfolio: EqualCostSixRedPortfolio70
    actual_issue: str
    actual: SixRedCombination
    slot_matched_red_counts: tuple[int, ...]
    slot_hit_histogram: tuple[int, ...]
    unique_ticket_hit_histogram: tuple[int, ...]
    settlement_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.portfolio, EqualCostSixRedPortfolio70):
            _reject("equal_cost_settlement_portfolio_invalid", "settlement portfolio is invalid")
        actual_issue = _require_issue(self.actual_issue, field_name="actual_issue")
        if actual_issue != self.portfolio.target_issue:
            _reject(
                "equal_cost_settlement_issue_mismatch",
                "actual issue must equal the sealed portfolio target issue",
            )
        if not isinstance(self.actual, SixRedCombination):
            _reject("equal_cost_settlement_actual_invalid", "actual must be a SixRedCombination")
        actual_set = set(self.actual.sorted_red_numbers)
        expected_counts = tuple(
            len(actual_set.intersection(slot.six_red.sorted_red_numbers))
            for slot in self.portfolio.slots
        )
        if self.slot_matched_red_counts != expected_counts:
            _reject(
                "equal_cost_settlement_slot_counts_mismatch",
                "slot hit counts do not match the sealed portfolio and actual outcome",
            )
        if any(not 0 <= count <= 6 for count in expected_counts):
            _reject("equal_cost_settlement_hit_count_invalid", "slot hit counts are invalid")
        expected_slot_histogram = tuple(Counter(expected_counts).get(value, 0) for value in range(7))
        unique_by_id = {
            slot.six_red.combination_id: slot.six_red for slot in self.portfolio.slots
        }
        unique_counts = tuple(
            len(actual_set.intersection(ticket.sorted_red_numbers))
            for ticket in unique_by_id.values()
        )
        expected_unique_histogram = tuple(
            Counter(unique_counts).get(value, 0) for value in range(7)
        )
        if self.slot_hit_histogram != expected_slot_histogram:
            _reject(
                "equal_cost_settlement_slot_histogram_mismatch",
                "slot-weighted histogram is inconsistent",
            )
        if self.unique_ticket_hit_histogram != expected_unique_histogram:
            _reject(
                "equal_cost_settlement_unique_histogram_mismatch",
                "unique-ticket histogram is inconsistent",
            )
        if sum(self.slot_hit_histogram) != 70 or sum(
            self.unique_ticket_hit_histogram
        ) != self.portfolio.unique_ticket_count:
            _reject(
                "equal_cost_settlement_histogram_total_mismatch",
                "settlement histogram totals are inconsistent",
            )
        object.__setattr__(
            self,
            "settlement_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.equal-cost.portfolio-settlement.v1",
            ),
        )

    @classmethod
    def evaluate(
        cls,
        *,
        portfolio: EqualCostSixRedPortfolio70,
        actual_issue: str,
        actual_red_numbers: Sequence[object],
    ) -> EqualCostPortfolioSettlement:
        if not isinstance(portfolio, EqualCostSixRedPortfolio70):
            _reject("equal_cost_settlement_portfolio_invalid", "settlement portfolio is invalid")
        actual = SixRedCombination.from_numbers(actual_red_numbers)
        actual_set = set(actual.sorted_red_numbers)
        counts = tuple(
            len(actual_set.intersection(slot.six_red.sorted_red_numbers))
            for slot in portfolio.slots
        )
        slot_histogram = tuple(Counter(counts).get(value, 0) for value in range(7))
        unique_tickets = {
            slot.six_red.combination_id: slot.six_red for slot in portfolio.slots
        }
        unique_counts = tuple(
            len(actual_set.intersection(ticket.sorted_red_numbers))
            for ticket in unique_tickets.values()
        )
        unique_histogram = tuple(
            Counter(unique_counts).get(value, 0) for value in range(7)
        )
        return cls(
            portfolio=portfolio,
            actual_issue=actual_issue,
            actual=actual,
            slot_matched_red_counts=counts,
            slot_hit_histogram=slot_histogram,
            unique_ticket_hit_histogram=unique_histogram,
        )

    @property
    def slot_weighted_exact_red6_count(self) -> int:
        return self.slot_hit_histogram[6]

    @property
    def unique_ticket_exact_red6_count(self) -> int:
        return self.unique_ticket_hit_histogram[6]

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": EQUAL_COST_SETTLEMENT_VERSION,
            "line_key": LINE_KEY,
            "research_only": RESEARCH_ONLY,
            "contract": EQUAL_COST_PORTFOLIO_CONTRACT_V1.normative_identity(),
            "portfolio_digest": self.portfolio.portfolio_digest,
            "actual_issue": self.actual_issue,
            "actual": self.actual.identity_payload(),
            "slot_matched_red_counts": list(self.slot_matched_red_counts),
            "slot_hit_histogram": list(self.slot_hit_histogram),
            "unique_ticket_hit_histogram": list(self.unique_ticket_hit_histogram),
            "slot_weighted_exact_red6_count": self.slot_weighted_exact_red6_count,
            "unique_ticket_exact_red6_count": self.unique_ticket_exact_red6_count,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "settlement_digest": self.settlement_digest}


class EqualCostPortfolioVerifier:
    def verify_raw(
        self,
        portfolio: EqualCostSixRedPortfolio70,
        *,
        score_pool: SevenRedScoredCandidatePoolSnapshot,
        raw_top10: RawSevenRedTop10Snapshot,
    ) -> None:
        expected = compile_raw_equal_cost_portfolio(
            score_pool=score_pool,
            raw_top10=raw_top10,
        )
        self._compare(portfolio, expected)

    def verify_diversified(
        self,
        portfolio: EqualCostSixRedPortfolio70,
        *,
        score_pool: SevenRedScoredCandidatePoolSnapshot,
        diversified_top10: DiversifiedSevenRedTop10Snapshot,
    ) -> None:
        expected = compile_diversified_equal_cost_portfolio(
            score_pool=score_pool,
            diversified_top10=diversified_top10,
        )
        self._compare(portfolio, expected)

    def verify_six_red_top70(
        self,
        portfolio: EqualCostSixRedPortfolio70,
        *,
        source_vector: SixRedFullScoreVector,
        target_issue: str,
    ) -> None:
        expected = compile_six_red_top70_portfolio(
            source_vector=source_vector,
            target_issue=target_issue,
        )
        self._compare(portfolio, expected)

    @staticmethod
    def _compare(
        actual: EqualCostSixRedPortfolio70,
        expected: EqualCostSixRedPortfolio70,
    ) -> None:
        if not isinstance(actual, EqualCostSixRedPortfolio70):
            _reject("equal_cost_portfolio_type_invalid", "portfolio is invalid")
        if actual.portfolio_digest != expected.portfolio_digest:
            _reject(
                "equal_cost_portfolio_replay_mismatch",
                "portfolio does not match deterministic compilation from its source",
                expected=expected.portfolio_digest,
                actual=actual.portfolio_digest,
            )
