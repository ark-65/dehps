from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from typing import Any

from dehps.contracts import ContractRef, canonical_digest
from dehps.input_contracts.candidate_abi import candidate_unrank
from dehps.seven_red.domain import (
    LINE_KEY,
    RESEARCH_ONLY,
    SIX_RED_UNIVERSE,
    SixRedCombination,
    expand_seven_red_candidate,
)
from dehps.seven_red.scoring import (
    SEVEN_RED_SCORE_POOL_CONTRACT_V1,
    SevenRedScorePoolVerifier,
    SevenRedScorePoolViolation,
    SevenRedScoredCandidatePoolSnapshot,
)


RANDOM_CONTROL_TICKET_BUDGET = 70
RANDOM_POOL_CANDIDATE_COUNT = 10
RANDOM_CONTROL_SEED_POLICY_VERSION = "random_control_seed_policy.v1"
RANDOM_CONTROL_PORTFOLIO_VERSION = "random_control_portfolio70.v1"
RANDOM_CONTROL_COHORT_VERSION = "random_control_cohort_snapshot.v1"
RANDOM_CONTROL_SETTLEMENT_VERSION = "random_control_cohort_settlement.v1"
RANDOM_POOL_ALGORITHM = "sha256_candidate_priority_without_replacement.v1"
UNIFORM_LEGAL_ALGORITHM = "sha256_counter_rejection_without_replacement.v1"
UNIFORM_WORD_DOMAIN = b"dehps.random-control.uniform-legal-word.v1\x00"
UINT64_SPACE = 1 << 64
UINT64_MAX = UINT64_SPACE - 1
UNIFORM_REJECTION_LIMIT = (
    UINT64_SPACE // SIX_RED_UNIVERSE.cardinality
) * SIX_RED_UNIVERSE.cardinality


class RandomControlKind(str, Enum):
    RANDOM_FROM_POOL = "random_from_pool"
    UNIFORM_LEGAL = "uniform_legal"


RANDOM_CONTROL_NORMATIVE_DEFINITION = {
    "contract": "seven-red-random-control.v1.0.0",
    "line_key": LINE_KEY,
    "research_only": RESEARCH_ONLY,
    "dependency": SEVEN_RED_SCORE_POOL_CONTRACT_V1.normative_identity(),
    "seed_policy": {
        "representation": "sorted_unique_lowercase_sha256_digests",
        "minimum_seed_count": 2,
        "default": "absent",
        "generated_seed": "forbidden",
        "selection_policy": "no_best_seed",
    },
    "random_from_pool": {
        "source": "replay_verified_parent_score_pool_candidate_list",
        "priority": (
            "domain_separated_sha256_of_seed_target_source_and_candidate_identity"
        ),
        "selection": "ten_lowest_priority_then_lower_seven_red_lex_id",
        "replacement": False,
        "expansion": "all_70_paid_slots_preserve_duplicates",
        "algorithm": RANDOM_POOL_ALGORITHM,
    },
    "uniform_legal": {
        "universe": SIX_RED_UNIVERSE.identity_payload(),
        "word": "first_8_bytes_of_sha256_framed_payload_as_big_endian_uint64",
        "framing": [
            "ascii_domain_then_null",
            "32_seed_bytes",
            "null",
            "7_target_issue_ascii_bytes",
            "null",
            "32_source_snapshot_digest_bytes",
            "null",
            "8_byte_big_endian_counter",
        ],
        "counter_origin": 0,
        "counter_maximum": UINT64_MAX,
        "modulo_acceptance": f"word < {UNIFORM_REJECTION_LIMIT}",
        "lex_id": f"word mod {SIX_RED_UNIVERSE.cardinality}",
        "duplicate_policy": "reject_and_consume_next_counter",
        "selection": "first_70_accepted_distinct_lex_ids_in_counter_order",
        "algorithm": UNIFORM_LEGAL_ALGORITHM,
    },
    "cohort": {
        "order": "seed_digest_ascending_then_random_from_pool_then_uniform_legal",
        "portfolio_count": "two_per_seed",
        "omission_or_best_seed": "forbidden",
        "outcome_input": "forbidden",
    },
    "settlement": {
        "stage": "separate_post_outcome_artifact",
        "actual_issue": "must_equal_cohort_target_issue",
        "coverage": "every_seed_and_both_control_kinds",
        "metrics": "slot_weighted_and_unique_ticket_histograms_0_through_6",
    },
    "assumption": (
        "sha256_words_and_priorities_are_a_deterministic_computational_"
        "pseudorandom_control_not_physical_randomness"
    ),
    "non_goals": [
        "no_default_or_best_seed",
        "no_outcome_comparison_or_statistical_claim",
        "no_parameter_selection_or_walk_forward",
        "no_physical_randomness_claim",
        "no_economic_or_production_integration",
    ],
}

