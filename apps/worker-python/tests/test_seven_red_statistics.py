from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
import inspect

import pytest

from dehps.contracts import canonical_digest
from dehps.seven_red import (
    ALL_SEED_RANDOM_MEAN,
    CIRCULAR_BLOCK_BOOTSTRAP,
    CONFIRMATORY_COMPARISONS,
    EQUAL_COST_TICKET_BUDGET,
    EXACT_SIGN_TEST,
    HOLM_MULTIPLICITY,
    NEAREST_RANK_PERCENTILE,
    SEVEN_RED_COMPLETE_ARM_POLICY,
    SEVEN_RED_MATCHED_RANDOM_POLICY,
    SEVEN_RED_OUTER_EVIDENCE_POLICY,
    RandomControlKind,
    RandomControlSeedPolicy,
    SevenRedComparisonId,
    SevenRedEndpoint,
    SevenRedMatchedRandomEvidence,
    SevenRedOuterArmKind,
    SevenRedOuterRandomRowEvidence,
    SevenRedOuterStrategyArmEvidence,
    SevenRedOuterTrial,
    SevenRedStatisticalProtocol,
    SevenRedStatisticalSnapshot,
    SevenRedStatisticalVerifier,
    SevenRedStatisticalViolation,
    SevenRedStrategyKind,
    SevenRedWalkForwardProtocol,
    SevenRedWalkForwardSnapshot,
    SixRedCombination,
    circular_block_bootstrap_interval,
    exact_greater_sign_test_p,
    holm_adjusted_p_values,
)
from dehps.seven_red.statistics import (
    SEVEN_RED_STATISTICAL_GOLDEN_SUITE,
    SEVEN_RED_STATISTICAL_NORMATIVE_DEFINITION,
)


def _digest(label: str, identity: str) -> str:
    return canonical_digest(
        {"label": label, "identity": identity},
        domain="dehps.test.seven-red-statistics.v1",
    )


def _targets() -> tuple[str, ...]:
    return tuple(f"2026{index:03d}" for index in range(31, 61))


def _seed_policy() -> RandomControlSeedPolicy:
    return RandomControlSeedPolicy(("a" * 64, "b" * 64))


def _walk_protocol() -> SevenRedWalkForwardProtocol:
    return SevenRedWalkForwardProtocol(
        outer_target_issues=_targets(),
        seed_policy=_seed_policy(),
        paid_ticket_budget=EQUAL_COST_TICKET_BUDGET,
        matched_random_policy=SEVEN_RED_MATCHED_RANDOM_POLICY,
        complete_arm_policy=SEVEN_RED_COMPLETE_ARM_POLICY,
        evidence_policy=SEVEN_RED_OUTER_EVIDENCE_POLICY,
    )


def _statistical_protocol(
    walk_protocol: SevenRedWalkForwardProtocol,
    *,
    bootstrap_seed_digest: str = "c" * 64,
) -> SevenRedStatisticalProtocol:
    return SevenRedStatisticalProtocol(
        walk_forward_protocol_digest=walk_protocol.protocol_digest,
        confirmatory_endpoint=SevenRedEndpoint.BEST_UNIQUE_MATCHED_RED,
        confirmatory_comparisons=CONFIRMATORY_COMPARISONS,
        alternative="greater",
        sign_test_contract=EXACT_SIGN_TEST,
        alpha=Fraction(1, 20),
        minimum_effect=Fraction(0),
        multiplicity_contract=HOLM_MULTIPLICITY,
        random_aggregation_contract=ALL_SEED_RANDOM_MEAN,
        confidence_level=Fraction(19, 20),
        bootstrap_block_length=5,
        bootstrap_resample_count=1_000,
        bootstrap_seed_digest=bootstrap_seed_digest,
        bootstrap_contract=CIRCULAR_BLOCK_BOOTSTRAP,
        percentile_contract=NEAREST_RANK_PERCENTILE,
    )


def _histogram(best_match: int, total: int) -> tuple[int, ...]:
    values = [0] * 7
    values[best_match] = total
    return tuple(values)


def _strategy_arm(
    kind: SevenRedOuterArmKind,
    target: str,
    best_match: int,
) -> SevenRedOuterStrategyArmEvidence:
    unique = 61 if kind is SevenRedOuterArmKind.RAW_TOP10 else 70
    return SevenRedOuterStrategyArmEvidence(
        arm_kind=kind,
        parameter_digest=(
            None
            if kind is SevenRedOuterArmKind.SIX_RED_TOP70
            else _digest("parameter", kind.value)
        ),
        source_vector_digest=_digest("vector", target),
        source_score_pool_snapshot_digest=(
            None
            if kind is SevenRedOuterArmKind.SIX_RED_TOP70
            else _digest("score-pool", f"{target}-{kind.value}")
        ),
        source_strategy_artifact_digest=_digest("strategy", f"{target}-{kind.value}"),
        portfolio_digest=_digest("portfolio", f"{target}-{kind.value}"),
        settlement_digest=_digest("settlement", f"{target}-{kind.value}"),
        paid_ticket_count=70,
        unique_ticket_count=unique,
        duplicate_slot_count=70 - unique,
        slot_hit_histogram=_histogram(best_match, 70),
        unique_ticket_hit_histogram=_histogram(best_match, unique),
    )


