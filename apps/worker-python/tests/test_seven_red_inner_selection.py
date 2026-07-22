from __future__ import annotations

import inspect

import numpy as np
import pytest

from dehps.contracts import canonical_digest
from dehps.seven_red import (
    SEVEN_RED_INNER_SELECTION_METRIC,
    SEVEN_RED_INNER_SELECTION_TIE_BREAK,
    SIX_RED_UNIVERSE,
    DiversifiedSevenRedTop10Snapshot,
    EqualCostPortfolioSettlement,
    RawSevenRedTop10Snapshot,
    SevenRedDiversificationWeights,
    SevenRedDiversityAuditSnapshot,
    SevenRedInnerSelectionProtocol,
    SevenRedInnerSelectionSnapshot,
    SevenRedInnerSelectionVerifier,
    SevenRedInnerSelectionViolation,
    SevenRedParameterGrid,
    SevenRedParameterIssueEvaluation,
    SevenRedScorePoolConfig,
    SevenRedStrategyKind,
    SevenRedStrategyParameter,
    SixRedCombination,
    SixRedFullScoreVector,
    compile_diversified_equal_cost_portfolio,
    compile_raw_equal_cost_portfolio,
    compile_seven_red_score_pool,
)
from dehps.seven_red.inner_selection import (
    SEVEN_RED_INNER_SELECTION_GOLDEN_SUITE,
    SEVEN_RED_INNER_SELECTION_NORMATIVE_DEFINITION,
)


_DIGEST = "a" * 64
_OTHER_DIGEST = "b" * 64
_COMMIT = "c" * 40


def _parameter_grid() -> SevenRedParameterGrid:
    parameters = (
        SevenRedStrategyParameter(
            SevenRedStrategyKind.RAW,
            SevenRedScorePoolConfig(seed_top_n=1, pool_top_n=10),
            None,
        ),
        SevenRedStrategyParameter(
            SevenRedStrategyKind.RAW,
            SevenRedScorePoolConfig(seed_top_n=2, pool_top_n=20),
            None,
        ),
        SevenRedStrategyParameter(
            SevenRedStrategyKind.DIVERSIFIED,
            SevenRedScorePoolConfig(seed_top_n=10, pool_top_n=100),
            SevenRedDiversificationWeights(1, 1, 1, 1),
        ),
        SevenRedStrategyParameter(
            SevenRedStrategyKind.DIVERSIFIED,
            SevenRedScorePoolConfig(seed_top_n=20, pool_top_n=200),
            SevenRedDiversificationWeights(2, 1, 1, 1),
        ),
    )
    return SevenRedParameterGrid.build(reversed(parameters))


def _protocol(window_size: int = 20) -> SevenRedInnerSelectionProtocol:
    return SevenRedInnerSelectionProtocol(
        inner_window_size=window_size,
        metric_contract=SEVEN_RED_INNER_SELECTION_METRIC,
        tie_break_contract=SEVEN_RED_INNER_SELECTION_TIE_BREAK,
    )


def _issues(window_size: int = 20) -> tuple[str, ...]:
    return tuple(f"2026{index:03d}" for index in range(1, window_size + 1))


def _evaluation(
    parameter: SevenRedStrategyParameter,
    issue: str,
    histogram: tuple[int, ...] = (70, 0, 0, 0, 0, 0, 0),
) -> SevenRedParameterIssueEvaluation:
    def digest(label: str) -> str:
        return canonical_digest(
            {
                "label": label,
                "parameter": parameter.parameter_digest,
                "issue": issue,
            },
            domain="dehps.test.seven-red-inner-selection.v1",
        )

    return SevenRedParameterIssueEvaluation(
        parameter=parameter,
        target_issue=issue,
        source_history_latest_issue=f"{int(issue) - 1:07d}",
        score_pool_snapshot_digest=digest("score-pool"),
        source_candidate_pool_digest=digest("candidate-pool"),
        source_strategy_artifact_digest=digest("strategy"),
        portfolio_digest=digest("portfolio"),
        settlement_digest=digest("settlement"),
        unique_ticket_hit_histogram=histogram,
    )