RANDOM_CONTROL_GOLDEN_SUITE = {
    "suite": "seven_red_random_control_golden.v1",
    "seed_digests": ["a" * 64, "b" * 64],
    "target_issue": "2026002",
    "uniform_rejection_limit": UNIFORM_REJECTION_LIMIT,
    "uniform_universe_cardinality": SIX_RED_UNIVERSE.cardinality,
    "counter_origin": 0,
    "counter_byte_order": "big",
    "expected_seed_policy_digest": (
        "207e6925e3fee0ae5ed815232de8cc0f8fd48a45f92149398c87db65a63254fc"
    ),
    "expected_portfolio_digests": [
        "cfb944e1607f54f93d19ee60ee52085553dd89224b7bd10422aa2e26bdceee2f",
        "8eea43a2a1a2f35e95c8220ec5d234f96fbdd14a2ca9287832f64b20521c78a5",
        "d5c02d6dcbe2eba339fd966d02f9bceda71a18494f52ead19c960f3ef9179a98",
        "3a4974a7ef10289a0a1947ff74ff160b35cf4d97296faf462e178f348234a081",
    ],
    "expected_cohort_digest": (
        "5e9d01aeafd7e22c92133c4f089990c2c242db145ee80080e0126a1349d91714"
    ),
    "stochastic": False,
}

RANDOM_CONTROL_CONTRACT_V1 = ContractRef.from_definition(
    family="seven-red-random-control",
    semantic_version="1.0.0",
    schema_version="dehps.seven-red-random-control.schema.v1",
    normative_definition=RANDOM_CONTROL_NORMATIVE_DEFINITION,
    golden_suite=RANDOM_CONTROL_GOLDEN_SUITE,
)


class RandomControlViolation(ValueError):
    def __init__(self, code: str, message: str, **context: Any) -> None:
        self.code = code
        self.context = context
        super().__init__(f"{code}: {message}")

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": str(self), "context": dict(self.context)}


def _reject(code: str, message: str, **context: Any) -> None:
    raise RandomControlViolation(code, message, **context)


def _require_digest(value: object, *, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _reject(
            "random_control_digest_invalid",
            f"{field_name} must be a lowercase sha256 digest",
            field=field_name,
        )
    return value


def _require_issue(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or len(value) != 7 or not value.isascii() or not value.isdigit():
        _reject(
            "random_control_issue_invalid",
            f"{field_name} must be a seven-digit issue string",
            field=field_name,
        )
    return value


@dataclass(frozen=True)
class RandomControlSeedPolicy:
    seed_digests: tuple[str, ...]
    policy_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.seed_digests, tuple) or len(self.seed_digests) < 2:
            _reject(
                "random_control_seed_count_invalid",
                "seed policy requires at least two explicit seed digests",
            )
        for seed in self.seed_digests:
            _require_digest(seed, field_name="seed_digest")
        if tuple(sorted(set(self.seed_digests))) != self.seed_digests:
            _reject(
                "random_control_seed_order_invalid",
                "seed digests must be unique and stored in ascending order",
            )
        object.__setattr__(
            self,
            "policy_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.random-control.seed-policy.v1",
            ),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": RANDOM_CONTROL_SEED_POLICY_VERSION,
            "seed_digests": list(self.seed_digests),
            "seed_count": len(self.seed_digests),
            "default_seed": None,
            "generated_seed": None,
            "selection_policy": "no_best_seed",
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "policy_digest": self.policy_digest}


def _pool_priority(
    *,
    seed_digest: str,
    target_issue: str,
    source_snapshot_digest: str,
    candidate_id: str,
) -> str:
    return canonical_digest(
        {
            "algorithm": RANDOM_POOL_ALGORITHM,
            "seed_digest": seed_digest,
            "target_issue": target_issue,
            "source_snapshot_digest": source_snapshot_digest,
            "candidate_id": candidate_id,
        },
        domain="dehps.random-control.pool-priority.v1",
    )


