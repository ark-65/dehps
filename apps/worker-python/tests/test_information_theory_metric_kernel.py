import json
import math
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from dehps import cli
from dehps.research_os.control_plane import ResearchOSControlPlane
from dehps.research_os.information_theory import build_m4_status, load_m4_manifest
from dehps.research_os.information_theory.digest import config_digest
from dehps.research_os.information_theory.metrics import (
    MetricKernelError,
    UnitContract,
    adapt_number_event_rows,
    aggregate_issue_metrics,
    bernoulli_log_loss_nats,
    bits_to_nats,
    build_metric_artifact,
    clip_probabilities,
    evaluate_issue,
    joint_uniform_code_length,
    load_metric_kernel_manifest,
    nats_to_bits,
    reject_marginal_product_as_joint,
    theoretical_baseline_loss,
    theoretical_number_probability,
    validate_metric_artifact,
    validate_metric_input,
    validate_probability_vector,
    validate_target_vector,
)
from dehps.research_os.information_theory.synthetic import (
    SyntheticIssue,
    legal_combination_count,
)
from dehps.research_os.models import TaskStatus


ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = (
    ROOT / "configs/research-os/m4-information-theory-metric-kernel-v1.json"
)
CONTROL_PATH = ROOT / "apps/worker-python/tests/fixtures/research_os/m4-information-theory-evidence-head-b6c03ba.json"
EPSILON = 1e-6
BASELINE_P = 6 / 33
TARGET = tuple([1] * 6 + [0] * 27)
BASELINE = tuple([BASELINE_P] * 33)
PERFECT = tuple(
    1 - EPSILON if target else EPSILON for target in TARGET
)
REVERSED = tuple(
    EPSILON if target else 1 - EPSILON for target in TARGET
)


def _issue(
    issue_id: str = "fixture-1",
    probe=BASELINE,
    target=TARGET,
):
    return evaluate_issue(
        issue_id=issue_id,
        cluster_id=issue_id,
        target_vector=target,
        baseline_probability_vector=BASELINE,
        probe_probability_vector=probe,
        baseline_identity="NUMBER_EVENT_COMPOSITE_BASELINE",
    )


def _input(*, probes=(BASELINE,), issue_ids=None):
    ids = issue_ids or tuple(f"fixture-{index + 1}" for index in range(len(probes)))
    return {
        "schema_version": "dehps-m4-information-theory-metric-input.v1",
        "created_at": "2026-07-25T10:00:00+08:00",
        "source_dataset_digest": "a" * 64,
        "parent_digests": ["b" * 64],
        "issues": [
            {
                "issue_id": issue_id,
                "cluster_id": issue_id,
                "target_vector": list(TARGET),
                "baseline_identity": "NUMBER_EVENT_COMPOSITE_BASELINE",
                "baseline_probability_vector": list(BASELINE),
                "probe_probability_vector": list(probe),
            }
            for issue_id, probe in zip(ids, probes, strict=True)
        ],
    }


def _artifact(payload=None):
    return build_metric_artifact(
        payload or _input(),
        manifest=load_metric_kernel_manifest(MANIFEST_PATH),
        git_commit="c" * 40,
        working_tree_clean=True,
    )


def _assert_code(exc_info, code: str):
    assert exc_info.value.code == code


def test_01_frozen_manifest_validates() -> None:
    manifest = load_metric_kernel_manifest(MANIFEST_PATH)
    assert manifest.artifact_digest == (
        "56b9d0a62d43d167069e5222c7095383c9c5106bb3361b0b1def75cf2b6c86a2"
    )
    assert manifest.probability_epsilon == EPSILON
    assert manifest.payload["seed_policy"] == "none"


def test_02_theoretical_probability_is_exact_fraction() -> None:
    assert theoretical_number_probability() == Fraction(6, 33)


