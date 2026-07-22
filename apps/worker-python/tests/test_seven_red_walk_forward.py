from __future__ import annotations

from dataclasses import replace
import inspect

import numpy as np
import pytest

from dehps.contracts import canonical_digest
from dehps.seven_red import (
    EQUAL_COST_TICKET_BUDGET,
    MINIMUM_OUTER_TARGET_COUNT,
    SEVEN_RED_COMPLETE_ARM_POLICY,
    SEVEN_RED_INNER_SELECTION_METRIC,
    SEVEN_RED_INNER_SELECTION_TIE_BREAK,
    SEVEN_RED_MATCHED_RANDOM_POLICY,
    SEVEN_RED_OUTER_EVIDENCE_POLICY,
    SIX_RED_UNIVERSE,
    DiversifiedSevenRedTop10Snapshot,
    EqualCostPortfolioSettlement,
    RandomControlCohortSettlement,
    RandomControlKind,
    RandomControlSeedPolicy,
    RawSevenRedTop10Snapshot,
    SevenRedDiversificationWeights,
    SevenRedDiversityAuditSnapshot,
    SevenRedInnerSelectionProtocol,
    SevenRedInnerSelectionSnapshot,
    SevenRedMatchedRandomEvidence,
    SevenRedOuterArmKind,
    SevenRedOuterRandomRowEvidence,
    SevenRedOuterStrategyArmEvidence,
    SevenRedOuterTrial,
    SevenRedParameterGrid,
    SevenRedParameterIssueEvaluation,
    SevenRedScorePoolConfig,
    SevenRedStrategyKind,
    SevenRedStrategyParameter,
    SevenRedWalkForwardProtocol,
    SevenRedWalkForwardSnapshot,
    SevenRedWalkForwardVerifier,
    SevenRedWalkForwardViolation,
    SixRedCombination,
    SixRedFullScoreVector,
    compile_diversified_equal_cost_portfolio,
    compile_random_control_cohort,
    compile_raw_equal_cost_portfolio,
    compile_seven_red_score_pool,
    compile_six_red_top70_portfolio,
)
from dehps.seven_red.walk_forward import (
    SEVEN_RED_WALK_FORWARD_GOLDEN_SUITE,
    SEVEN_RED_WALK_FORWARD_NORMATIVE_DEFINITION,
)


_DIGEST = "a" * 64
_OTHER_DIGEST = "b" * 64
_COMMIT = "c" * 40


def _digest(label: str, identity: str) -> str:
    return canonical_digest(
        {"label": label, "identity": identity},
        domain="dehps.test.seven-red-walk-forward.v1",
    )


def _targets() -> tuple[str, ...]:
    return tuple(f"2026{index:03d}" for index in range(31, 61))


def _seed_policy() -> RandomControlSeedPolicy:
    return RandomControlSeedPolicy(("a" * 64, "b" * 64))


def _protocol() -> SevenRedWalkForwardProtocol:
    return SevenRedWalkForwardProtocol(
        outer_target_issues=_targets(),
        seed_policy=_seed_policy(),
        paid_ticket_budget=EQUAL_COST_TICKET_BUDGET,
        matched_random_policy=SEVEN_RED_MATCHED_RANDOM_POLICY,
        complete_arm_policy=SEVEN_RED_COMPLETE_ARM_POLICY,
        evidence_policy=SEVEN_RED_OUTER_EVIDENCE_POLICY,
    )