def _uniform_word(
    *,
    seed_digest: str,
    target_issue: str,
    source_snapshot_digest: str,
    counter: int,
) -> int:
    if not 0 <= counter <= UINT64_MAX:
        _reject(
            "random_control_counter_overflow",
            "uniform-legal counter exceeds uint64",
        )
    payload = b"".join(
        (
            UNIFORM_WORD_DOMAIN,
            bytes.fromhex(seed_digest),
            b"\x00",
            target_issue.encode("ascii"),
            b"\x00",
            bytes.fromhex(source_snapshot_digest),
            b"\x00",
            counter.to_bytes(8, "big"),
        )
    )
    return int.from_bytes(sha256(payload).digest()[:8], "big")


@dataclass(frozen=True)
class RandomControlTicketSlot:
    slot_ordinal: int
    control_kind: RandomControlKind
    six_red: SixRedCombination
    source_candidate_id: str | None
    source_candidate_rank: int | None
    expansion_ordinal: int | None
    priority_digest: str | None
    source_counter: int | None
    sample_word: int | None
    slot_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.slot_ordinal, int)
            or isinstance(self.slot_ordinal, bool)
            or not 1 <= self.slot_ordinal <= RANDOM_CONTROL_TICKET_BUDGET
        ):
            _reject("random_control_slot_ordinal_invalid", "slot ordinal must be in [1,70]")
        if not isinstance(self.control_kind, RandomControlKind):
            _reject("random_control_kind_invalid", "control kind is invalid")
        if not isinstance(self.six_red, SixRedCombination):
            _reject("random_control_ticket_invalid", "slot requires a SixRedCombination")
        if self.control_kind is RandomControlKind.RANDOM_FROM_POOL:
            _require_digest(self.source_candidate_id, field_name="source_candidate_id")
            _require_digest(self.priority_digest, field_name="priority_digest")
            if (
                not isinstance(self.source_candidate_rank, int)
                or isinstance(self.source_candidate_rank, bool)
                or not 1 <= self.source_candidate_rank <= RANDOM_POOL_CANDIDATE_COUNT
                or not isinstance(self.expansion_ordinal, int)
                or isinstance(self.expansion_ordinal, bool)
                or not 1 <= self.expansion_ordinal <= 7
            ):
                _reject(
                    "random_control_pool_slot_provenance_invalid",
                    "pool slots require candidate rank and expansion ordinal",
                )
            if self.source_counter is not None or self.sample_word is not None:
                _reject(
                    "random_control_pool_slot_provenance_invalid",
                    "pool slots cannot contain uniform counter evidence",
                )
        else:
            if any(
                value is not None
                for value in (
                    self.source_candidate_id,
                    self.source_candidate_rank,
                    self.expansion_ordinal,
                    self.priority_digest,
                )
            ):
                _reject(
                    "random_control_uniform_slot_provenance_invalid",
                    "uniform slots cannot contain pool candidate provenance",
                )
            if (
                not isinstance(self.source_counter, int)
                or isinstance(self.source_counter, bool)
                or not 0 <= self.source_counter <= UINT64_MAX
                or not isinstance(self.sample_word, int)
                or isinstance(self.sample_word, bool)
                or not 0 <= self.sample_word <= UINT64_MAX
                or self.sample_word >= UNIFORM_REJECTION_LIMIT
                or self.sample_word % SIX_RED_UNIVERSE.cardinality != self.six_red.lex_id
            ):
                _reject(
                    "random_control_uniform_slot_provenance_invalid",
                    "uniform slot counter, word, or mapped lex ID is invalid",
                )
        object.__setattr__(
            self,
            "slot_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.random-control.slot.v1",
            ),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "slot_ordinal": self.slot_ordinal,
            "control_kind": self.control_kind.value,
            "six_red": self.six_red.identity_payload(),
            "source_candidate_id": self.source_candidate_id,
            "source_candidate_rank": self.source_candidate_rank,
            "expansion_ordinal": self.expansion_ordinal,
            "priority_digest": self.priority_digest,
            "source_counter": self.source_counter,
            "sample_word": self.sample_word,
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "slot_digest": self.slot_digest}