def _matrix(
    grid: SevenRedParameterGrid,
    issues: tuple[str, ...],
) -> tuple[SevenRedParameterIssueEvaluation, ...]:
    return tuple(
        _evaluation(parameter, issue)
        for parameter in grid.parameters
        for issue in issues
    )


def _vector(values: dict[int, int] | None = None) -> SixRedFullScoreVector:
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
        source_history_latest_issue="2026000",
        source_window_artifact_digest=_DIGEST,
        source_window_spec_digest=_OTHER_DIGEST,
        source_weights_digest=_DIGEST,
        source_config_index=0,
        source_config_count=1,
        source_code_commit=_COMMIT,
    )


def test_contract_freezes_complete_unique_ticket_inner_selection_boundary() -> None:
    definition = SEVEN_RED_INNER_SELECTION_NORMATIVE_DEFINITION

    assert definition["research_only"] is True
    assert definition["issue_evaluation"]["metric_source"] == (
        "unique_ticket_hit_histogram_only"
    )
    assert definition["inner_window"]["minimum_issues"] == 20
    assert definition["selection"]["families_selected_independently"] is True
    assert definition["selection"]["outer_outcome_input"] is None
    assert SEVEN_RED_INNER_SELECTION_GOLDEN_SUITE["stochastic"] is False


def test_parameter_and_protocol_identity_fields_have_no_defaults() -> None:
    parameter_signature = inspect.signature(SevenRedStrategyParameter)
    protocol_signature = inspect.signature(SevenRedInnerSelectionProtocol)

    assert all(
        parameter.default is inspect.Parameter.empty
        for parameter in parameter_signature.parameters.values()
    )
    assert all(
        parameter.default is inspect.Parameter.empty
        for parameter in protocol_signature.parameters.values()
    )
    assert "actual" not in inspect.signature(SevenRedInnerSelectionSnapshot.build).parameters
    assert "random" not in inspect.signature(SevenRedInnerSelectionSnapshot.build).parameters


def test_parameter_families_enforce_weight_boundary_and_grid_representation() -> None:
    config = SevenRedScorePoolConfig(seed_top_n=1, pool_top_n=10)
    weights = SevenRedDiversificationWeights(1, 1, 1, 1)

    with pytest.raises(SevenRedInnerSelectionViolation) as raw_error:
        SevenRedStrategyParameter(SevenRedStrategyKind.RAW, config, weights)
    assert raw_error.value.code == "seven_red_parameter_raw_weights_forbidden"

    with pytest.raises(SevenRedInnerSelectionViolation) as diversified_error:
        SevenRedStrategyParameter(SevenRedStrategyKind.DIVERSIFIED, config, None)
    assert diversified_error.value.code == (
        "seven_red_parameter_diversified_weights_required"
    )

    raw = SevenRedStrategyParameter(SevenRedStrategyKind.RAW, config, None)
    with pytest.raises(SevenRedInnerSelectionViolation) as grid_error:
        SevenRedParameterGrid.build((raw, raw))
    assert grid_error.value.code == "seven_red_parameter_grid_duplicate"


def test_issue_metrics_are_derived_only_from_unique_ticket_histogram() -> None:
    parameter = next(
        row
        for row in _parameter_grid().parameters
        if row.strategy_kind is SevenRedStrategyKind.RAW
    )
    row = _evaluation(parameter, "2026001", (1, 2, 3, 4, 5, 6, 7))

    assert row.unique_ticket_count == 28
    assert row.exact_red6_covered is True
    assert row.red5_or_better_covered is True
    assert row.best_unique_matched_red_count == 6
    assert row.unique_red5_ticket_count == 6
    assert "slot_hit_histogram" not in row.as_dict()


