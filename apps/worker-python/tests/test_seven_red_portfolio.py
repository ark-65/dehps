from __future__ import annotations

from dataclasses import replace
import inspect

import numpy as np
import pytest

from dehps.seven_red import (
    EQUAL_COST_PORTFOLIO_CONTRACT_V1,
    EQUAL_COST_TICKET_BUDGET,
    DiversifiedSevenRedTop10Snapshot,
    EqualCostPortfolioSettlement,
    EqualCostPortfolioSource,
    EqualCostPortfolioVerifier,
    EqualCostPortfolioViolation,
    RawSevenRedTop10Snapshot,
    SIX_RED_UNIVERSE,
    SevenRedDiversificationWeights,
    SevenRedDiversityAuditSnapshot,
    SevenRedScorePoolConfig,
    SixRedCombination,
    SixRedFullScoreVector,
    compile_diversified_equal_cost_portfolio,
    compile_raw_equal_cost_portfolio,
    compile_seven_red_score_pool,
    compile_six_red_top70_portfolio,
)


_DIGEST = "a" * 64
_OTHER_DIGEST = "b" * 64
_COMMIT = "c" * 40


def _vector(
    *,
    values: dict[int, int] | None = None,
    fill: int = 0,
    latest_issue: str = "2026001",
) -> SixRedFullScoreVector:
    ticks = np.full(SIX_RED_UNIVERSE.cardinality, fill, dtype=np.int64)
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
        source_history_latest_issue=latest_issue,
        source_window_artifact_digest=_DIGEST,
        source_window_spec_digest=_OTHER_DIGEST,
        source_weights_digest=_DIGEST,
        source_config_index=0,
        source_config_count=1,
        source_code_commit=_COMMIT,
    )


def _raw_score_pool(*, changed: bool = False):
    source = _vector(values={0: 1} if changed else None)
    score_pool = compile_seven_red_score_pool(
        source_vector=source,
        configuration=SevenRedScorePoolConfig(seed_top_n=1, pool_top_n=10),
        target_issue="2026002",
    )
    return score_pool, RawSevenRedTop10Snapshot.build(score_pool.candidate_pool)


def _diversified_score_pool():
    seed_numbers = (
        (1, 2, 3, 4, 5, 6),
        (7, 8, 9, 10, 11, 12),
        (13, 14, 15, 16, 17, 18),
        (19, 20, 21, 22, 23, 24),
        (25, 26, 27, 28, 29, 30),
        (1, 7, 13, 19, 25, 31),
        (2, 8, 14, 20, 26, 32),
        (3, 9, 15, 21, 27, 33),
        (4, 10, 16, 22, 28, 31),
        (5, 11, 17, 23, 29, 32),
    )
    values = {SixRedCombination(numbers).lex_id: 100 for numbers in seed_numbers}
    score_pool = compile_seven_red_score_pool(
        source_vector=_vector(values=values),
        configuration=SevenRedScorePoolConfig(seed_top_n=10, pool_top_n=270),
        target_issue="2026002",
    )
    raw = RawSevenRedTop10Snapshot.build(score_pool.candidate_pool)
    audit = SevenRedDiversityAuditSnapshot.build(score_pool.candidate_pool, raw)
    diversified = DiversifiedSevenRedTop10Snapshot.build(
        audit,
        SevenRedDiversificationWeights(1, 1, 1, 1),
    )
    return score_pool, diversified


def test_contract_freezes_paid_slot_and_post_outcome_boundary() -> None:
    identity = EQUAL_COST_PORTFOLIO_CONTRACT_V1.normative_identity()

    assert identity["family"] == "seven-red-equal-cost-portfolio"
    assert EQUAL_COST_TICKET_BUDGET == 70
    assert "actual_issue" not in inspect.signature(compile_raw_equal_cost_portfolio).parameters
    assert "actual_red_numbers" not in inspect.signature(
        compile_six_red_top70_portfolio
    ).parameters