@dataclass(frozen=True)
class RandomControlPortfolio70:
    control_kind: RandomControlKind
    seed_digest: str
    target_issue: str
    source_score_pool_snapshot_digest: str
    source_candidate_pool_digest: str
    source_history_latest_issue: str
    algorithm: str
    slots: tuple[RandomControlTicketSlot, ...]
    selected_candidate_ids: tuple[str, ...]
    selected_priority_digests: tuple[str, ...]
    counter_words_consumed: int
    modulo_rejection_count: int
    duplicate_rejection_count: int
    unique_ticket_count: int = field(init=False)
    duplicate_slot_count: int = field(init=False)
    slot_sequence_digest: str = field(init=False)
    portfolio_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.control_kind, RandomControlKind):
            _reject("random_control_kind_invalid", "control kind is invalid")
        _require_digest(self.seed_digest, field_name="seed_digest")
        target = _require_issue(self.target_issue, field_name="target_issue")
        latest = _require_issue(
            self.source_history_latest_issue,
            field_name="source_history_latest_issue",
        )
        if int(latest) >= int(target):
            _reject(
                "random_control_chronology_invalid",
                "source history must end strictly before target issue",
            )
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
            or len(self.slots) != RANDOM_CONTROL_TICKET_BUDGET
            or any(not isinstance(slot, RandomControlTicketSlot) for slot in self.slots)
        ):
            _reject(
                "random_control_slot_count_invalid",
                "portfolio requires exactly 70 immutable slots",
            )
        if tuple(slot.slot_ordinal for slot in self.slots) != tuple(range(1, 71)):
            _reject("random_control_slot_order_invalid", "slot order is invalid")
        if any(slot.control_kind is not self.control_kind for slot in self.slots):
            _reject("random_control_mixed_kind", "portfolio slots mix control kinds")
        for field_name in (
            "counter_words_consumed",
            "modulo_rejection_count",
            "duplicate_rejection_count",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                _reject(
                    "random_control_rejection_evidence_invalid",
                    f"{field_name} must be a non-negative integer",
                    field=field_name,
                )
        if self.control_kind is RandomControlKind.RANDOM_FROM_POOL:
            if self.algorithm != RANDOM_POOL_ALGORITHM:
                _reject("random_control_algorithm_invalid", "pool algorithm is invalid")
            if (
                not isinstance(self.selected_candidate_ids, tuple)
                or len(self.selected_candidate_ids) != RANDOM_POOL_CANDIDATE_COUNT
                or len(set(self.selected_candidate_ids)) != RANDOM_POOL_CANDIDATE_COUNT
                or not isinstance(self.selected_priority_digests, tuple)
                or len(self.selected_priority_digests) != RANDOM_POOL_CANDIDATE_COUNT
            ):
                _reject(
                    "random_control_pool_selection_invalid",
                    "pool control requires ten distinct selected candidates and priorities",
                )
            for value in (*self.selected_candidate_ids, *self.selected_priority_digests):
                _require_digest(value, field_name="pool_selection_digest")
            expected_parents = tuple(
                self.slots[index * 7].source_candidate_id
                for index in range(RANDOM_POOL_CANDIDATE_COUNT)
            )
            if self.selected_candidate_ids != expected_parents:
                _reject(
                    "random_control_pool_selection_invalid",
                    "selected candidates do not match slot parent order",
                )
            if any(
                self.slots[index * 7].priority_digest
                != self.selected_priority_digests[index]
                for index in range(RANDOM_POOL_CANDIDATE_COUNT)
            ):
                _reject(
                    "random_control_pool_selection_invalid",
                    "selected priorities do not match slot provenance",
                )
            if any(
                value != 0
                for value in (
                    self.counter_words_consumed,
                    self.modulo_rejection_count,
                    self.duplicate_rejection_count,
                )
            ):
                _reject(
                    "random_control_pool_rejection_evidence_invalid",
                    "pool controls cannot contain uniform rejection evidence",
                )
        else:
            if self.algorithm != UNIFORM_LEGAL_ALGORITHM:
                _reject("random_control_algorithm_invalid", "uniform algorithm is invalid")
            if self.selected_candidate_ids or self.selected_priority_digests:
                _reject(
                    "random_control_uniform_selection_invalid",
                    "uniform control cannot contain pool candidate selection",
                )
            if self.counter_words_consumed != (
                70 + self.modulo_rejection_count + self.duplicate_rejection_count
            ):
                _reject(
                    "random_control_rejection_evidence_invalid",
                    "uniform counter consumption does not match accepts and rejections",
                )
            counters = tuple(slot.source_counter for slot in self.slots)
            if counters != tuple(sorted(counters)) or len(set(counters)) != 70:
                _reject(
                    "random_control_uniform_counter_order_invalid",
                    "accepted uniform counters must be unique and increasing",
                )
        unique_count = len({slot.six_red.combination_id for slot in self.slots})
        duplicate_count = len(self.slots) - unique_count
        if self.control_kind is RandomControlKind.UNIFORM_LEGAL and unique_count != 70:
            _reject(
                "random_control_uniform_unique70_invalid",
                "uniform-legal control requires 70 unique tickets",
            )
        slot_digest = canonical_digest(
            [slot.as_dict() for slot in self.slots],
            domain="dehps.random-control.slot-sequence.v1",
        )
        object.__setattr__(self, "unique_ticket_count", unique_count)
        object.__setattr__(self, "duplicate_slot_count", duplicate_count)
        object.__setattr__(self, "slot_sequence_digest", slot_digest)
        object.__setattr__(
            self,
            "portfolio_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.random-control.portfolio70.v1",
            ),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": RANDOM_CONTROL_PORTFOLIO_VERSION,
            "line_key": LINE_KEY,
            "research_only": RESEARCH_ONLY,
            "contract": RANDOM_CONTROL_CONTRACT_V1.normative_identity(),
            "control_kind": self.control_kind.value,
            "seed_digest": self.seed_digest,
            "target_issue": self.target_issue,
            "source_score_pool_snapshot_digest": self.source_score_pool_snapshot_digest,
            "source_candidate_pool_digest": self.source_candidate_pool_digest,
            "source_history_latest_issue": self.source_history_latest_issue,
            "algorithm": self.algorithm,
            "paid_ticket_slot_count": len(self.slots),
            "unique_ticket_count": self.unique_ticket_count,
            "duplicate_slot_count": self.duplicate_slot_count,
            "selected_candidate_ids": list(self.selected_candidate_ids),
            "selected_priority_digests": list(self.selected_priority_digests),
            "counter_words_consumed": self.counter_words_consumed,
            "modulo_rejection_count": self.modulo_rejection_count,
            "duplicate_rejection_count": self.duplicate_rejection_count,
            "slot_sequence_digest": self.slot_sequence_digest,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "slots": [slot.as_dict() for slot in self.slots],
            "portfolio_digest": self.portfolio_digest,
        }


