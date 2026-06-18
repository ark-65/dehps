from __future__ import annotations

import math

from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization.ridge_kdj_advisor import (
    ADVISOR_SOURCE,
    RidgeKdjOffsetAdvice,
    _build_lagged_dataset,
    numpy_ridge_kdj_offset_v0,
    ridge_kdj_advice_to_frequency_ranker_config_candidates,
)


def _row(
    issue: int,
    *,
    weight_name: str = "frequency_weight",
    base_value: float = 0.30,
    close_value: float = 0.30,
    recommended_offset: float = 0.0,
    objective_delta: float = 1.0,
    sample_count: int = 100,
) -> dict:
    return {
        "signal_run_id": "ridge-test",
        "issue": f"{issue:07d}",
        "draw_date": f"2026-01-{(issue % 28) + 1:02d}",
        "weight_name": weight_name,
        "base_value": base_value,
        "close_value": close_value,
        "rsv": 50.0 + recommended_offset * 100,
        "k_value": 51.0 + recommended_offset * 80,
        "d_value": 49.0 - recommended_offset * 50,
        "j_value": 55.0 + recommended_offset * 120,
        "recommended_offset": recommended_offset,
        "objective_delta": objective_delta,
        "sample_count": sample_count,
    }


def _learnable_rows(*, weight_name: str = "frequency_weight", base_value: float = 0.30, count: int = 44) -> list[dict]:
    offsets = [(-0.02, -0.01, 0.0, 0.01, 0.02, 0.03)[index % 6] for index in range(count)]
    rows = [
        _row(
            2026000,
            weight_name=weight_name,
            base_value=base_value,
            close_value=base_value,
            recommended_offset=offsets[0],
        )
    ]
    for index in range(1, count):
        realized = offsets[index - 1] * 2
        rows.append(
            _row(
                2026000 + index,
                weight_name=weight_name,
                base_value=base_value,
                close_value=base_value + realized,
                recommended_offset=offsets[index],
            )
        )
    return rows


def test_lagged_dataset_uses_next_issue_label_without_leakage():
    rows = [
        _row(1, close_value=0.31, recommended_offset=0.99),
        _row(2, close_value=0.35, recommended_offset=-0.99),
        _row(3, close_value=0.28, recommended_offset=0.25, objective_delta=-1.0),
    ]

    dataset = _build_lagged_dataset(rows, weight_name="frequency_weight", step=0.01, bounds=(0.0, 1.25))

    assert dataset is not None
    assert dataset.source_issues == ("0000001", "0000002")
    assert dataset.target_issues == ("0000002", "0000003")
    assert dataset.feature_names[-1] == "base_value"
    assert round(float(dataset.y[0]), 6) == 0.05
    assert round(float(dataset.y[1]), 6) == 0.0
    assert round(float(dataset.sample_weight[1]), 6) == 0.25
    recommended_offset_column = dataset.feature_names.index("recommended_offset_steps")
    assert round(float(dataset.x[0, recommended_offset_column]), 6) == 99.0


def test_numpy_ridge_kdj_offset_v0_is_deterministic_and_advisor_only():
    rows = _learnable_rows(count=48)

    first = numpy_ridge_kdj_offset_v0(rows, step=0.01, ridge_alpha=0.01, min_train_rows=12, min_validation_rows=6)
    second = numpy_ridge_kdj_offset_v0(rows, step=0.01, ridge_alpha=0.01, min_train_rows=12, min_validation_rows=6)

    assert [record.to_dict() for record in first] == [record.to_dict() for record in second]
    assert len(first) == 1
    assert first[0].source == ADVISOR_SOURCE
    assert first[0].validation_metric < first[0].baseline_metric
    assert first[0].train_rows >= 12


def test_numpy_ridge_kdj_offset_v0_bounds_suggested_offsets():
    rows = _learnable_rows(weight_name="sum_tail_weight", base_value=0.28, count=48)

    advice = numpy_ridge_kdj_offset_v0(rows, step=0.01, ridge_alpha=0.01, min_train_rows=12, min_validation_rows=6)

    assert len(advice) == 1
    assert -0.58 <= advice[0].suggested_offset <= 0.02


def test_numpy_ridge_kdj_offset_v0_returns_empty_for_bad_or_unhelpful_data():
    insufficient = _learnable_rows(count=6)
    degenerate = [_row(2026000 + index, close_value=0.30, recommended_offset=0.0) for index in range(30)]
    kdj_perfect = _learnable_rows(count=36)
    for index in range(1, len(kdj_perfect)):
        previous_offset = float(kdj_perfect[index - 1]["recommended_offset"])
        kdj_perfect[index]["close_value"] = float(kdj_perfect[index]["base_value"]) + previous_offset
    with_nan = _learnable_rows(count=36)
    with_nan[5]["j_value"] = math.nan
    unknown_field = _learnable_rows(weight_name="not_a_weight", count=36)

    kwargs = {"step": 0.01, "ridge_alpha": 0.01, "min_train_rows": 12, "min_validation_rows": 6}

    assert numpy_ridge_kdj_offset_v0(insufficient, **kwargs) == ()
    assert numpy_ridge_kdj_offset_v0(degenerate, **kwargs) == ()
    assert numpy_ridge_kdj_offset_v0(kdj_perfect, **kwargs) == ()
    assert numpy_ridge_kdj_offset_v0(with_nan, **kwargs) == ()
    assert numpy_ridge_kdj_offset_v0(unknown_field, **kwargs) == ()


def test_ridge_kdj_advice_to_frequency_ranker_config_candidates_is_bounded_and_limited():
    base = FrequencyRankerConfig(frequency_weight=1.24, sum_tail_weight=0.29)
    advice = [
        RidgeKdjOffsetAdvice(
            weight_name="frequency_weight",
            suggested_offset=0.20,
            confidence=0.70,
            train_rows=30,
            validation_metric=0.01,
            baseline_metric=0.03,
        ),
        {
            "weight_name": "sum_tail_weight",
            "suggested_offset": 0.20,
            "confidence": 0.60,
            "train_rows": 30,
            "validation_metric": 0.01,
            "baseline_metric": 0.03,
            "source": ADVISOR_SOURCE,
        },
        RidgeKdjOffsetAdvice(
            weight_name="omission_weight",
            suggested_offset=-0.03,
            confidence=0.10,
            train_rows=30,
            validation_metric=0.02,
            baseline_metric=0.03,
        ),
    ]

    configs = ridge_kdj_advice_to_frequency_ranker_config_candidates(base, advice, max_configs=2, min_confidence=0.5)

    assert len(configs) == 2
    assert configs[0].frequency_weight == 1.25
    assert configs[1].sum_tail_weight == 0.30
