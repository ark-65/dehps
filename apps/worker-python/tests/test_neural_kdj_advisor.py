from __future__ import annotations

import json

import pytest

from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization.neural_kdj_advisor import (
    ADVISOR_SOURCE,
    NeuralKdjOffsetAdvice,
    config_hash,
    neural_kdj_advice_to_frequency_ranker_config_candidates,
    neural_kdj_config_json_payload,
    numpy_neural_kdj_offset_v0,
)
from dehps.optimization.control_experiments import load_config_json_candidate
from scripts.generate_neural_kdj_advisor_candidate import load_base_config as load_neural_base_config
from scripts.generate_neural_kdj_advisor_candidate import load_signal_rows


def _row(
    issue: int,
    *,
    weight_name: str = "frequency_weight",
    base_value: float = 0.30,
    realized_offset: float = 0.0,
    encoded_next_offset: float = 0.0,
    recommended_offset: float = 0.0,
    objective_delta: float = 1.0,
    sample_count: int = 100,
) -> dict:
    return {
        "signal_run_id": "neural-kdj-test",
        "issue": f"{issue:07d}",
        "draw_date": f"2026-01-{(issue % 28) + 1:02d}",
        "weight_name": weight_name,
        "base_value": base_value,
        "close_value": base_value + realized_offset,
        "rsv": 50.0 + encoded_next_offset * 900,
        "k_value": 51.0 + encoded_next_offset * 700,
        "d_value": 49.0 - encoded_next_offset * 300,
        "j_value": 55.0 + encoded_next_offset * 1000,
        "recommended_offset": recommended_offset,
        "objective_delta": objective_delta,
        "sample_count": sample_count,
    }


def _learnable_rows(
    *,
    weight_name: str = "frequency_weight",
    base_value: float = 0.30,
    count: int = 64,
) -> list[dict]:
    pattern = (-0.02, -0.01, 0.01, 0.03, 0.02, -0.03, 0.0, 0.02)
    rows = []
    for index in range(count):
        realized_offset = pattern[(index - 1) % len(pattern)] if index else 0.0
        encoded_next_offset = pattern[index % len(pattern)]
        rows.append(
            _row(
                2026000 + index,
                weight_name=weight_name,
                base_value=base_value,
                realized_offset=realized_offset,
                encoded_next_offset=encoded_next_offset,
            )
        )
    return rows


def test_numpy_neural_kdj_offset_v0_is_deterministic_and_advisor_only():
    rows = _learnable_rows()

    kwargs = {
        "step": 0.01,
        "seed": 5,
        "hidden_units": 6,
        "epochs": 500,
        "min_train_rows": 20,
        "min_validation_rows": 8,
    }
    first = numpy_neural_kdj_offset_v0(rows, **kwargs)
    second = numpy_neural_kdj_offset_v0(rows, **kwargs)

    assert [record.to_dict() for record in first] == [record.to_dict() for record in second]
    assert len(first) == 1
    assert first[0].source == ADVISOR_SOURCE
    assert first[0].advisory_only is True
    assert first[0].validation_metric < first[0].baseline_metric
    assert "weight::frequency_weight" in first[0].feature_names


def test_numpy_neural_kdj_offset_v0_returns_empty_for_insufficient_degenerate_or_baseline_like_data():
    insufficient = _learnable_rows(count=8)
    degenerate = [_row(2026000 + index, encoded_next_offset=0.01, realized_offset=0.0) for index in range(36)]
    future_like_kdj_perfect = _learnable_rows(count=48)
    for index in range(len(future_like_kdj_perfect) - 1):
        next_offset = float(future_like_kdj_perfect[index + 1]["close_value"]) - float(
            future_like_kdj_perfect[index + 1]["base_value"]
        )
        future_like_kdj_perfect[index]["recommended_offset"] = next_offset
    with_unknown_weight = _learnable_rows(weight_name="not_a_weight", count=48)

    kwargs = {"step": 0.01, "seed": 7, "hidden_units": 5, "epochs": 300, "min_train_rows": 12, "min_validation_rows": 6}

    assert numpy_neural_kdj_offset_v0(insufficient, **kwargs) == ()
    assert numpy_neural_kdj_offset_v0(degenerate, **kwargs) == ()
    assert numpy_neural_kdj_offset_v0(future_like_kdj_perfect, **kwargs) == ()
    assert numpy_neural_kdj_offset_v0(with_unknown_weight, **kwargs) == ()