def _verify_score_pool(score_pool: SevenRedScoredCandidatePoolSnapshot) -> None:
    if not isinstance(score_pool, SevenRedScoredCandidatePoolSnapshot):
        _reject("random_control_score_pool_invalid", "score pool is invalid")
    try:
        SevenRedScorePoolVerifier().verify(score_pool)
    except SevenRedScorePoolViolation as exc:
        raise RandomControlViolation(
            "random_control_score_pool_verification_failed",
            "parent score pool failed deterministic replay",
            cause=exc.code,
        ) from exc


def compile_random_from_pool_control(
    *,
    score_pool: SevenRedScoredCandidatePoolSnapshot,
    seed_digest: str,
) -> RandomControlPortfolio70:
    _verify_score_pool(score_pool)
    return _compile_random_from_pool_verified(
        score_pool=score_pool,
        seed_digest=seed_digest,
    )


def _compile_random_from_pool_verified(
    *,
    score_pool: SevenRedScoredCandidatePoolSnapshot,
    seed_digest: str,
) -> RandomControlPortfolio70:
    seed = _require_digest(seed_digest, field_name="seed_digest")
    rows = score_pool.candidate_pool.rows
    if len(rows) < RANDOM_POOL_CANDIDATE_COUNT:
        _reject(
            "random_control_pool_insufficient",
            "random-from-pool requires at least ten candidates",
        )
    prioritized = sorted(
        (
            _pool_priority(
                seed_digest=seed,
                target_issue=score_pool.target_issue,
                source_snapshot_digest=score_pool.snapshot_digest,
                candidate_id=row.candidate.candidate_id,
            ),
            row.candidate.lex_id,
            row,
        )
        for row in rows
    )
    selected = prioritized[:RANDOM_POOL_CANDIDATE_COUNT]
    slots: list[RandomControlTicketSlot] = []
    for candidate_rank, (priority, _lex_id, row) in enumerate(selected, start=1):
        for expansion in expand_seven_red_candidate(row.candidate):
            slots.append(
                RandomControlTicketSlot(
                    slot_ordinal=len(slots) + 1,
                    control_kind=RandomControlKind.RANDOM_FROM_POOL,
                    six_red=expansion.six_red,
                    source_candidate_id=row.candidate.candidate_id,
                    source_candidate_rank=candidate_rank,
                    expansion_ordinal=expansion.ordinal,
                    priority_digest=priority,
                    source_counter=None,
                    sample_word=None,
                )
            )
    return RandomControlPortfolio70(
        control_kind=RandomControlKind.RANDOM_FROM_POOL,
        seed_digest=seed,
        target_issue=score_pool.target_issue,
        source_score_pool_snapshot_digest=score_pool.snapshot_digest,
        source_candidate_pool_digest=score_pool.candidate_pool.artifact_digest,
        source_history_latest_issue=score_pool.source_vector.source_history_latest_issue,
        algorithm=RANDOM_POOL_ALGORITHM,
        slots=tuple(slots),
        selected_candidate_ids=tuple(item[2].candidate.candidate_id for item in selected),
        selected_priority_digests=tuple(item[0] for item in selected),
        counter_words_consumed=0,
        modulo_rejection_count=0,
        duplicate_rejection_count=0,
    )


