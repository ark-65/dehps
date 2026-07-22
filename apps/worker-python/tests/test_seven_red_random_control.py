from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import inspect

import numpy as np
import pytest

from dehps.seven_red import (
    RANDOM_POOL_ALGORITHM,
    RANDOM_POOL_CANDIDATE_COUNT,
    SIX_RED_UNIVERSE,
    UNIFORM_LEGAL_ALGORITHM,
    UNIFORM_REJECTION_LIMIT,
    RandomControlCohortSettlement,
    RandomControlCohortVerifier,
    RandomControlKind,
    RandomControlSeedPolicy,
    RandomControlViolation,
    SevenRedScorePoolConfig,
    SixRedFullScoreVector,
    compile_random_control_cohort,
    compile_random_from_pool_control,
    compile_seven_red_score_pool,
    compile_uniform_legal_control,
)
from dehps.seven_red import random_control as random_control_module


_DIGEST = "a" * 64
_OTHER_DIGEST = "b" * 64
_THIRD_DIGEST = "c" * 64
_COMMIT = "d" * 40


def _vector(*, values: dict[int, int] | None = None) -> SixRedFullScoreVector:
    ticks = np.zeros(SIX_RED_UNIVERSE.cardinality, dtype=np.int64)
    for lex_id, value in (values or {}).items():
        ticks[lex_id] = value
    ticks.setflags(write=False)
    return SixRedFullScoreVector(
        score_ticks=ticks,
        source_full_score_artifact_digest=_DIGEST,
        source_full_score_payload_digest=_OTHER_DIGEST,
        source_full_score_scores_digest=_DIGEST,
        source_runtime_envelope_digest=_OTHER_DIGEST,
        source_candidate_package_digest=_DIGEST,
        source_history_snapshot_digest=_OTHER_DIGEST,
        source_history_latest_issue="2026001",
        source_window_artifact_digest=_DIGEST,
        source_window_spec_digest=_OTHER_DIGEST,
        source_weights_digest=_DIGEST,
        source_config_index=0,
        source_config_count=1,
        source_code_commit=_COMMIT,
    )


def _score_pool(*, values: dict[int, int] | None = None):
    return compile_seven_red_score_pool(
        source_vector=_vector(values=values),
        configuration=SevenRedScorePoolConfig(seed_top_n=1, pool_top_n=27),
        target_issue="2026002",
    )


def _policy() -> RandomControlSeedPolicy:
    return RandomControlSeedPolicy((_DIGEST, _OTHER_DIGEST))


def _reference_uniform_ids(score_pool, seed_digest: str) -> tuple[int, ...]:
    seen: set[int] = set()
    result: list[int] = []
    counter = 0
    while len(result) < 70:
        payload = b"".join(
            (
                b"dehps.random-control.uniform-legal-word.v1\x00",
                bytes.fromhex(seed_digest),
                b"\x00",
                score_pool.target_issue.encode("ascii"),
                b"\x00",
                bytes.fromhex(score_pool.snapshot_digest),
                b"\x00",
                counter.to_bytes(8, "big"),
            )
        )
        counter += 1
        word = int.from_bytes(sha256(payload).digest()[:8], "big")
        if word >= UNIFORM_REJECTION_LIMIT:
            continue
        lex_id = word % SIX_RED_UNIVERSE.cardinality
        if lex_id in seen:
            continue
        seen.add(lex_id)
        result.append(lex_id)
    return tuple(result)


def test_seed_policy_has_no_defaults_and_requires_two_sorted_unique_seeds() -> None:
    signature = inspect.signature(RandomControlSeedPolicy)
    assert signature.parameters["seed_digests"].default is inspect.Parameter.empty

    for seeds, code in (
        ((), "random_control_seed_count_invalid"),
        ((_DIGEST,), "random_control_seed_count_invalid"),
        ((_DIGEST, _DIGEST), "random_control_seed_order_invalid"),
        ((_OTHER_DIGEST, _DIGEST), "random_control_seed_order_invalid"),
        ((_DIGEST, "A" * 64), "random_control_digest_invalid"),
    ):
        with pytest.raises(RandomControlViolation) as error:
            RandomControlSeedPolicy(seeds)
        assert error.value.code == code

    policy = _policy()
    assert policy.seed_digests == (_DIGEST, _OTHER_DIGEST)
    assert policy.identity_payload()["selection_policy"] == "no_best_seed"