def test_03_valid_probability_vector_passes() -> None:
    assert validate_probability_vector(BASELINE) == BASELINE


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_04_non_finite_probability_rejected(value) -> None:
    probabilities = list(BASELINE)
    probabilities[0] = value
    with pytest.raises(MetricKernelError) as exc_info:
        validate_probability_vector(probabilities)
    _assert_code(exc_info, "non_finite_probability")


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_05_out_of_range_probability_rejected(value) -> None:
    probabilities = list(BASELINE)
    probabilities[0] = value
    with pytest.raises(MetricKernelError) as exc_info:
        validate_probability_vector(probabilities)
    _assert_code(exc_info, "probability_out_of_range")


@pytest.mark.parametrize("length", [0, 32, 34])
def test_06_probability_length_rejected(length) -> None:
    with pytest.raises(MetricKernelError) as exc_info:
        validate_probability_vector([0.5] * length)
    _assert_code(exc_info, "invalid_probability_vector")


def test_07_non_numeric_probability_rejected() -> None:
    with pytest.raises(MetricKernelError) as exc_info:
        validate_probability_vector([0.5] * 32 + ["0.5"])
    _assert_code(exc_info, "invalid_probability_value")


def test_08_clipping_diagnostics_are_explicit() -> None:
    raw = tuple([0.0, 1.0] + [0.5] * 31)
    clipped, diagnostics = clip_probabilities(raw)
    assert clipped[:2] == (EPSILON, 1 - EPSILON)
    assert diagnostics.clip_count_low == diagnostics.clip_count_high == 1
    assert diagnostics.clip_fraction == 2 / 33
    assert diagnostics.raw_min_probability == 0
    assert diagnostics.raw_max_probability == 1


def test_09_target_contract_accepts_six_of_33() -> None:
    assert validate_target_vector(TARGET) == TARGET


@pytest.mark.parametrize(
    ("target", "code"),
    [
        ([1] * 6 + [0] * 26, "invalid_target_vector"),
        ([1] * 5 + [0] * 28, "invalid_target_cardinality"),
        ([2] + [1] * 5 + [0] * 27, "invalid_target_value"),
    ],
)
def test_10_illegal_targets_fail_closed(target, code) -> None:
    with pytest.raises(MetricKernelError) as exc_info:
        validate_target_vector(target)
    _assert_code(exc_info, code)


def test_11_red_mask_target_consistency_remains_enforced() -> None:
    issue = SyntheticIssue(
        issue_index=1,
        red_mask=sum(1 << index for index in range(6)),
        sorted_red_numbers=(1, 2, 3, 4, 5, 6),
        target_vector=TARGET,
    )
    assert issue.red_mask == 63


def test_12_stable_bernoulli_formula_is_analytical() -> None:
    assert bernoulli_log_loss_nats(1, 0.25) == pytest.approx(-math.log(0.25))
    assert bernoulli_log_loss_nats(0, 0.25) == pytest.approx(-math.log1p(-0.25))


def test_13_log_loss_is_non_negative() -> None:
    assert all(
        bernoulli_log_loss_nats(target, probability) >= 0
        for target in (0, 1)
        for probability in (EPSILON, 0.25, 0.5, 0.75, 1 - EPSILON)
    )


def test_14_half_probability_is_symmetric() -> None:
    assert bernoulli_log_loss_nats(0, 0.5) == bernoulli_log_loss_nats(1, 0.5)


def test_15_nats_bits_conversion_is_reversible() -> None:
    for value in (0.0, 0.1, 1.0, 12.5):
        assert bits_to_nats(nats_to_bits(value)) == pytest.approx(value)


def test_16_analytic_baseline_matches_issue_loop() -> None:
    analytic = theoretical_baseline_loss()
    assert analytic["probability"]["numerator"] == 6
    assert analytic["probability"]["denominator"] == 33
    issue = _issue()
    assert issue.baseline_log_loss_nats_per_issue == pytest.approx(
        analytic["theoretical_baseline_nats_per_issue"]
    )
    assert issue.baseline_log_loss_bits_per_issue == pytest.approx(
        analytic["theoretical_baseline_bits_per_issue"]
    )