def compile_uniform_legal_control(
    *,
    score_pool: SevenRedScoredCandidatePoolSnapshot,
    seed_digest: str,
) -> RandomControlPortfolio70:
    _verify_score_pool(score_pool)
    return _compile_uniform_legal_verified(
        score_pool=score_pool,
        seed_digest=seed_digest,
    )


def _compile_uniform_legal_verified(
    *,
    score_pool: SevenRedScoredCandidatePoolSnapshot,
    seed_digest: str,
) -> RandomControlPortfolio70:
    seed = _require_digest(seed_digest, field_name="seed_digest")
    seen: set[int] = set()
    accepted: list[tuple[int, int, int]] = []
    counter = 0
    modulo_rejections = 0
    duplicate_rejections = 0
    while len(accepted) < RANDOM_CONTROL_TICKET_BUDGET:
        if counter > UINT64_MAX:
            _reject(
                "random_control_counter_overflow",
                "uniform-legal sampling exhausted uint64 counter space",
            )
        word = _uniform_word(
            seed_digest=seed,
            target_issue=score_pool.target_issue,
            source_snapshot_digest=score_pool.snapshot_digest,
            counter=counter,
        )
        current_counter = counter
        counter += 1
        if word >= UNIFORM_REJECTION_LIMIT:
            modulo_rejections += 1
            continue
        lex_id = word % SIX_RED_UNIVERSE.cardinality
        if lex_id in seen:
            duplicate_rejections += 1
            continue
        seen.add(lex_id)
        accepted.append((current_counter, word, lex_id))
    slots = tuple(
        RandomControlTicketSlot(
            slot_ordinal=ordinal,
            control_kind=RandomControlKind.UNIFORM_LEGAL,
            six_red=SixRedCombination(
                candidate_unrank(lex_id, universe=SIX_RED_UNIVERSE)
            ),
            source_candidate_id=None,
            source_candidate_rank=None,
            expansion_ordinal=None,
            priority_digest=None,
            source_counter=source_counter,
            sample_word=word,
        )
        for ordinal, (source_counter, word, lex_id) in enumerate(accepted, start=1)
    )
    return RandomControlPortfolio70(
        control_kind=RandomControlKind.UNIFORM_LEGAL,
        seed_digest=seed,
        target_issue=score_pool.target_issue,
        source_score_pool_snapshot_digest=score_pool.snapshot_digest,
        source_candidate_pool_digest=score_pool.candidate_pool.artifact_digest,
        source_history_latest_issue=score_pool.source_vector.source_history_latest_issue,
        algorithm=UNIFORM_LEGAL_ALGORITHM,
        slots=slots,
        selected_candidate_ids=(),
        selected_priority_digests=(),
        counter_words_consumed=counter,
        modulo_rejection_count=modulo_rejections,
        duplicate_rejection_count=duplicate_rejections,
    )


