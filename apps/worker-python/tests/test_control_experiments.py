from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization.control_experiments import (
    CONTROL_LABELS,
    GUARDRAIL_LANGUAGE,
    LoadedCandidate,
    fixed_control_labels,
    load_config_json_candidate,
    parse_random_seeds,
    promotion_gate,
    random_same_budget_summary,
    run_control_experiments,
    write_control_experiment_artifacts,
)


TOY_UNIVERSE = [
    (1, 7, 12, 18, 23, 29),
    (2, 8, 13, 19, 24, 30),
    (3, 9, 14, 20, 25, 31),
    (4, 10, 15, 21, 26, 32),
    (5, 11, 16, 22, 27, 33),
    (6, 12, 17, 23, 28, 32),
]


def toy_history():
    start = date(2026, 1, 1)
    return [
        (f"00{index + 1}", start + timedelta(days=index * 2), numbers)
        for index, numbers in enumerate(TOY_UNIVERSE[:5])
    ]


def test_control_list_and_protocol_equality_use_same_snapshot():
    payload = run_control_experiments(
        history=toy_history(),
        universe=TOY_UNIVERSE,
        candidate=LoadedCandidate(
            label="candidate_config_json",
            source="config-json",
            config=FrequencyRankerConfig(frequency_weight=0.45),
        ),
        base_config=FrequencyRankerConfig(),
        train_mode="expanding",
        train_window=2,
        eval_window=2,
        top_n=3,
        random_seeds=(3, 5),
        workers=1,
    )

    assert fixed_control_labels() == CONTROL_LABELS
    assert [item["label"] for item in payload["controls"]] + [payload["random_baseline"]["label"]] == list(CONTROL_LABELS)
    assert payload["protocol"]["protocol_equality"] == {
        "same_universe": True,
        "same_target_issues": True,
        "same_top_n": True,
        "same_train_eval_protocol": True,
    }
    assert len({tuple(item["protocol_key"].items()) for item in payload["controls"]}) == 1


def test_random_same_budget_has_deterministic_math_and_monte_carlo():
    first = random_same_budget_summary(evaluated_draws=5, universe_size=10, top_n=3, random_seeds=(7, 11))
    second = random_same_budget_summary(evaluated_draws=5, universe_size=10, top_n=3, random_seeds=(7, 11))

    assert first == second
    assert first["analytical"]["top_n"]["expected_hits"] == 1.5
    assert first["analytical"]["top_10000"]["expected_hits"] == 1.5
    assert [item["seed"] for item in first["monte_carlo"]] == [7, 11]


def test_promotion_gate_requires_control_win_and_tail_risk_not_worse():
    candidate = {"label": "candidate", "reward": {"objectiveScore": 3.0, "tailRiskPenalty": 0.4}}
    controls = [
        {"label": "current_best_frozen_baseline", "reward": {"objectiveScore": 2.0, "tailRiskPenalty": 0.4}},
        {"label": "structural_baseline", "reward": {"objectiveScore": 1.0, "tailRiskPenalty": 0.2}},
    ]

    assert promotion_gate(candidate_summary=candidate, control_summaries=controls)["passed"] is True

    stronger_control = [*controls, {"label": "frequency_baseline", "reward": {"objectiveScore": 3.1, "tailRiskPenalty": 0.1}}]
    assert promotion_gate(candidate_summary=candidate, control_summaries=stronger_control)["passed"] is False

    risky_candidate = {"label": "candidate", "reward": {"objectiveScore": 4.0, "tailRiskPenalty": 0.5}}
    assert promotion_gate(candidate_summary=risky_candidate, control_summaries=controls)["passed"] is False


def test_report_renderer_writes_artifacts_and_guardrail_language(tmp_path):
    payload = run_control_experiments(
        history=toy_history(),
        universe=TOY_UNIVERSE,
        candidate=LoadedCandidate(
            label="candidate_config_json",
            source="config-json",
            config=FrequencyRankerConfig(frequency_weight=0.45),
        ),
        base_config=FrequencyRankerConfig(),
        train_mode="rolling",
        train_window=2,
        eval_window=2,
        top_n=3,
        random_seeds=(13,),
        workers=1,
    )

    json_path, md_path = write_control_experiment_artifacts(payload, tmp_path)

    assert json_path.exists()
    assert md_path.exists()
    assert "not a prediction claim" in md_path.read_text()
    assert GUARDRAIL_LANGUAGE in md_path.read_text()
    assert json.loads(json_path.read_text())["frozen_verdict"]["passed"] in (True, False)


def test_config_json_candidate_path_loads_normalized_config(tmp_path):
    config_path = tmp_path / "candidate.json"
    config_path.write_text(
        json.dumps(
            {
                "label": "from_file",
                "config": {
                    "structural_weight": 0.35,
                    "frequency_weight": 0.44,
                    "omission_weight": 0.21,
                },
            }
        )
    )

    candidate = load_config_json_candidate(config_path)

    assert candidate.label == "from_file"
    assert candidate.source == "config-json"
    assert candidate.config == FrequencyRankerConfig(
        structural_weight=0.35,
        frequency_weight=0.44,
        omission_weight=0.21,
    )
    assert parse_random_seeds("1, 2,3") == (1, 2, 3)


def test_config_json_candidate_rejects_nonfinite_config_values(tmp_path):
    config_path = tmp_path / "candidate.json"
    config_path.write_text('{"config": {"frequency_weight": "NaN"}}')

    with pytest.raises(ValueError, match="config-json field frequency_weight must be a finite number"):
        load_config_json_candidate(config_path)