def test_17_baseline_loss_is_target_identity_invariant() -> None:
    shifted = tuple([0] * 27 + [1] * 6)
    assert _issue(target=shifted).baseline_log_loss_bits_per_issue == pytest.approx(
        _issue().baseline_log_loss_bits_per_issue
    )


def test_18_equal_probe_has_zero_pe1_gain() -> None:
    issue = _issue()
    assert issue.observed_log_loss_gain_bits_per_issue == 0
    assert issue.gain_direction == "zero_equal"
    assert issue.eligible_for_pe1 is True
    assert issue.eligible_for_final_pe2 is False


def test_19_better_probe_has_positive_gain() -> None:
    issue = _issue(probe=PERFECT)
    assert issue.probe_log_loss_bits_per_issue < issue.baseline_log_loss_bits_per_issue
    assert issue.observed_log_loss_gain_bits_per_issue > 0
    assert issue.gain_direction == "positive_probe_better"


def test_20_worse_probe_has_negative_gain() -> None:
    issue = _issue(probe=REVERSED)
    assert issue.probe_log_loss_bits_per_issue > issue.baseline_log_loss_bits_per_issue
    assert issue.observed_log_loss_gain_bits_per_issue < 0
    assert issue.gain_direction == "negative_probe_worse"


def test_21_issue_sum_and_mean_units_are_distinct() -> None:
    issue = _issue(probe=PERFECT)
    assert issue.probe_log_loss_bits_per_issue == pytest.approx(
        33 * issue.probe_log_loss_bits_per_number_event
    )
    assert issue.probe_log_loss_nats_per_issue == pytest.approx(
        33 * issue.probe_log_loss_nats_per_number_event
    )


def test_22_same_permutation_preserves_issue_scores() -> None:
    permutation = tuple(reversed(range(33)))
    target = tuple(TARGET[index] for index in permutation)
    probe = tuple(PERFECT[index] for index in permutation)
    permuted = _issue(target=target, probe=probe)
    original = _issue(probe=PERFECT)
    assert permuted.probe_log_loss_bits_per_issue == pytest.approx(
        original.probe_log_loss_bits_per_issue
    )
    assert permuted.probe_brier_sum_per_issue == pytest.approx(
        original.probe_brier_sum_per_issue
    )


def test_23_baseline_and_probe_use_same_epsilon() -> None:
    issue = _issue(probe=tuple([0.0] * 6 + [1.0] * 27))
    assert issue.baseline_clip_diagnostics.epsilon == EPSILON
    assert issue.probe_clip_diagnostics.epsilon == EPSILON


def test_24_perfect_binary_brier_matches_clipping_contract() -> None:
    issue = _issue(probe=tuple(TARGET))
    assert issue.probe_brier_sum_per_issue == pytest.approx(33 * EPSILON**2)


def test_25_baseline_brier_matches_formula() -> None:
    expected = 6 * (1 - BASELINE_P) ** 2 + 27 * BASELINE_P**2
    assert _issue().baseline_brier_sum_per_issue == pytest.approx(expected)


def test_26_brier_gain_sign_is_positive_for_better_probe() -> None:
    assert _issue(probe=PERFECT).brier_gain_per_issue > 0
    assert _issue(probe=REVERSED).brier_gain_per_issue < 0


def test_27_brier_sum_and_mean_are_distinct() -> None:
    issue = _issue(probe=PERFECT)
    assert issue.probe_brier_sum_per_issue == pytest.approx(
        33 * issue.probe_brier_mean_per_number_event
    )


def test_28_joint_code_length_reuses_exact_sample_space() -> None:
    result = joint_uniform_code_length()
    assert result["combination_space_size"] == legal_combination_count()
    assert result["joint_uniform_probability"]["numerator"] == 1
    assert result["joint_uniform_probability"]["denominator"] == legal_combination_count()
    assert 2 ** result["joint_code_length_bits"] == pytest.approx(
        legal_combination_count()
    )