def test_raw_adapter_replays_score_pool_portfolio_and_settlement() -> None:
    config = SevenRedScorePoolConfig(seed_top_n=1, pool_top_n=10)
    parameter = SevenRedStrategyParameter(SevenRedStrategyKind.RAW, config, None)
    score_pool = compile_seven_red_score_pool(
        source_vector=_vector(), configuration=config, target_issue="2026001"
    )
    raw = RawSevenRedTop10Snapshot.build(score_pool.candidate_pool)
    portfolio = compile_raw_equal_cost_portfolio(score_pool=score_pool, raw_top10=raw)
    settlement = EqualCostPortfolioSettlement.evaluate(
        portfolio=portfolio,
        actual_issue="2026001",
        actual_red_numbers=(1, 2, 3, 4, 5, 6),
    )

    row = SevenRedParameterIssueEvaluation.compile_raw(
        parameter=parameter,
        score_pool=score_pool,
        portfolio=portfolio,
        settlement=settlement,
    )

    assert row.score_pool_snapshot_digest == score_pool.snapshot_digest
    assert row.portfolio_digest == portfolio.portfolio_digest
    assert row.settlement_digest == settlement.settlement_digest
    assert row.unique_ticket_hit_histogram == settlement.unique_ticket_hit_histogram

    wrong_parameter = SevenRedStrategyParameter(
        SevenRedStrategyKind.RAW,
        SevenRedScorePoolConfig(seed_top_n=2, pool_top_n=10),
        None,
    )
    with pytest.raises(SevenRedInnerSelectionViolation) as error:
        SevenRedParameterIssueEvaluation.compile_raw(
            parameter=wrong_parameter,
            score_pool=score_pool,
            portfolio=portfolio,
            settlement=settlement,
        )
    assert error.value.code == "seven_red_issue_evaluation_config_mismatch"


def test_diversified_adapter_binds_exact_weight_vector_and_source() -> None:
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
    score_pool = compile_seven_red_score_pool(
        source_vector=_vector(values), configuration=config, target_issue="2026001"
    )
    raw = RawSevenRedTop10Snapshot.build(score_pool.candidate_pool)
    audit = SevenRedDiversityAuditSnapshot.build(score_pool.candidate_pool, raw)
    weights = SevenRedDiversificationWeights(1, 1, 1, 1)
    diversified = DiversifiedSevenRedTop10Snapshot.build(audit, weights)
    portfolio = compile_diversified_equal_cost_portfolio(
        score_pool=score_pool, diversified_top10=diversified
    )
    settlement = EqualCostPortfolioSettlement.evaluate(
        portfolio=portfolio,
        actual_issue="2026001",
        actual_red_numbers=(1, 2, 3, 4, 5, 6),
    )
    parameter = SevenRedStrategyParameter(
        SevenRedStrategyKind.DIVERSIFIED, config, weights
    )

    row = SevenRedParameterIssueEvaluation.compile_diversified(
        parameter=parameter,
        score_pool=score_pool,
        diversified_top10=diversified,
        portfolio=portfolio,
        settlement=settlement,
    )
    assert row.source_strategy_artifact_digest == diversified.snapshot_digest

    wrong_weights = SevenRedStrategyParameter(
        SevenRedStrategyKind.DIVERSIFIED,
        config,
        SevenRedDiversificationWeights(2, 1, 1, 1),
    )
    with pytest.raises(SevenRedInnerSelectionViolation) as error:
        SevenRedParameterIssueEvaluation.compile_diversified(
            parameter=wrong_weights,
            score_pool=score_pool,
            diversified_top10=diversified,
            portfolio=portfolio,
            settlement=settlement,
        )
    assert error.value.code == "seven_red_issue_evaluation_weight_mismatch"


def test_complete_matrix_and_strict_outer_chronology_fail_closed() -> None:
    grid = _parameter_grid()
    issues = _issues()
    rows = _matrix(grid, issues)

    with pytest.raises(SevenRedInnerSelectionViolation) as missing_error:
        SevenRedInnerSelectionSnapshot.build(
            outer_target_issue="2026021",
            parameter_grid=grid,
            protocol=_protocol(),
            inner_issues=issues,
            evaluations=rows[:-1],
        )
    assert missing_error.value.code == "seven_red_inner_snapshot_incomplete_matrix"

    with pytest.raises(SevenRedInnerSelectionViolation) as duplicate_error:
        SevenRedInnerSelectionSnapshot.build(
            outer_target_issue="2026021",
            parameter_grid=grid,
            protocol=_protocol(),
            inner_issues=issues,
            evaluations=rows + (rows[0],),
        )
    assert duplicate_error.value.code == "seven_red_inner_snapshot_duplicate_cell"

    with pytest.raises(SevenRedInnerSelectionViolation) as chronology_error:
        SevenRedInnerSelectionSnapshot.build(
            outer_target_issue="2026020",
            parameter_grid=grid,
            protocol=_protocol(),
            inner_issues=issues,
            evaluations=rows,
        )
    assert chronology_error.value.code == "seven_red_inner_snapshot_chronology_invalid"


