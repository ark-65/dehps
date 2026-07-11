from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_hourly_self_iteration_prompt_requires_budget_evidence_geometry():
    prompt = (REPO_ROOT / "scripts/hourly_self_iterate.sh").read_text(encoding="utf-8")

    for required_field in (
        "source_conversion_signature_count",
        "history_surface_signature_count",
        "performance_signature_count",
        "evidence_geometry",
        "budget_experiment_candidate_ready",
        "budget_review_limitations",
        "automatic_budget_change_allowed",
    ):
        assert required_field in prompt
    assert "每次最多选择一个来源预算变量" in prompt
    assert "不得同时削减多个来源" in prompt


def test_hourly_self_iteration_prompt_requires_sequential_null_coverage_audit():
    prompt = (REPO_ROOT / "scripts/hourly_self_iterate.sh").read_text(encoding="utf-8")

    for required_field in (
        "sequential_null_audit",
        "invariants_passed",
        "observed_round_coverage_ratio",
        "legacy_round_gap_ratio",
        "full_family_complete",
        "candidate_signal_interpretable",
        "automatic_promotion_allowed",
        "incomplete_observed_lower_bound",
    ):
        assert required_field in prompt
    assert "保持 noise risk" in prompt
    assert "不得把历史信号解释为预测能力" in prompt