def test_29_marginal_product_cannot_claim_joint_probability() -> None:
    reject_marginal_product_as_joint("LEGAL_SIX_RED_JOINT_UNIFORM")
    with pytest.raises(MetricKernelError) as exc_info:
        reject_marginal_product_as_joint("MARGINAL_BERNOULLI_PRODUCT")
    _assert_code(exc_info, "joint_probability_contract_violation")


def test_30_calibration_statistics_preserve_raw_predicted_count() -> None:
    probe = tuple([0.2] * 33)
    issue = _issue(probe=probe)
    assert issue.mean_predicted_probability == pytest.approx(0.2)
    assert issue.predicted_red_count == pytest.approx(6.6)
    assert issue.actual_red_count == 6
    assert issue.red_count_error == pytest.approx(0.6)


def test_31_aggregate_uses_issue_count_for_inference() -> None:
    aggregate = aggregate_issue_metrics(
        [_issue("a", PERFECT), _issue("b", BASELINE), _issue("c", REVERSED)]
    )
    assert aggregate.issue_count == aggregate.sample_size_for_inference == 3
    assert aggregate.iid_confidence_interval is None
    assert aggregate.uncertainty_status == "not_final_time_series_uncertainty"


def test_32_aggregate_cumulative_mean_and_median_are_correct() -> None:
    issues = [_issue("a", PERFECT), _issue("b", BASELINE), _issue("c", REVERSED)]
    aggregate = aggregate_issue_metrics(issues)
    gains = [item.observed_log_loss_gain_bits_per_issue for item in issues]
    assert aggregate.cumulative_observed_log_loss_gain_bits == pytest.approx(
        math.fsum(gains)
    )
    assert aggregate.mean_observed_log_loss_gain_bits_per_issue == pytest.approx(
        math.fsum(gains) / 3
    )
    assert aggregate.median_observed_log_loss_gain_bits_per_issue == sorted(gains)[1]


def test_33_aggregate_numeric_values_are_order_invariant_but_sequence_is_not() -> None:
    issues = [_issue("a", PERFECT), _issue("b", BASELINE), _issue("c", REVERSED)]
    forward = aggregate_issue_metrics(issues)
    reverse = aggregate_issue_metrics(list(reversed(issues)))
    assert forward.cumulative_observed_log_loss_gain_bits == (
        reverse.cumulative_observed_log_loss_gain_bits
    )
    assert forward.issue_ids_in_sequence != reverse.issue_ids_in_sequence


def test_34_long_row_adapter_rebuilds_issue_cluster() -> None:
    rows = [
        {
            "issue_id": "i1",
            "cluster_id": "i1",
            "red_number": number,
            "target": TARGET[number - 1],
            "probability": BASELINE[number - 1],
        }
        for number in reversed(range(1, 34))
    ]
    adapted = adapt_number_event_rows(rows)
    assert adapted[0].target_vector == TARGET
    assert adapted[0].probability_vector == BASELINE


@pytest.mark.parametrize(
    ("rows_mutation", "code"),
    [
        (lambda rows: rows.pop(), "invalid_issue_cluster_size"),
        (
            lambda rows: rows[0].update(red_number=2),
            "invalid_red_number_identity",
        ),
        (lambda rows: rows[0].pop("cluster_id"), "issue_cluster_missing"),
        (
            lambda rows: rows[0].update(cluster_id="other"),
            "issue_cluster_mismatch",
        ),
    ],
)
def test_35_long_row_failures_are_structured(rows_mutation, code) -> None:
    rows = [
        {
            "issue_id": "i1",
            "cluster_id": "i1",
            "red_number": number,
            "target": TARGET[number - 1],
            "probability": BASELINE[number - 1],
        }
        for number in range(1, 34)
    ]
    rows_mutation(rows)
    with pytest.raises(MetricKernelError) as exc_info:
        adapt_number_event_rows(rows)
    _assert_code(exc_info, code)