def test_lexicographic_metric_and_family_selection_are_independent() -> None:
    grid = _parameter_grid()
    issues = _issues()
    rows = list(_matrix(grid, issues))
    raw = tuple(
        parameter
        for parameter in grid.parameters
        if parameter.strategy_kind is SevenRedStrategyKind.RAW
    )
    diversified = tuple(
        parameter
        for parameter in grid.parameters
        if parameter.strategy_kind is SevenRedStrategyKind.DIVERSIFIED
    )

    # Raw[0] wins on exact-6 issue coverage despite Raw[1] having more red-5 tickets.
    rows = [
        _evaluation(row.parameter, row.target_issue, (69, 0, 0, 0, 0, 0, 1))
        if row.parameter == raw[0] and row.target_issue == issues[0]
        else _evaluation(row.parameter, row.target_issue, (60, 0, 0, 0, 0, 10, 0))
        if row.parameter == raw[1]
        else row
        for row in rows
    ]
    snapshot = SevenRedInnerSelectionSnapshot.build(
        outer_target_issue="2026021",
        parameter_grid=grid,
        protocol=_protocol(),
        inner_issues=issues,
        evaluations=rows,
    )

    assert snapshot.selected_parameter_digest(SevenRedStrategyKind.RAW) == (
        raw[0].parameter_digest
    )
    # Equal Diversified metrics use the lower digest and retain both tie rows.
    diversified_selection = next(
        row
        for row in snapshot.family_selections
        if row.strategy_kind is SevenRedStrategyKind.DIVERSIFIED
    )
    assert diversified_selection.selected_parameter_digest == min(
        parameter.parameter_digest for parameter in diversified
    )
    assert len(diversified_selection.tied_parameter_digests) == 2
    assert len(snapshot.aggregates) == 4
    assert snapshot.as_dict()["global_winner"] is None


def test_input_order_is_digest_invariant_and_verifier_replays() -> None:
    grid = _parameter_grid()
    issues = _issues()
    rows = _matrix(grid, issues)
    kwargs = {
        "outer_target_issue": "2026021",
        "parameter_grid": grid,
        "protocol": _protocol(),
        "inner_issues": issues,
    }

    first = SevenRedInnerSelectionSnapshot.build(**kwargs, evaluations=rows)
    second = SevenRedInnerSelectionSnapshot.build(
        **kwargs, evaluations=reversed(rows)
    )

    assert first == second
    assert first.snapshot_digest == second.snapshot_digest
    SevenRedInnerSelectionVerifier().verify(first)


def test_metric_priority_reference_covers_all_four_coordinates() -> None:
    parameter = _parameter_grid().parameters[0]
    issues = _issues()
    cases = (
        ((69, 0, 0, 0, 0, 0, 1), (1, 1, 6, 0)),
        ((69, 0, 0, 0, 0, 1, 0), (0, 1, 5, 1)),
        ((69, 0, 0, 0, 1, 0, 0), (0, 0, 4, 0)),
    )

    for histogram, expected in cases:
        row = _evaluation(parameter, issues[0], histogram)
        assert (
            int(row.exact_red6_covered),
            int(row.red5_or_better_covered),
            row.best_unique_matched_red_count,
            row.unique_red5_ticket_count,
        ) == expected


def test_inner_selection_golden_digest() -> None:
    grid = _parameter_grid()
    snapshot = SevenRedInnerSelectionSnapshot.build(
        outer_target_issue="2026021",
        parameter_grid=grid,
        protocol=_protocol(),
        inner_issues=_issues(),
        evaluations=_matrix(grid, _issues()),
    )

    assert snapshot.snapshot_digest == (
        "960991d54d210de1316f8e40796bd7b34a016a514d8b02ab4761e01ed9159e3d"
    )