def test_neural_kdj_candidates_are_bounded_and_metadata_hashes_are_unique():
    base = FrequencyRankerConfig(frequency_weight=1.24, sum_tail_weight=0.29)
    advice = [
        NeuralKdjOffsetAdvice(
            weight_name="frequency_weight",
            suggested_offset=0.20,
            confidence=0.70,
            train_rows=30,
            validation_rows=10,
            validation_metric=0.01,
            baseline_metric=0.03,
            feature_names=("rsv", "weight::frequency_weight"),
        ),
        NeuralKdjOffsetAdvice(
            weight_name="sum_tail_weight",
            suggested_offset=0.20,
            confidence=0.60,
            train_rows=30,
            validation_rows=10,
            validation_metric=0.02,
            baseline_metric=0.04,
            feature_names=("j", "weight::sum_tail_weight"),
        ),
    ]

    configs = neural_kdj_advice_to_frequency_ranker_config_candidates(base, advice, max_configs=4)
    payload = neural_kdj_config_json_payload(
        base_config=base,
        advice=advice,
        configs=configs,
        seed=11,
        hidden_units=4,
        epochs=20,
    )

    assert configs[0].frequency_weight == 1.25
    assert configs[1].sum_tail_weight == 0.30
    hashes = [item["config_hash"] for item in payload["candidate_configs"]]
    assert hashes == [config_hash(config) for config in configs]
    assert len(hashes) == len(set(hashes))
    assert payload["metadata"]["advisory_only"] is True
    assert payload["candidate_configs"][0]["metadata"]["selected_fields"] == ["frequency_weight"]


def test_neural_kdj_payload_is_loadable_by_control_experiment_config_json_path(tmp_path):
    base = FrequencyRankerConfig()
    advice = numpy_neural_kdj_offset_v0(
        _learnable_rows(),
        step=0.01,
        seed=5,
        hidden_units=6,
        epochs=500,
        min_train_rows=20,
        min_validation_rows=8,
    )
    configs = neural_kdj_advice_to_frequency_ranker_config_candidates(base, advice, max_configs=1)
    payload = neural_kdj_config_json_payload(
        base_config=base,
        advice=advice,
        configs=configs,
        seed=5,
        hidden_units=6,
        epochs=500,
        signal_run_id="neural-kdj-test",
        train_window=900,
        top_n=10000,
    )
    path = tmp_path / "neural-kdj-candidate.json"
    path.write_text(json.dumps(payload))

    candidate = load_config_json_candidate(path)

    assert candidate.label == "candidate_neural_kdj_advisor_v0"
    assert candidate.source == "config-json"
    assert candidate.config == configs[0]
    assert payload["metadata"]["advisor_source"] == ADVISOR_SOURCE
    assert payload["metadata"]["advisory_only"] is True


def test_neural_base_config_rejects_nonfinite_values(tmp_path):
    path = tmp_path / "base-config.json"
    path.write_text('{"config": {"sum_tail_weight": "-Infinity"}}')

    with pytest.raises(ValueError, match="--base-config-json field sum_tail_weight must be a finite number"):
        load_neural_base_config(path)


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"limit": 0, "train_window": None, "top_n": None}, "limit must be at least 1"),
        ({"limit": 1, "train_window": 0, "top_n": None}, "train_window must be at least 1"),
        ({"limit": 1, "train_window": None, "top_n": 0}, "top_n must be at least 1"),
    ],
)
def test_neural_signal_loader_rejects_nonpositive_query_bounds(kwargs, match):
    with pytest.raises(ValueError, match=match):
        load_signal_rows(signal_run_id="neural-kdj-test", **kwargs)