@dataclass(frozen=True)
class RandomControlCohortSnapshot:
    source_score_pool: SevenRedScoredCandidatePoolSnapshot = field(repr=False)
    seed_policy: RandomControlSeedPolicy
    portfolios: tuple[RandomControlPortfolio70, ...]
    cohort_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.source_score_pool, SevenRedScoredCandidatePoolSnapshot):
            _reject("random_control_score_pool_invalid", "cohort score pool is invalid")
        if not isinstance(self.seed_policy, RandomControlSeedPolicy):
            _reject("random_control_seed_policy_invalid", "seed policy is invalid")
        if (
            not isinstance(self.portfolios, tuple)
            or len(self.portfolios) != 2 * len(self.seed_policy.seed_digests)
            or any(not isinstance(row, RandomControlPortfolio70) for row in self.portfolios)
        ):
            _reject(
                "random_control_cohort_completeness_invalid",
                "cohort requires both controls for every seed",
            )
        expected_keys = tuple(
            (seed, kind)
            for seed in self.seed_policy.seed_digests
            for kind in (
                RandomControlKind.RANDOM_FROM_POOL,
                RandomControlKind.UNIFORM_LEGAL,
            )
        )
        actual_keys = tuple((row.seed_digest, row.control_kind) for row in self.portfolios)
        if actual_keys != expected_keys:
            _reject(
                "random_control_cohort_order_invalid",
                "cohort seed/control order or completeness is invalid",
            )
        source = self.source_score_pool
        if any(
            row.target_issue != source.target_issue
            or row.source_score_pool_snapshot_digest != source.snapshot_digest
            or row.source_candidate_pool_digest != source.candidate_pool.artifact_digest
            for row in self.portfolios
        ):
            _reject(
                "random_control_cohort_source_mismatch",
                "cohort portfolios do not share the parent score-pool source",
            )
        object.__setattr__(
            self,
            "cohort_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.random-control.cohort.v1",
            ),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": RANDOM_CONTROL_COHORT_VERSION,
            "line_key": LINE_KEY,
            "research_only": RESEARCH_ONLY,
            "contract": RANDOM_CONTROL_CONTRACT_V1.normative_identity(),
            "target_issue": self.source_score_pool.target_issue,
            "source_score_pool_snapshot_digest": self.source_score_pool.snapshot_digest,
            "source_candidate_pool_digest": (
                self.source_score_pool.candidate_pool.artifact_digest
            ),
            "source_history_latest_issue": (
                self.source_score_pool.source_vector.source_history_latest_issue
            ),
            "seed_policy": self.seed_policy.as_dict(),
            "selection_policy": "no_best_seed",
            "portfolio_count": len(self.portfolios),
            "portfolio_digests": [row.portfolio_digest for row in self.portfolios],
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.identity_payload(),
            "portfolios": [row.as_dict() for row in self.portfolios],
            "cohort_digest": self.cohort_digest,
        }


def compile_random_control_cohort(
    *,
    score_pool: SevenRedScoredCandidatePoolSnapshot,
    seed_policy: RandomControlSeedPolicy,
) -> RandomControlCohortSnapshot:
    _verify_score_pool(score_pool)
    if not isinstance(seed_policy, RandomControlSeedPolicy):
        _reject("random_control_seed_policy_invalid", "seed policy is invalid")
    portfolios: list[RandomControlPortfolio70] = []
    for seed in seed_policy.seed_digests:
        portfolios.append(
            _compile_random_from_pool_verified(
                score_pool=score_pool,
                seed_digest=seed,
            )
        )
        portfolios.append(
            _compile_uniform_legal_verified(
                score_pool=score_pool,
                seed_digest=seed,
            )
        )
    return RandomControlCohortSnapshot(
        source_score_pool=score_pool,
        seed_policy=seed_policy,
        portfolios=tuple(portfolios),
    )


@dataclass(frozen=True)
class RandomControlPortfolioSettlement:
    portfolio_digest: str
    seed_digest: str
    control_kind: RandomControlKind
    slot_hit_histogram: tuple[int, ...]
    unique_ticket_hit_histogram: tuple[int, ...]
    row_digest: str = field(init=False)

    def __post_init__(self) -> None:
        _require_digest(self.portfolio_digest, field_name="portfolio_digest")
        _require_digest(self.seed_digest, field_name="seed_digest")
        if not isinstance(self.control_kind, RandomControlKind):
            _reject("random_control_kind_invalid", "settlement control kind is invalid")
        for field_name, histogram in (
            ("slot_hit_histogram", self.slot_hit_histogram),
            ("unique_ticket_hit_histogram", self.unique_ticket_hit_histogram),
        ):
            if (
                not isinstance(histogram, tuple)
                or len(histogram) != 7
                or any(
                    not isinstance(value, int) or isinstance(value, bool) or value < 0
                    for value in histogram
                )
            ):
                _reject(
                    "random_control_settlement_histogram_invalid",
                    f"{field_name} is invalid",
                    field=field_name,
                )
        object.__setattr__(
            self,
            "row_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.random-control.settlement-row.v1",
            ),
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "portfolio_digest": self.portfolio_digest,
            "seed_digest": self.seed_digest,
            "control_kind": self.control_kind.value,
            "slot_hit_histogram": list(self.slot_hit_histogram),
            "unique_ticket_hit_histogram": list(self.unique_ticket_hit_histogram),
        }


