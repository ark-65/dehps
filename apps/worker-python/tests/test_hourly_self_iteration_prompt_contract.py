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


def test_hourly_self_iteration_prompt_consumes_rejected_gpu_probe_evidence():
    prompt = (REPO_ROOT / "scripts/hourly_self_iterate.sh").read_text(encoding="utf-8")

    for required_field in (
        "probe_status",
        "probe_accepted_for_training",
        "probe_blockers",
        "probe_full_end_to_end_speedup",
        "probe_rounded_score_matrix_exact",
        "probe_rounded_changed_cell_count",
        "probe_target_ranks_equal",
        "cpu_parallel_gpu_probe_rejected",
    ):
        assert required_field in prompt
    assert "不是尚未尝试" in prompt
    assert "不得在内核、传输或组件构造瓶颈没有预声明变化时重复同一探针" in prompt
    assert "禁止自动启用训练或更改 selection/promotion" in prompt


def test_hourly_self_iteration_prompt_distinguishes_heavy_job_owner_pids():
    prompt = (REPO_ROOT / "scripts/hourly_self_iterate.sh").read_text(encoding="utf-8")

    for required_field in (
        "heavy_job_supervisor_relation",
        "different_active_pid",
        "different_inactive_pid",
        "selection_changed",
        "promotion_allowed",
    ):
        assert required_field in prompt
    assert "以 PID 关系而不是 `owner` 字符串" in prompt
    assert "不得覆盖锁元数据或启动竞争重任务" in prompt
    assert "不得把它误报成当前 parked supervisor 的异常" in prompt


def test_hourly_self_iteration_prompt_distinguishes_status_file_from_process():
    prompt = (REPO_ROOT / "scripts/hourly_self_iterate.sh").read_text(encoding="utf-8")

    for required_field in (
        "supervisor_lifecycle",
        "parked_waiting_for_forward_issue",
        "lifecycle_consistent",
        "running_pid_inactive",
        "pid_activity_scope=os_pid_exists_not_command_identity",
    ):
        assert required_field in prompt
    assert "只代表状态文件存在，不代表进程仍运行" in prompt
    assert "不得误报为 supervisor 崩溃或据此重启" in prompt
    assert "不能把它当作命令身份验证" in prompt


def test_hourly_self_iteration_prompt_requires_forward_release_fail_closed():
    prompt = (REPO_ROOT / "scripts/hourly_self_iterate.sh").read_text(encoding="utf-8")

    for requirement in (
        "先完成开奖前冻结的 static/dynamic/near 三线评估",
        "再刷新 advisor",
        "最后才允许启动 fresh supervisor",
        "拒绝空快照、缺线、重复 line",
        "candidate_count!=top_n",
        "as_of_issue>=predicted_issue",
        "任一评估返回 missing/mismatch/leakage/empty/partial-ranked-set 或非零退出",
        "禁止刷新 advisor 或启动 supervisor",
        "history 未再次变化也必须重试尚未接受的到期快照",
        "evaluated + leakage_passed + candidate_count==top_n",
        "不能因 changed_count=0 跳过失败重试",
        "inserted/updated count 大于零",
        "当前期次必须强制重评",
        "不能沿用可能基于 CSV 或旧开奖记录的接受结果",
    ):
        assert requirement in prompt


def test_hourly_self_iteration_prompt_requires_sync_conflict_fail_closed():
    prompt = (REPO_ROOT / "scripts/hourly_self_iterate.sh").read_text(encoding="utf-8")

    for requirement in (
        "最新 `conflict_count`",
        "累计 `recorded_data_conflict_count`",
        "冲突计数无法解析",
        "前向评估、advisor 刷新和 supervisor 启动前 fail closed",
        "inspect_parser_sync_conflicts",
        "不得把 status=success 误当作号码一致",
        "不得自动删除冲突证据",
    ):
        assert requirement in prompt