def _strategy_arm(
    kind: SevenRedOuterArmKind,
    identity: str,
) -> SevenRedOuterStrategyArmEvidence:
    is_raw = kind is SevenRedOuterArmKind.RAW_TOP10
    unique_count = 61 if is_raw else 70
    score_pool_digest = (
        None
        if kind is SevenRedOuterArmKind.SIX_RED_TOP70
        else _digest("score-pool", f"{kind.value}-{identity}")
    )
    return SevenRedOuterStrategyArmEvidence(
        arm_kind=kind,
        parameter_digest=(
            None
            if kind is SevenRedOuterArmKind.SIX_RED_TOP70
            else _digest("parameter", kind.value)
        ),
        source_vector_digest=_digest("vector", identity),
        source_score_pool_snapshot_digest=score_pool_digest,
        source_strategy_artifact_digest=_digest("strategy", f"{kind.value}-{identity}"),
        portfolio_digest=_digest("portfolio", f"{kind.value}-{identity}"),
        settlement_digest=_digest("settlement", f"{kind.value}-{identity}"),
        paid_ticket_count=70,
        unique_ticket_count=unique_count,
        duplicate_slot_count=70 - unique_count,
        slot_hit_histogram=(70, 0, 0, 0, 0, 0, 0),
        unique_ticket_hit_histogram=(unique_count, 0, 0, 0, 0, 0, 0),
    )


def _random_evidence(
    family: SevenRedStrategyKind,
    identity: str,
    score_pool_digest: str,
) -> SevenRedMatchedRandomEvidence:
    policy = _seed_policy()
    rows = []
    for seed in policy.seed_digests:
        for kind in (RandomControlKind.RANDOM_FROM_POOL, RandomControlKind.UNIFORM_LEGAL):
            unique_count = 61 if kind is RandomControlKind.RANDOM_FROM_POOL else 70
            row_identity = f"{family.value}-{identity}-{seed}-{kind.value}"
            rows.append(
                SevenRedOuterRandomRowEvidence(
                    seed_digest=seed,
                    control_kind=kind,
                    portfolio_digest=_digest("random-portfolio", row_identity),
                    settlement_row_digest=_digest("random-settlement", row_identity),
                    paid_ticket_count=70,
                    unique_ticket_count=unique_count,
                    duplicate_slot_count=70 - unique_count,
                    slot_hit_histogram=(70, 0, 0, 0, 0, 0, 0),
                    unique_ticket_hit_histogram=(
                        unique_count,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                    ),
                )
            )
    return SevenRedMatchedRandomEvidence(
        matched_family=family,
        source_score_pool_snapshot_digest=score_pool_digest,
        seed_policy=policy,
        cohort_digest=_digest("cohort", f"{family.value}-{identity}"),
        settlement_digest=_digest("cohort-settlement", f"{family.value}-{identity}"),
        rows=tuple(rows),
    )


def _trial(target: str, protocol: SevenRedWalkForwardProtocol) -> SevenRedOuterTrial:
    arms = tuple(_strategy_arm(kind, target) for kind in SevenRedOuterArmKind)
    return SevenRedOuterTrial(
        target_issue=target,
        protocol_digest=protocol.protocol_digest,
        inner_selection_snapshot_digest=_digest("inner-selection", target),
        source_history_latest_issue=f"{int(target) - 1:07d}",
        source_vector_digest=arms[0].source_vector_digest,
        actual=SixRedCombination((1, 2, 3, 4, 5, 6)),
        strategy_arms=arms,
        matched_random_evidence=(
            _random_evidence(
                SevenRedStrategyKind.RAW,
                target,
                arms[0].source_score_pool_snapshot_digest,
            ),
            _random_evidence(
                SevenRedStrategyKind.DIVERSIFIED,
                target,
                arms[1].source_score_pool_snapshot_digest,
            ),
        ),
    )


def _vector(values: dict[int, int]) -> SixRedFullScoreVector:
    ticks = np.zeros(SIX_RED_UNIVERSE.cardinality, dtype=np.int64)
    for lex_id, value in values.items():
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
        source_history_latest_issue="2026030",
        source_window_artifact_digest=_DIGEST,
        source_window_spec_digest=_OTHER_DIGEST,
        source_weights_digest=_DIGEST,
        source_config_index=0,
        source_config_count=1,
        source_code_commit=_COMMIT,
    )