def test_36_unknown_baseline_fails_closed() -> None:
    with pytest.raises(MetricKernelError) as exc_info:
        evaluate_issue(
            issue_id="x",
            target_vector=TARGET,
            baseline_probability_vector=BASELINE,
            probe_probability_vector=BASELINE,
            baseline_identity="UNKNOWN",
        )
    _assert_code(exc_info, "unknown_baseline")


def test_37_baseline_probability_mismatch_fails_closed() -> None:
    with pytest.raises(MetricKernelError) as exc_info:
        evaluate_issue(
            issue_id="x",
            target_vector=TARGET,
            baseline_probability_vector=[0.5] * 33,
            probe_probability_vector=BASELINE,
        )
    _assert_code(exc_info, "baseline_probability_mismatch")


def test_38_issue_cluster_mismatch_fails_closed() -> None:
    with pytest.raises(MetricKernelError) as exc_info:
        evaluate_issue(
            issue_id="x",
            cluster_id="y",
            target_vector=TARGET,
            baseline_probability_vector=BASELINE,
            probe_probability_vector=BASELINE,
        )
    _assert_code(exc_info, "issue_cluster_mismatch")


def test_39_unit_guard_allows_only_bits_per_issue() -> None:
    contract = UnitContract()
    contract.require_practical_null_compatible("bits_per_issue")
    with pytest.raises(MetricKernelError) as exc_info:
        contract.require_practical_null_compatible("bits_per_number_event")
    _assert_code(exc_info, "unit_mismatch")


def test_40_metric_input_validates_without_evidence_claim() -> None:
    result = validate_metric_input(_input())
    assert result["valid"] is True
    assert result["descriptive_metric_artifact"] is True
    assert result["p2_gate_result"] is result["real_data_evidence"] is False


def test_41_artifact_is_deterministic_and_seedless() -> None:
    first = _artifact()
    second = _artifact()
    assert first == second
    assert first["seed_policy"] == "none"
    assert validate_metric_artifact(first)["valid"] is True


def test_42_artifact_substantive_change_changes_digest() -> None:
    first = _artifact(_input(probes=(BASELINE,)))
    second = _artifact(_input(probes=(PERFECT,)))
    assert first["artifact_digest"] != second["artifact_digest"]


def test_43_input_sequence_changes_artifact_identity_not_aggregate_value() -> None:
    first = _artifact(_input(probes=(PERFECT, REVERSED), issue_ids=("a", "b")))
    second = _artifact(_input(probes=(REVERSED, PERFECT), issue_ids=("b", "a")))
    assert first["artifact_digest"] != second["artifact_digest"]
    assert first["aggregate"]["cumulative_observed_log_loss_gain_bits"] == (
        second["aggregate"]["cumulative_observed_log_loss_gain_bits"]
    )


def test_44_object_field_order_does_not_change_artifact_digest() -> None:
    artifact = _artifact()
    reordered = dict(reversed(list(artifact.items())))
    assert validate_metric_artifact(reordered)["artifact_digest"] == artifact[
        "artifact_digest"
    ]


def test_45_unit_epsilon_baseline_and_sign_enter_metric_identity_digest() -> None:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    original = config_digest(payload)
    for mutation in (
        lambda value: value["unit_contract"].update(
            primary_reporting_unit="bits_per_number_event"
        ),
        lambda value: value["probability_clip"].update(epsilon=1e-5),
        lambda value: value["baseline"].update(identity="OTHER"),
        lambda value: value["gain_contract"].update(formula="probe_minus_baseline"),
    ):
        changed = deepcopy(payload)
        mutation(changed)
        assert config_digest(changed) != original


def test_46_pe2_remains_not_implemented() -> None:
    artifact = _artifact()
    assert artifact["bias_corrected_information_gain"] == {
        "status": "NOT_IMPLEMENTED",
        "reason": "requires synthetic calibration / bias validation contract",
        "eligible_for_final_pe2": False,
    }
    assert "true_mutual_information" not in json.dumps(artifact)


def test_47_cli_validate_labels_output_descriptive_only(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps(_input()), encoding="utf-8")
    result = CliRunner().invoke(
        cli.app,
        [
            "research-os",
            "information-theory",
            "metrics",
            "validate",
            "--input",
            str(input_path),
        ],
    )
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["p2_gate_result"] is payload["real_data_evidence"] is False