def test_cohort_contains_both_controls_for_every_seed_without_best_seed() -> None:
    cohort = compile_random_control_cohort(
        score_pool=_score_pool(),
        seed_policy=_policy(),
    )

    assert [(row.seed_digest, row.control_kind) for row in cohort.portfolios] == [
        (_DIGEST, RandomControlKind.RANDOM_FROM_POOL),
        (_DIGEST, RandomControlKind.UNIFORM_LEGAL),
        (_OTHER_DIGEST, RandomControlKind.RANDOM_FROM_POOL),
        (_OTHER_DIGEST, RandomControlKind.UNIFORM_LEGAL),
    ]
    assert len(cohort.portfolios) == 4
    identity = cohort.identity_payload()
    assert identity["selection_policy"] == "no_best_seed"
    assert "best_seed" not in identity
    assert "selected_seed" not in identity
    golden = random_control_module.RANDOM_CONTROL_GOLDEN_SUITE
    assert cohort.seed_policy.policy_digest == golden["expected_seed_policy_digest"]
    assert [row.portfolio_digest for row in cohort.portfolios] == golden[
        "expected_portfolio_digests"
    ]
    assert cohort.cohort_digest == golden["expected_cohort_digest"]
    RandomControlCohortVerifier().verify(cohort)


def test_random_from_pool_reference_priority_and_paid_slot_multiplicity() -> None:
    score_pool = _score_pool()
    portfolio = compile_random_from_pool_control(
        score_pool=score_pool,
        seed_digest=_DIGEST,
    )
    expected = sorted(
        (
            random_control_module._pool_priority(
                seed_digest=_DIGEST,
                target_issue=score_pool.target_issue,
                source_snapshot_digest=score_pool.snapshot_digest,
                candidate_id=row.candidate.candidate_id,
            ),
            row.candidate.lex_id,
            row.candidate.candidate_id,
        )
        for row in reversed(score_pool.candidate_pool.rows)
    )[:RANDOM_POOL_CANDIDATE_COUNT]

    assert portfolio.algorithm == RANDOM_POOL_ALGORITHM
    assert portfolio.selected_candidate_ids == tuple(item[2] for item in expected)
    assert portfolio.selected_priority_digests == tuple(item[0] for item in expected)
    assert len(portfolio.slots) == 70
    assert len(set(portfolio.selected_candidate_ids)) == 10
    assert portfolio.unique_ticket_count == 61
    assert portfolio.duplicate_slot_count == 9


def test_uniform_legal_matches_independent_sha256_reference() -> None:
    score_pool = _score_pool()
    portfolio = compile_uniform_legal_control(
        score_pool=score_pool,
        seed_digest=_DIGEST,
    )

    assert portfolio.algorithm == UNIFORM_LEGAL_ALGORITHM
    assert tuple(slot.six_red.lex_id for slot in portfolio.slots) == (
        _reference_uniform_ids(score_pool, _DIGEST)
    )
    assert portfolio.unique_ticket_count == 70
    assert portfolio.duplicate_slot_count == 0
    assert portfolio.counter_words_consumed == (
        70 + portfolio.modulo_rejection_count + portfolio.duplicate_rejection_count
    )


def test_uniform_legal_records_forced_modulo_and_duplicate_rejections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forced_word(**kwargs) -> int:
        counter = kwargs["counter"]
        if counter == 0:
            return (1 << 64) - 1
        if counter in (1, 2):
            return 0
        return counter - 2

    monkeypatch.setattr(random_control_module, "_uniform_word", forced_word)
    portfolio = compile_uniform_legal_control(
        score_pool=_score_pool(),
        seed_digest=_DIGEST,
    )

    assert portfolio.modulo_rejection_count == 1
    assert portfolio.duplicate_rejection_count == 1
    assert portfolio.counter_words_consumed == 72
    assert [slot.six_red.lex_id for slot in portfolio.slots] == list(range(70))
    assert [slot.source_counter for slot in portfolio.slots[:3]] == [1, 3, 4]