def _inner_selection(
    selected_config: SevenRedScorePoolConfig,
    selected_weights: SevenRedDiversificationWeights,
) -> SevenRedInnerSelectionSnapshot:
    selected_raw = SevenRedStrategyParameter(
        SevenRedStrategyKind.RAW, selected_config, None
    )
    other_raw = SevenRedStrategyParameter(
        SevenRedStrategyKind.RAW,
        SevenRedScorePoolConfig(seed_top_n=11, pool_top_n=270),
        None,
    )
    selected_diversified = SevenRedStrategyParameter(
        SevenRedStrategyKind.DIVERSIFIED, selected_config, selected_weights
    )
    other_diversified = SevenRedStrategyParameter(
        SevenRedStrategyKind.DIVERSIFIED,
        selected_config,
        SevenRedDiversificationWeights(2, 1, 1, 1),
    )
    grid = SevenRedParameterGrid.build(
        (selected_raw, other_raw, selected_diversified, other_diversified)
    )
    issues = tuple(f"2026{index:03d}" for index in range(1, 21))
    selected = {selected_raw.parameter_digest, selected_diversified.parameter_digest}
    evaluations = []
    for parameter in grid.parameters:
        for issue in issues:
            identity = f"{parameter.parameter_digest}-{issue}"
            evaluations.append(
                SevenRedParameterIssueEvaluation(
                    parameter=parameter,
                    target_issue=issue,
                    source_history_latest_issue=f"{int(issue) - 1:07d}",
                    score_pool_snapshot_digest=_digest("score-pool", identity),
                    source_candidate_pool_digest=_digest("candidate-pool", identity),
                    source_strategy_artifact_digest=_digest("strategy", identity),
                    portfolio_digest=_digest("portfolio", identity),
                    settlement_digest=_digest("settlement", identity),
                    unique_ticket_hit_histogram=(
                        (69, 0, 0, 0, 0, 0, 1)
                        if parameter.parameter_digest in selected
                        else (70, 0, 0, 0, 0, 0, 0)
                    ),
                )
            )
    return SevenRedInnerSelectionSnapshot.build(
        outer_target_issue="2026031",
        parameter_grid=grid,
        protocol=SevenRedInnerSelectionProtocol(
            inner_window_size=20,
            metric_contract=SEVEN_RED_INNER_SELECTION_METRIC,
            tie_break_contract=SEVEN_RED_INNER_SELECTION_TIE_BREAK,
        ),
        inner_issues=issues,
        evaluations=evaluations,
    )


def _real_trial_inputs():
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
    config = SevenRedScorePoolConfig(seed_top_n=10, pool_top_n=270)
    weights = SevenRedDiversificationWeights(1, 1, 1, 1)
    score_pool = compile_seven_red_score_pool(
        source_vector=_vector(values),
        configuration=config,
        target_issue="2026031",
    )
    raw_top10 = RawSevenRedTop10Snapshot.build(score_pool.candidate_pool)
    audit = SevenRedDiversityAuditSnapshot.build(score_pool.candidate_pool, raw_top10)
    diversified_top10 = DiversifiedSevenRedTop10Snapshot.build(audit, weights)
    raw_portfolio = compile_raw_equal_cost_portfolio(
        score_pool=score_pool, raw_top10=raw_top10
    )
    diversified_portfolio = compile_diversified_equal_cost_portfolio(
        score_pool=score_pool, diversified_top10=diversified_top10
    )
    six_portfolio = compile_six_red_top70_portfolio(
        source_vector=score_pool.source_vector, target_issue="2026031"
    )
    actual = (1, 2, 3, 4, 5, 6)
    raw_settlement = EqualCostPortfolioSettlement.evaluate(
        portfolio=raw_portfolio,
        actual_issue="2026031",
        actual_red_numbers=actual,
    )
    diversified_settlement = EqualCostPortfolioSettlement.evaluate(
        portfolio=diversified_portfolio,
        actual_issue="2026031",
        actual_red_numbers=actual,
    )
    six_settlement = EqualCostPortfolioSettlement.evaluate(
        portfolio=six_portfolio,
        actual_issue="2026031",
        actual_red_numbers=actual,
    )
    cohort = compile_random_control_cohort(
        score_pool=score_pool, seed_policy=_seed_policy()
    )
    random_settlement = RandomControlCohortSettlement.evaluate(
        cohort=cohort,
        actual_issue="2026031",
        actual_red_numbers=actual,
    )
    return {
        "protocol": _protocol(),
        "inner_selection": _inner_selection(config, weights),
        "raw_score_pool": score_pool,
        "diversified_score_pool": score_pool,
        "diversified_top10": diversified_top10,
        "raw_portfolio": raw_portfolio,
        "diversified_portfolio": diversified_portfolio,
        "six_red_top70_portfolio": six_portfolio,
        "raw_settlement": raw_settlement,
        "diversified_settlement": diversified_settlement,
        "six_red_top70_settlement": six_settlement,
        "raw_random_cohort": cohort,
        "diversified_random_cohort": cohort,
        "raw_random_settlement": random_settlement,
        "diversified_random_settlement": random_settlement,
    }