def test_48_kernel_source_uses_no_rng_or_real_history_import() -> None:
    source_dir = (
        ROOT
        / "apps/worker-python/dehps/research_os/information_theory/metrics"
    )
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(source_dir.glob("*.py"))
    )
    assert "numpy.random" not in source
    assert "random." not in source
    assert "history_draw" not in source
    assert "get_connection" not in source


def test_49_research_os_has_completed_preflight_and_unlocks_only_repair() -> None:
    manifest = load_m4_manifest(CONTROL_PATH)
    snapshot = ResearchOSControlPlane().resolve(manifest)
    resolutions = {item.task_key: item for item in snapshot.resolutions}
    status = build_m4_status(manifest, snapshot=snapshot)
    assert resolutions["m4-p2-metric-kernel"].status is TaskStatus.COMPLETED
    assert resolutions["m4-p2-walk-forward-probe-harness"].status is TaskStatus.COMPLETED
    assert (
        resolutions["m4-p2-injected-signal-calibration"].status
        is TaskStatus.COMPLETED
    )
    assert [item.task_key for item in snapshot.ready_queue] == [
        "m4-p2-repair-measurement-system"
    ]
    assert status["p2_subphase"]["completed"] == [
        "M4-P2.1",
        "M4-P2.2",
        "M4-P2.3",
        "M4-P2.4",
        "M4-P2.5",
        "M4-P2.6-PREFLIGHT",
    ]
    assert status["next_ready_task"] == "m4-p2-repair-measurement-system"
    assert status["progress"]["engineering_percent"] == 38
    assert status["progress"]["evidence_percent"] == 0


def test_50_governance_and_production_boundaries_remain_frozen() -> None:
    status = build_m4_status(load_m4_manifest(CONTROL_PATH))
    assert status["gate_status"] == {
        "promotion_gate": "CLOSED",
        "adaptive_supervisor": "STOPPED",
        "production_action": "none",
    }
    assert status["old_training_mainline"] == "FROZEN"
    assert status["formal_real_data_run"] == "NOT_STARTED"
    assert status["forward_event_2026085"]["m4_forward_evidence_eligible"] is False
    assert status["production_impact"] == "none"


def test_51_cli_evaluate_and_show_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_path = tmp_path / "input.json"
    output_dir = tmp_path / "artifacts"
    input_path.write_text(json.dumps(_input()), encoding="utf-8")
    monkeypatch.setattr(
        cli.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=""),
    )
    monkeypatch.setattr(cli, "resolve_git_commit", lambda _root: "c" * 40)
    runner = CliRunner()
    evaluated = runner.invoke(
        cli.app,
        [
            "research-os",
            "information-theory",
            "metrics",
            "evaluate",
            "--input",
            str(input_path),
            "--output-dir",
            str(output_dir),
        ],
    )
    assert evaluated.exit_code == 0, evaluated.stdout
    result = json.loads(evaluated.stdout)
    assert result["status"] == "DESCRIPTIVE_METRIC_ARTIFACT"
    assert result["p2_gate_result"] is result["real_data_evidence"] is False
    replayed = runner.invoke(
        cli.app,
        [
            "research-os",
            "information-theory",
            "metrics",
            "evaluate",
            "--input",
            str(input_path),
            "--output-dir",
            str(output_dir),
        ],
    )
    assert replayed.exit_code == 0, replayed.stdout
    assert json.loads(replayed.stdout)["artifact_digest"] == result["artifact_digest"]
    shown = runner.invoke(
        cli.app,
        [
            "research-os",
            "information-theory",
            "metrics",
            "show",
            "--digest",
            result["artifact_digest"],
            "--artifact-dir",
            str(output_dir),
        ],
    )
    assert shown.exit_code == 0, shown.stdout
    assert json.loads(shown.stdout)["artifact_digest"] == result["artifact_digest"]