def _settle_portfolio(
    portfolio: RandomControlPortfolio70,
    actual: SixRedCombination,
) -> RandomControlPortfolioSettlement:
    actual_set = set(actual.sorted_red_numbers)
    slot_counts = tuple(
        len(actual_set.intersection(slot.six_red.sorted_red_numbers))
        for slot in portfolio.slots
    )
    unique_tickets = {
        slot.six_red.combination_id: slot.six_red for slot in portfolio.slots
    }
    unique_counts = tuple(
        len(actual_set.intersection(ticket.sorted_red_numbers))
        for ticket in unique_tickets.values()
    )
    return RandomControlPortfolioSettlement(
        portfolio_digest=portfolio.portfolio_digest,
        seed_digest=portfolio.seed_digest,
        control_kind=portfolio.control_kind,
        slot_hit_histogram=tuple(Counter(slot_counts).get(value, 0) for value in range(7)),
        unique_ticket_hit_histogram=tuple(
            Counter(unique_counts).get(value, 0) for value in range(7)
        ),
    )


@dataclass(frozen=True)
class RandomControlCohortSettlement:
    cohort: RandomControlCohortSnapshot = field(repr=False)
    actual_issue: str
    actual: SixRedCombination
    rows: tuple[RandomControlPortfolioSettlement, ...]
    settlement_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.cohort, RandomControlCohortSnapshot):
            _reject("random_control_cohort_invalid", "settlement cohort is invalid")
        issue = _require_issue(self.actual_issue, field_name="actual_issue")
        if issue != self.cohort.source_score_pool.target_issue:
            _reject(
                "random_control_settlement_issue_mismatch",
                "actual issue must equal cohort target issue",
            )
        if not isinstance(self.actual, SixRedCombination):
            _reject("random_control_settlement_actual_invalid", "actual is invalid")
        expected = tuple(
            _settle_portfolio(portfolio, self.actual)
            for portfolio in self.cohort.portfolios
        )
        if self.rows != expected:
            _reject(
                "random_control_settlement_rows_mismatch",
                "settlement must cover every cohort portfolio in canonical order",
            )
        for portfolio, row in zip(self.cohort.portfolios, self.rows, strict=True):
            if (
                sum(row.slot_hit_histogram) != 70
                or sum(row.unique_ticket_hit_histogram) != portfolio.unique_ticket_count
            ):
                _reject(
                    "random_control_settlement_histogram_total_mismatch",
                    "settlement histogram totals are invalid",
                )
        object.__setattr__(
            self,
            "settlement_digest",
            canonical_digest(
                self.identity_payload(),
                domain="dehps.random-control.cohort-settlement.v1",
            ),
        )

    @classmethod
    def evaluate(
        cls,
        *,
        cohort: RandomControlCohortSnapshot,
        actual_issue: str,
        actual_red_numbers: Sequence[object],
    ) -> RandomControlCohortSettlement:
        if not isinstance(cohort, RandomControlCohortSnapshot):
            _reject("random_control_cohort_invalid", "settlement cohort is invalid")
        actual = SixRedCombination.from_numbers(actual_red_numbers)
        rows = tuple(
            _settle_portfolio(portfolio, actual)
            for portfolio in cohort.portfolios
        )
        return cls(
            cohort=cohort,
            actual_issue=actual_issue,
            actual=actual,
            rows=rows,
        )

    def identity_payload(self) -> dict[str, Any]:
        return {
            "artifact_version": RANDOM_CONTROL_SETTLEMENT_VERSION,
            "line_key": LINE_KEY,
            "research_only": RESEARCH_ONLY,
            "contract": RANDOM_CONTROL_CONTRACT_V1.normative_identity(),
            "cohort_digest": self.cohort.cohort_digest,
            "actual_issue": self.actual_issue,
            "actual": self.actual.identity_payload(),
            "rows": [
                {**row.identity_payload(), "row_digest": row.row_digest}
                for row in self.rows
            ],
        }

    def as_dict(self) -> dict[str, Any]:
        return {**self.identity_payload(), "settlement_digest": self.settlement_digest}


class RandomControlCohortVerifier:
    def verify(self, cohort: RandomControlCohortSnapshot) -> None:
        if not isinstance(cohort, RandomControlCohortSnapshot):
            _reject("random_control_cohort_invalid", "cohort is invalid")
        replay = compile_random_control_cohort(
            score_pool=cohort.source_score_pool,
            seed_policy=cohort.seed_policy,
        )
        if replay.cohort_digest != cohort.cohort_digest:
            _reject(
                "random_control_cohort_replay_mismatch",
                "cohort does not match deterministic source replay",
                expected=replay.cohort_digest,
                actual=cohort.cohort_digest,
            )