def _random_evidence(
    family: SevenRedStrategyKind,
    target: str,
    score_pool_digest: str,
    *,
    pool_best: tuple[int, int],
    uniform_best: tuple[int, int],
) -> SevenRedMatchedRandomEvidence:
    policy = _seed_policy()
    rows = []
    for seed_index, seed in enumerate(policy.seed_digests):
        for kind, best_values in (
            (RandomControlKind.RANDOM_FROM_POOL, pool_best),
            (RandomControlKind.UNIFORM_LEGAL, uniform_best),
        ):
            unique = 61 if kind is RandomControlKind.RANDOM_FROM_POOL else 70
            identity = f"{family.value}-{target}-{seed}-{kind.value}"
            rows.append(
                SevenRedOuterRandomRowEvidence(
                    seed_digest=seed,
                    control_kind=kind,
                    portfolio_digest=_digest("random-portfolio", identity),
                    settlement_row_digest=_digest("random-settlement", identity),
                    paid_ticket_count=70,
                    unique_ticket_count=unique,
                    duplicate_slot_count=70 - unique,
                    slot_hit_histogram=_histogram(best_values[seed_index], 70),
                    unique_ticket_hit_histogram=_histogram(
                        best_values[seed_index], unique
                    ),
                )
            )
    return SevenRedMatchedRandomEvidence(
        matched_family=family,
        source_score_pool_snapshot_digest=score_pool_digest,
        seed_policy=policy,
        cohort_digest=_digest("cohort", f"{family.value}-{target}"),
        settlement_digest=_digest("random-settlement", f"{family.value}-{target}"),
        rows=tuple(rows),
    )


def _trial(target: str, protocol: SevenRedWalkForwardProtocol) -> SevenRedOuterTrial:
    raw = _strategy_arm(SevenRedOuterArmKind.RAW_TOP10, target, 5)
    diversified = _strategy_arm(
        SevenRedOuterArmKind.DIVERSIFIED_TOP10, target, 4
    )
    top70 = _strategy_arm(SevenRedOuterArmKind.SIX_RED_TOP70, target, 4)
    return SevenRedOuterTrial(
        target_issue=target,
        protocol_digest=protocol.protocol_digest,
        inner_selection_snapshot_digest=_digest("inner", target),
        source_history_latest_issue=f"{int(target) - 1:07d}",
        source_vector_digest=raw.source_vector_digest,
        actual=SixRedCombination((1, 2, 3, 4, 5, 6)),
        strategy_arms=(raw, diversified, top70),
        matched_random_evidence=(
            _random_evidence(
                SevenRedStrategyKind.RAW,
                target,
                raw.source_score_pool_snapshot_digest,
                pool_best=(4, 6),
                uniform_best=(3, 5),
            ),
            _random_evidence(
                SevenRedStrategyKind.DIVERSIFIED,
                target,
                diversified.source_score_pool_snapshot_digest,
                pool_best=(3, 5),
                uniform_best=(3, 3),
            ),
        ),
    )


def _walk_snapshot() -> SevenRedWalkForwardSnapshot:
    protocol = _walk_protocol()
    return SevenRedWalkForwardSnapshot.build(
        protocol=protocol,
        trials=(_trial(target, protocol) for target in protocol.outer_target_issues),
    )


def test_contract_freezes_target_pairing_seed_aggregation_and_no_decision() -> None:
    definition = SEVEN_RED_STATISTICAL_NORMATIVE_DEFINITION

    assert definition["research_only"] is True
    assert definition["confirmatory"]["sample_unit"] == "outer_target_issue"
    assert definition["random_comparator"]["seed_as_independent_sample"] is False
    assert definition["confirmatory"]["multiplicity"] == HOLM_MULTIPLICITY
    assert definition["output"]["boolean_decision"] is None
    assert SEVEN_RED_STATISTICAL_GOLDEN_SUITE["stochastic"] is False


def test_protocol_has_no_defaults_and_rejects_family_or_fraction_drift() -> None:
    signature = inspect.signature(SevenRedStatisticalProtocol)
    assert all(
        parameter.default is inspect.Parameter.empty
        for parameter in signature.parameters.values()
    )
    protocol = _statistical_protocol(_walk_protocol())

    with pytest.raises(SevenRedStatisticalViolation) as family_error:
        replace(
            protocol,
            confirmatory_comparisons=CONFIRMATORY_COMPARISONS[:-1],
        )
    assert family_error.value.code == "seven_red_statistical_comparison_family_invalid"

    with pytest.raises(SevenRedStatisticalViolation) as fraction_error:
        replace(protocol, alpha=0.05)
    assert fraction_error.value.code == "seven_red_statistical_fraction_invalid"