def test_raw_top10_preserves_70_paid_slots_and_duplicate_multiplicity() -> None:
    score_pool, raw = _raw_score_pool()

    portfolio = compile_raw_equal_cost_portfolio(
        score_pool=score_pool,
        raw_top10=raw,
    )

    assert portfolio.source_kind is EqualCostPortfolioSource.RAW_SEVEN_RED_TOP10
    assert len(portfolio.slots) == 70
    assert portfolio.unique_ticket_count == 61
    assert portfolio.duplicate_slot_count == 9
    common = SixRedCombination((1, 2, 3, 4, 5, 6)).combination_id
    assert sum(slot.six_red.combination_id == common for slot in portfolio.slots) == 10
    assert [slot.source_rank for slot in portfolio.slots[:14]] == [1] * 7 + [2] * 7
    assert [slot.expansion_ordinal for slot in portfolio.slots[:7]] == list(range(1, 8))
    EqualCostPortfolioVerifier().verify_raw(
        portfolio,
        score_pool=score_pool,
        raw_top10=raw,
    )


def test_diversified_top10_compiles_exactly_70_unique_slots() -> None:
    score_pool, diversified = _diversified_score_pool()

    portfolio = compile_diversified_equal_cost_portfolio(
        score_pool=score_pool,
        diversified_top10=diversified,
    )

    assert portfolio.source_kind is EqualCostPortfolioSource.DIVERSIFIED_SEVEN_RED_TOP10
    assert portfolio.unique_ticket_count == 70
    assert portfolio.duplicate_slot_count == 0
    assert [slot.source_rank for slot in portfolio.slots[:14]] == [1] * 7 + [2] * 7
    EqualCostPortfolioVerifier().verify_diversified(
        portfolio,
        score_pool=score_pool,
        diversified_top10=diversified,
    )


def test_six_red_top70_uses_exact_ticks_and_lower_lex_id_at_boundary_tie() -> None:
    values = {lex_id: 10 for lex_id in range(69)}
    values.update({70: 5, 80: 5})
    portfolio = compile_six_red_top70_portfolio(
        source_vector=_vector(values=values, fill=-100),
        target_issue="2026002",
    )

    assert portfolio.source_kind is EqualCostPortfolioSource.SIX_RED_TOP70
    assert portfolio.unique_ticket_count == 70
    assert [slot.six_red.lex_id for slot in portfolio.slots[:69]] == list(range(69))
    assert portfolio.slots[-1].six_red.lex_id == 70
    assert portfolio.slots[-1].source_score_tick == 5
    assert all(slot.parent_candidate_id is None for slot in portfolio.slots)


def test_negative_six_red_top70_ties_are_deterministic() -> None:
    portfolio = compile_six_red_top70_portfolio(
        source_vector=_vector(fill=-3),
        target_issue="2026002",
    )

    assert [slot.six_red.lex_id for slot in portfolio.slots] == list(range(70))
    assert {slot.source_score_tick for slot in portfolio.slots} == {-3}


def test_six_red_top70_handles_int64_min_without_negation_overflow() -> None:
    minimum = int(np.iinfo(np.int64).min)
    values = {lex_id: 0 for lex_id in range(68)}
    values[100] = minimum + 1
    portfolio = compile_six_red_top70_portfolio(
        source_vector=_vector(values=values, fill=minimum),
        target_issue="2026002",
    )

    assert [slot.six_red.lex_id for slot in portfolio.slots[:68]] == list(range(68))
    assert portfolio.slots[68].six_red.lex_id == 100
    assert portfolio.slots[68].source_score_tick == minimum + 1
    assert portfolio.slots[69].six_red.lex_id == 68
    assert portfolio.slots[69].source_score_tick == minimum


def test_raw_settlement_reports_paid_and_unique_exact_hits_separately() -> None:
    score_pool, raw = _raw_score_pool()
    portfolio = compile_raw_equal_cost_portfolio(
        score_pool=score_pool,
        raw_top10=raw,
    )

    settlement = EqualCostPortfolioSettlement.evaluate(
        portfolio=portfolio,
        actual_issue="2026002",
        actual_red_numbers=(1, 2, 3, 4, 5, 6),
    )

    assert sum(settlement.slot_hit_histogram) == 70
    assert sum(settlement.unique_ticket_hit_histogram) == 61
    assert settlement.slot_weighted_exact_red6_count == 10
    assert settlement.unique_ticket_exact_red6_count == 1
    assert settlement.slot_hit_histogram[5] == 60
    assert settlement.unique_ticket_hit_histogram[5] == 60