def test_uniform_counter_overflow_fails_closed() -> None:
    with pytest.raises(RandomControlViolation) as error:
        random_control_module._uniform_word(
            seed_digest=_DIGEST,
            target_issue="2026002",
            source_snapshot_digest=_OTHER_DIGEST,
            counter=1 << 64,
        )
    assert error.value.code == "random_control_counter_overflow"


def test_seed_source_and_target_are_digest_sensitive_and_replayable() -> None:
    score_pool = _score_pool()
    first = compile_random_control_cohort(
        score_pool=score_pool,
        seed_policy=_policy(),
    )
    replay = compile_random_control_cohort(
        score_pool=score_pool,
        seed_policy=_policy(),
    )
    changed_seed = compile_random_control_cohort(
        score_pool=score_pool,
        seed_policy=RandomControlSeedPolicy((_DIGEST, _THIRD_DIGEST)),
    )
    changed_source = compile_random_control_cohort(
        score_pool=_score_pool(values={0: 1}),
        seed_policy=_policy(),
    )

    assert replay.cohort_digest == first.cohort_digest
    assert changed_seed.cohort_digest != first.cohort_digest
    assert changed_source.cohort_digest != first.cohort_digest


def test_compiler_interface_is_outcome_free() -> None:
    for function in (
        compile_random_from_pool_control,
        compile_uniform_legal_control,
        compile_random_control_cohort,
    ):
        parameters = inspect.signature(function).parameters
        assert "actual_issue" not in parameters
        assert "actual_red_numbers" not in parameters


def test_settlement_covers_every_seed_and_control_in_cohort_order() -> None:
    cohort = compile_random_control_cohort(
        score_pool=_score_pool(),
        seed_policy=_policy(),
    )
    settlement = RandomControlCohortSettlement.evaluate(
        cohort=cohort,
        actual_issue="2026002",
        actual_red_numbers=(1, 2, 3, 4, 5, 6),
    )

    assert len(settlement.rows) == len(cohort.portfolios) == 4
    assert [
        (row.seed_digest, row.control_kind) for row in settlement.rows
    ] == [
        (portfolio.seed_digest, portfolio.control_kind)
        for portfolio in cohort.portfolios
    ]
    for portfolio, row in zip(cohort.portfolios, settlement.rows, strict=True):
        assert sum(row.slot_hit_histogram) == 70
        assert sum(row.unique_ticket_hit_histogram) == portfolio.unique_ticket_count


def test_settlement_rejects_wrong_issue_and_forged_rows() -> None:
    cohort = compile_random_control_cohort(
        score_pool=_score_pool(),
        seed_policy=_policy(),
    )
    with pytest.raises(RandomControlViolation) as error:
        RandomControlCohortSettlement.evaluate(
            cohort=cohort,
            actual_issue="2026003",
            actual_red_numbers=(1, 2, 3, 4, 5, 6),
        )
    assert error.value.code == "random_control_settlement_issue_mismatch"

    valid = RandomControlCohortSettlement.evaluate(
        cohort=cohort,
        actual_issue="2026002",
        actual_red_numbers=(1, 2, 3, 4, 5, 6),
    )
    with pytest.raises(RandomControlViolation) as error:
        replace(valid, rows=valid.rows[:-1])
    assert error.value.code == "random_control_settlement_rows_mismatch"


def test_forged_parent_score_pool_fails_replay_before_sampling() -> None:
    score_pool = _score_pool()
    forged = replace(score_pool, target_issue="2026003")

    with pytest.raises(RandomControlViolation) as error:
        compile_random_control_cohort(
            score_pool=forged,
            seed_policy=_policy(),
        )
    assert error.value.code == "random_control_score_pool_verification_failed"