def test_exact_greater_sign_test_matches_independent_binomial_tail() -> None:
    assert exact_greater_sign_test_p(3, 1) == Fraction(5, 16)
    assert exact_greater_sign_test_p(0, 0) == 1
    assert exact_greater_sign_test_p(0, 4) == 1
    assert exact_greater_sign_test_p(4, 0) == Fraction(1, 16)


def test_holm_adjustment_is_monotone_capped_and_tie_deterministic() -> None:
    raw = {
        comparison: value
        for comparison, value in zip(
            reversed(CONFIRMATORY_COMPARISONS),
            (
                Fraction(1, 2),
                Fraction(1, 5),
                Fraction(1, 10),
                Fraction(1, 25),
                Fraction(1, 50),
                Fraction(1, 100),
            ),
            strict=True,
        )
    }

    adjusted = holm_adjusted_p_values(raw)
    ordered = sorted(raw, key=lambda item: (raw[item], item.value))
    values = [adjusted[item] for item in ordered]

    assert values == sorted(values)
    assert all(raw[item] <= adjusted[item] <= 1 for item in raw)
    assert values[0] == Fraction(3, 50)


def test_circular_block_bootstrap_is_exact_and_deterministic() -> None:
    protocol = _statistical_protocol(_walk_protocol())
    differences = (Fraction(1),) * 30

    first = circular_block_bootstrap_interval(
        differences,
        protocol=protocol,
        comparison=SevenRedComparisonId.RAW_VS_SIX_RED_TOP70,
    )
    second = circular_block_bootstrap_interval(
        differences,
        protocol=protocol,
        comparison=SevenRedComparisonId.RAW_VS_SIX_RED_TOP70,
    )

    assert first == second
    assert first[0] == first[1] == 1


def test_snapshot_aggregates_random_seeds_within_target_without_pseudoreplication() -> None:
    walk = _walk_snapshot()
    snapshot = SevenRedStatisticalSnapshot.compile(
        source_walk_forward=walk,
        protocol=_statistical_protocol(walk.protocol),
    )
    raw_pool = next(
        row
        for row in snapshot.comparisons
        if row.comparison_id
        is SevenRedComparisonId.RAW_VS_MATCHED_RANDOM_POOL
    )

    assert len(raw_pool.target_issues) == 30
    assert len(raw_pool.strategy_values) == 30
    assert len(raw_pool.comparator_values) == 30
    assert set(raw_pool.comparator_values) == {Fraction(5)}
    assert len(raw_pool.random_seed_row_digests) == 60
    assert raw_pool.win_count == raw_pool.loss_count == 0
    assert raw_pool.tie_count == 30
    assert raw_pool.raw_sign_test_p_value == 1


def test_snapshot_computes_six_canonical_results_and_holm_values_only() -> None:
    walk = _walk_snapshot()
    snapshot = SevenRedStatisticalSnapshot.compile(
        source_walk_forward=walk,
        protocol=_statistical_protocol(walk.protocol),
    )

    assert tuple(row.comparison_id for row in snapshot.comparisons) == (
        CONFIRMATORY_COMPARISONS
    )
    assert len(snapshot.descriptive_rows) == 30 * 11
    raw_top70 = snapshot.comparisons[0]
    assert raw_top70.win_count == 30
    assert raw_top70.loss_count == raw_top70.tie_count == 0
    assert raw_top70.mean_difference == 1
    assert raw_top70.bootstrap_interval_lower == 1
    assert raw_top70.bootstrap_interval_upper == 1
    assert raw_top70.holm_adjusted_p_value >= raw_top70.raw_sign_test_p_value
    payload = snapshot.as_dict()
    assert payload["boolean_decision"] is None
    assert payload["winner"] is None
    assert payload["hypothesis_status"] is None


def test_snapshot_replay_and_bootstrap_seed_mutation_change_identity() -> None:
    walk = _walk_snapshot()
    first = SevenRedStatisticalSnapshot.compile(
        source_walk_forward=walk,
        protocol=_statistical_protocol(walk.protocol),
    )
    second = SevenRedStatisticalSnapshot.compile(
        source_walk_forward=walk,
        protocol=_statistical_protocol(
            walk.protocol, bootstrap_seed_digest="d" * 64
        ),
    )

    assert first.snapshot_digest != second.snapshot_digest
    assert (
        first.comparisons[0].bootstrap_distribution_digest
        != second.comparisons[0].bootstrap_distribution_digest
    )
    SevenRedStatisticalVerifier().verify(first)


def test_statistical_snapshot_golden_digest() -> None:
    walk = _walk_snapshot()
    snapshot = SevenRedStatisticalSnapshot.compile(
        source_walk_forward=walk,
        protocol=_statistical_protocol(walk.protocol),
    )

    assert snapshot.snapshot_digest == (
        "88ade3f1c5c37c9751ea83d08547d6409c47c85136952852087f1268cf93f080"
    )