def test_contract_freezes_complete_equal_cost_unaggregated_boundary() -> None:
    definition = SEVEN_RED_WALK_FORWARD_NORMATIVE_DEFINITION

    assert definition["research_only"] is True
    assert definition["protocol"]["minimum_outer_targets"] == MINIMUM_OUTER_TARGET_COUNT
    assert definition["protocol"]["paid_ticket_budget_per_portfolio"] == 70
    assert definition["snapshot"]["cross_target_aggregation"] is None
    assert definition["snapshot"]["winner"] is None
    assert SEVEN_RED_WALK_FORWARD_GOLDEN_SUITE["stochastic"] is False


def test_protocol_has_no_defaults_and_rejects_target_or_policy_drift() -> None:
    signature = inspect.signature(SevenRedWalkForwardProtocol)
    assert all(
        parameter.default is inspect.Parameter.empty
        for parameter in signature.parameters.values()
    )

    with pytest.raises(SevenRedWalkForwardViolation) as count_error:
        replace(_protocol(), outer_target_issues=_targets()[:-1])
    assert count_error.value.code == "seven_red_walk_forward_target_count_invalid"

    with pytest.raises(SevenRedWalkForwardViolation) as policy_error:
        replace(_protocol(), matched_random_policy="different")
    assert policy_error.value.code == "seven_red_walk_forward_random_policy_invalid"


def test_strategy_and_random_evidence_preserve_paid_and_unique_counts() -> None:
    protocol = _protocol()
    trial = _trial(protocol.outer_target_issues[0], protocol)

    raw, diversified, six = trial.strategy_arms
    assert raw.paid_ticket_count == 70
    assert raw.unique_ticket_count == 61
    assert raw.duplicate_slot_count == 9
    assert diversified.unique_ticket_count == six.unique_ticket_count == 70
    assert len(trial.matched_random_evidence) == 2
    assert all(len(row.rows) == 4 for row in trial.matched_random_evidence)
    assert "mean" not in trial.as_dict()


def test_real_outer_trial_replays_all_sources_and_common_outcome() -> None:
    inputs = _real_trial_inputs()

    trial = SevenRedOuterTrial.compile(**inputs)

    assert trial.target_issue == "2026031"
    assert tuple(row.arm_kind for row in trial.strategy_arms) == tuple(
        SevenRedOuterArmKind
    )
    assert all(row.paid_ticket_count == 70 for row in trial.strategy_arms)
    assert trial.strategy_arms[0].duplicate_slot_count > 0
    assert trial.strategy_arms[1].unique_ticket_count == 70
    assert trial.strategy_arms[2].unique_ticket_count == 70
    assert all(len(row.rows) == 4 for row in trial.matched_random_evidence)
    assert trial.as_dict()["winner"] is None