def test_settlement_rejects_wrong_issue_and_forged_histograms() -> None:
    portfolio = compile_six_red_top70_portfolio(
        source_vector=_vector(),
        target_issue="2026002",
    )
    with pytest.raises(EqualCostPortfolioViolation) as error:
        EqualCostPortfolioSettlement.evaluate(
            portfolio=portfolio,
            actual_issue="2026003",
            actual_red_numbers=(1, 2, 3, 4, 5, 6),
        )
    assert error.value.code == "equal_cost_settlement_issue_mismatch"

    valid = EqualCostPortfolioSettlement.evaluate(
        portfolio=portfolio,
        actual_issue="2026002",
        actual_red_numbers=(1, 2, 3, 4, 5, 6),
    )
    forged = list(valid.slot_hit_histogram)
    forged[0] += 1
    with pytest.raises(EqualCostPortfolioViolation) as error:
        replace(valid, slot_hit_histogram=tuple(forged))
    assert error.value.code == "equal_cost_settlement_slot_histogram_mismatch"


def test_portfolio_chronology_and_slot_count_fail_closed() -> None:
    source = _vector(latest_issue="2026002")
    with pytest.raises(EqualCostPortfolioViolation) as error:
        compile_six_red_top70_portfolio(
            source_vector=source,
            target_issue="2026002",
        )
    assert error.value.code == "equal_cost_portfolio_chronology_invalid"

    portfolio = compile_six_red_top70_portfolio(
        source_vector=_vector(),
        target_issue="2026002",
    )
    with pytest.raises(EqualCostPortfolioViolation) as error:
        replace(portfolio, slots=portfolio.slots[:-1])
    assert error.value.code == "equal_cost_portfolio_slot_count_invalid"


def test_parent_score_pool_binding_rejects_mixed_raw_source() -> None:
    original_pool, raw = _raw_score_pool()
    changed_pool, _ = _raw_score_pool(changed=True)
    assert original_pool.candidate_pool.artifact_digest != (
        changed_pool.candidate_pool.artifact_digest
    )

    with pytest.raises(EqualCostPortfolioViolation) as error:
        compile_raw_equal_cost_portfolio(
            score_pool=changed_pool,
            raw_top10=raw,
        )
    assert error.value.code == "equal_cost_portfolio_candidate_pool_mismatch"


def test_parent_score_pool_must_pass_deterministic_replay() -> None:
    score_pool, raw = _raw_score_pool()
    forged = replace(score_pool, target_issue="2026003")

    with pytest.raises(EqualCostPortfolioViolation) as error:
        compile_raw_equal_cost_portfolio(
            score_pool=forged,
            raw_top10=raw,
        )
    assert error.value.code == "equal_cost_portfolio_score_pool_verification_failed"


def test_replay_detects_source_vector_substitution() -> None:
    source = _vector()
    portfolio = compile_six_red_top70_portfolio(
        source_vector=source,
        target_issue="2026002",
    )
    EqualCostPortfolioVerifier().verify_six_red_top70(
        portfolio,
        source_vector=source,
        target_issue="2026002",
    )

    changed_source = _vector(values={0: 1})
    with pytest.raises(EqualCostPortfolioViolation) as error:
        EqualCostPortfolioVerifier().verify_six_red_top70(
            portfolio,
            source_vector=changed_source,
            target_issue="2026002",
        )
    assert error.value.code == "equal_cost_portfolio_replay_mismatch"


def test_outcome_changes_only_settlement_identity() -> None:
    portfolio = compile_six_red_top70_portfolio(
        source_vector=_vector(),
        target_issue="2026002",
    )
    first = EqualCostPortfolioSettlement.evaluate(
        portfolio=portfolio,
        actual_issue="2026002",
        actual_red_numbers=(1, 2, 3, 4, 5, 6),
    )
    second = EqualCostPortfolioSettlement.evaluate(
        portfolio=portfolio,
        actual_issue="2026002",
        actual_red_numbers=(7, 8, 9, 10, 11, 12),
    )

    assert first.portfolio.portfolio_digest == second.portfolio.portfolio_digest
    assert first.settlement_digest != second.settlement_digest
