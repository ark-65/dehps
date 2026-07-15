from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, timedelta

import pytest

from dehps.models.frequency_ranker import FrequencyRankerConfig
from dehps.optimization.feature_ablation import (
    ABLATION_GUARDRAIL,
    FEATURE_FAMILIES,
    feature_ablation_configs,
    run_feature_ablation,
    render_feature_ablation_report,
    validate_feature_families,
    write_feature_ablation_artifacts,
)
from dehps.optimization.walk_forward import CONFIG_WEIGHT_FIELDS


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


def test_feature_families_are_exhaustive_unique_and_known():
    validation = validate_feature_families()
    flattened = [field for fields in FEATURE_FAMILIES.values() for field in fields]

    assert validation == {"missing": (), "unknown": (), "duplicates": ()}
    assert len(flattened) == len(set(flattened))
    assert set(flattened) == set(CONFIG_WEIGHT_FIELDS)


def test_feature_family_validation_rejects_missing_and_duplicate_fields():
    with pytest.raises(ValueError, match="missing=.*frequency_weight.*duplicates=.*structural_weight"):
        validate_feature_families(
            {
                "one": ("structural_weight",),
                "two": ("structural_weight",),
            }
        )


def test_each_ablation_only_zeroes_its_declared_family():
    base = FrequencyRankerConfig(**{field: 0.37 for field in CONFIG_WEIGHT_FIELDS})
    configs = dict(feature_ablation_configs(base))

    assert configs["full_model"] == base
    for family, fields in FEATURE_FAMILIES.items():
        candidate = asdict(configs[f"without_{family}"])
        for field in CONFIG_WEIGHT_FIELDS:
            assert candidate[field] == (0.0 if field in fields else 0.37)


def test_ablation_uses_identical_targets_and_is_never_promotion_authority(tmp_path):
    from dehps.optimization.walk_forward import build_ranked_universe

    payload = run_feature_ablation(
        history=toy_history(),
        base_config=FrequencyRankerConfig(),
        train_mode="expanding",
        train_window=2,
        eval_window=2,
        top_n=3,
        workers=1,
        ranked_universe=build_ranked_universe(TOY_UNIVERSE, use_cache=False),
    )

    assert payload["status"] == "diagnostic_only"
    assert payload["promotion_allowed"] is False
    assert payload["protocol"]["same_target_issues"] is True
    assert all(item["target_issues_equal"] for item in payload["ablations"])
    assert len(payload["ablations"]) == len(FEATURE_FAMILIES)
    assert ABLATION_GUARDRAIL in payload["guardrail"]

    json_path, report_path = write_feature_ablation_artifacts(payload, tmp_path)
    assert json.loads(json_path.read_text())["promotion_allowed"] is False
    report = report_path.read_text()
    assert "Promotion allowed: `false`" in report
    assert "Forward unseen evidence remains required" in report


def test_report_handles_missing_rank_delta():
    payload = {
        "generated_at": "2026-07-15T00:00:00",
        "status": "diagnostic_only",
        "promotion_allowed": False,
        "guardrail": ABLATION_GUARDRAIL,
        "protocol": {
            "as_of_issue": "1",
            "train_mode": "expanding",
            "train_window": 1,
            "eval_window": 1,
            "frozen_window": 0,
            "top_n": 1,
            "universe_size": 1,
            "same_target_issues": True,
        },
        "feature_families": {},
        "ablations": [
            {
                "family": "empty",
                "metrics": {
                    "top_10000_hits": 0,
                    "median_rank": None,
                    "objective_score": 0.0,
                    "red5": {"top_10000_hits": 0},
                },
                "delta_vs_full_model": {
                    "top_10000_hits": 0.0,
                    "median_rank": None,
                    "objective_score": 0.0,
                    "red5": {"top_10000_hits": 0.0},
                },
                "frozen_metrics": {"objective_score": 0.0},
                "frozen_delta_vs_full_model": {"objective_score": 0.0},
            }
        ],
    }

    assert "None (n/a)" in render_feature_ablation_report(payload)