def test_outer_trial_rejects_random_common_outcome_mismatch() -> None:
    inputs = _real_trial_inputs()
    wrong = RandomControlCohortSettlement.evaluate(
        cohort=inputs["raw_random_cohort"],
        actual_issue="2026031",
        actual_red_numbers=(2, 3, 4, 5, 6, 7),
    )
    inputs["raw_random_settlement"] = wrong

    with pytest.raises(SevenRedWalkForwardViolation) as error:
        SevenRedOuterTrial.compile(**inputs)
    assert error.value.code == "seven_red_outer_trial_common_outcome_mismatch"


def test_outer_trial_rejects_selected_parameter_and_shared_vector_drift() -> None:
    inputs = _real_trial_inputs()
    source_vector = inputs["raw_score_pool"].source_vector
    wrong_config_pool = compile_seven_red_score_pool(
        source_vector=source_vector,
        configuration=SevenRedScorePoolConfig(seed_top_n=11, pool_top_n=270),
        target_issue="2026031",
    )
    wrong_config_inputs = {**inputs, "raw_score_pool": wrong_config_pool}

    with pytest.raises(SevenRedWalkForwardViolation) as parameter_error:
        SevenRedOuterTrial.compile(**wrong_config_inputs)
    assert parameter_error.value.code == "seven_red_outer_trial_raw_parameter_mismatch"

    changed_ticks = source_vector.score_ticks.copy()
    changed_ticks[0] += 1
    changed_ticks.setflags(write=False)
    changed_vector = replace(source_vector, score_ticks=changed_ticks)
    changed_pool = compile_seven_red_score_pool(
        source_vector=changed_vector,
        configuration=inputs["diversified_score_pool"].configuration,
        target_issue="2026031",
    )
    changed_inputs = {**inputs, "diversified_score_pool": changed_pool}

    with pytest.raises(SevenRedWalkForwardViolation) as vector_error:
        SevenRedOuterTrial.compile(**changed_inputs)
    assert vector_error.value.code == "seven_red_outer_trial_shared_vector_mismatch"


def test_walk_forward_requires_complete_target_matrix_and_protocol_binding() -> None:
    protocol = _protocol()
    trials = tuple(_trial(target, protocol) for target in protocol.outer_target_issues)

    with pytest.raises(SevenRedWalkForwardViolation) as missing_error:
        SevenRedWalkForwardSnapshot.build(protocol=protocol, trials=trials[:-1])
    assert missing_error.value.code == "seven_red_walk_forward_target_matrix_invalid"

    wrong_protocol_trial = replace(
        trials[0], protocol_digest=_digest("wrong-protocol", "one")
    )
    with pytest.raises(SevenRedWalkForwardViolation) as binding_error:
        SevenRedWalkForwardSnapshot.build(
            protocol=protocol, trials=(wrong_protocol_trial, *trials[1:])
        )
    assert binding_error.value.code == (
        "seven_red_walk_forward_protocol_binding_invalid"
    )


def test_walk_forward_input_order_is_digest_invariant_and_has_no_aggregate() -> None:
    protocol = _protocol()
    trials = tuple(_trial(target, protocol) for target in protocol.outer_target_issues)

    first = SevenRedWalkForwardSnapshot.build(protocol=protocol, trials=trials)
    second = SevenRedWalkForwardSnapshot.build(
        protocol=protocol, trials=reversed(trials)
    )

    assert first == second
    assert first.snapshot_digest == second.snapshot_digest
    assert first.as_dict()["cross_target_aggregate"] is None
    assert first.as_dict()["statistical_result"] is None
    SevenRedWalkForwardVerifier().verify(first)


def test_walk_forward_golden_digest() -> None:
    protocol = _protocol()
    snapshot = SevenRedWalkForwardSnapshot.build(
        protocol=protocol,
        trials=(_trial(target, protocol) for target in protocol.outer_target_issues),
    )

    assert snapshot.snapshot_digest == (
        "35ea8dcd2d7d1f86a76ee33d6b1e0d175a58e5341505590ff1618aea1c542239"
    )
