import json
from copy import deepcopy
from fractions import Fraction
from math import comb
from pathlib import Path

import numpy as np
import pytest
from typer.testing import CliRunner

from dehps import cli
from dehps.research_os.information_theory.synthetic import (
    SyntheticIssue,
    full_combination_probability,
    generate_null_dataset,
    legal_combination_count,
    load_synthetic_run_manifest,
    number_marginal_probability,
    pair_marginal_probability,
    validate_synthetic_run_manifest,
)
from dehps.research_os.information_theory.digest import config_digest


ROOT = Path(__file__).resolve().parents[3]
RUN_PATH = (
    ROOT
    / "configs/research-os/m4-information-theory-p2-synthetic-run-manifest-v1.json"
)


def _load() -> dict:
    return json.loads(RUN_PATH.read_text(encoding="utf-8"))


def _redigest(payload: dict) -> dict:
    payload["artifact_digest"] = config_digest(payload)
    return payload


def test_run_manifest_freezes_p2_1_without_execution() -> None:
    manifest = load_synthetic_run_manifest(RUN_PATH)

    assert manifest.artifact_digest == RUN_PATH.read_text().split('"artifact_digest": "')[1][:64]
    assert len(manifest.scenarios) == 13
    assert [item.scale_id for item in manifest.scales] == [
        "HISTORICAL",
        "FORWARD_61",
        "LONG",
    ]
    assert manifest.payload["planned_workload"]["scenario_replicates"] == 31000
    assert manifest.payload["planned_workload"]["outer_issue_predictions"] == 64656000
    assert manifest.payload["execution"] == {
        "large_replicates_executed": False,
        "metrics_executed": False,
        "real_data_executed": False,
    }


def test_theoretical_truth_uses_exact_combination_formulas() -> None:
    assert legal_combination_count() == comb(33, 6)
    assert number_marginal_probability() == Fraction(6, 33)
    assert pair_marginal_probability() == Fraction(comb(31, 4), comb(33, 6))
    assert full_combination_probability() == Fraction(1, comb(33, 6))


def test_null_draws_preserve_legal_sample_space_targets_and_masks() -> None:
    artifact = generate_null_dataset(
        load_synthetic_run_manifest(RUN_PATH),
        scale_id="FORWARD_61",
        seed=200000,
    )

    assert len(artifact.issues) == 961
    for issue in artifact.issues:
        assert len(issue.sorted_red_numbers) == len(set(issue.sorted_red_numbers)) == 6
        assert issue.sorted_red_numbers == tuple(sorted(issue.sorted_red_numbers))
        assert min(issue.sorted_red_numbers) >= 1
        assert max(issue.sorted_red_numbers) <= 33
        assert len(issue.target_vector) == 33
        assert sum(issue.target_vector) == 6
        decoded = tuple(
            index + 1 for index, value in enumerate(issue.target_vector) if value
        )
        assert decoded == issue.sorted_red_numbers
        assert issue.red_mask == sum(1 << (number - 1) for number in decoded)
        assert issue.red_mask <= np.iinfo(np.uint64).max


def test_same_seed_replays_identically_and_different_seed_changes_draw_digest() -> None:
    manifest = load_synthetic_run_manifest(RUN_PATH)
    first = generate_null_dataset(
        manifest, scale_id="FORWARD_61", seed=200001
    ).to_dict()
    replay = generate_null_dataset(
        manifest, scale_id="FORWARD_61", seed=200001
    ).to_dict()
    different = generate_null_dataset(
        manifest, scale_id="FORWARD_61", seed=200002
    ).to_dict()

    assert first == replay
    assert first["artifact_digest"] == replay["artifact_digest"]
    assert first["draw_digest"] != different["draw_digest"]
    assert first["data_source"] == "synthetic_only"
    assert first["real_dataset_reference"] is None


def test_explicit_numpy_generator_can_be_injected_for_replay() -> None:
    manifest = load_synthetic_run_manifest(RUN_PATH)
    first = generate_null_dataset(
        manifest,
        scale_id="FORWARD_61",
        seed=200003,
        rng=np.random.default_rng(99),
    ).to_dict()
    second = generate_null_dataset(
        manifest,
        scale_id="FORWARD_61",
        seed=200003,
        rng=np.random.default_rng(99),
    ).to_dict()
    assert first == second


def test_seed_outside_policy_is_rejected() -> None:
    with pytest.raises(ValueError, match="outside"):
        generate_null_dataset(
            load_synthetic_run_manifest(RUN_PATH),
            scale_id="FORWARD_61",
            seed=199999,
        )


def test_issue_contract_rejects_mask_target_disagreement() -> None:
    with pytest.raises(ValueError, match="same numbers"):
        SyntheticIssue(
            issue_index=1,
            red_mask=0,
            sorted_red_numbers=(1, 2, 3, 4, 5, 6),
            target_vector=tuple([1] * 6 + [0] * 27),
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.update(data_source="real_history"), "real data"),
        (
            lambda value: value.update(
                preregistration_digest="0" * 64
            ),
            "preregistration digest mismatch",
        ),
        (
            lambda value: value["seed_policy"].update(seed_range=[200000, 200999]),
            "seed range changed",
        ),
        (
            lambda value: value["sequence_scales"][0].update(sequence_length=3480),
            "outer evaluation length",
        ),
    ],
)
def test_manifest_validation_fails_closed(mutation, message: str) -> None:
    payload = deepcopy(_load())
    mutation(payload)
    _redigest(payload)
    with pytest.raises(ValueError, match=message):
        validate_synthetic_run_manifest(payload)


def test_object_order_does_not_change_run_manifest_digest() -> None:
    payload = _load()
    reordered = dict(reversed(list(payload.items())))
    assert config_digest(reordered) == payload["artifact_digest"]


def test_cli_validates_config_and_later_p2_commands_fail_closed() -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli.app,
        [
            "research-os",
            "information-theory",
            "synthetic",
            "validate-config",
            "--input",
            str(RUN_PATH),
        ],
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout)["large_replicates_executed"] is False

    gated = runner.invoke(
        cli.app,
        ["research-os", "information-theory", "synthetic", "run"],
    )
    assert gated.exit_code == 2
    assert "phase_gate_not_satisfied" in gated.stdout + gated.stderr
