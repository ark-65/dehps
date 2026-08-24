from __future__ import annotations

import copy
from datetime import date, datetime
from pathlib import Path

import pytest
from dehps.config import ROOT_DIR
from dehps.research_os.information_theory.measurement_system_v2 import (
    forward_prequential_confirmatory as successor,
)

from scripts import run_m4_p3_performance_runtime as runtime


def _history(count: int = 900) -> list[tuple[str, date, tuple[int, ...]]]:
    rows = []
    for index in range(count):
        start = index % 33
        red = tuple(sorted(((start + offset) % 33) + 1 for offset in range(6)))
        rows.append(
            (f"{2000 + index // 153:04d}{index % 153 + 1:03d}", date(2000, 1, 1), red)
        )
    return rows


def _reference_bundle() -> dict:
    source = successor.load_source_contract(root_dir=ROOT_DIR)
    preregistration, _ = successor.build_preregistration_artifacts(
        source_contract=source
    )
    dataset, model = successor.fit_model_artifacts(
        source_contract=source,
        preregistration=preregistration,
        history_rows=_history(),
        target_issue=runtime.TARGET_ISSUE,
    )
    candidates, baseline, checkpoint, report = successor.generate_predraw_artifacts(
        preregistration=preregistration,
        model=model,
        target_draw_date=date(2026, 8, 25),
        sealed_at=datetime(2026, 8, 25, 12, tzinfo=successor.SHANGHAI),
    )
    replay = successor.build_predraw_replay_artifact(
        model_candidates=candidates,
        random_baseline=baseline,
        checkpoint=checkpoint,
        report=report,
    )
    return {
        "source_contract": source,
        "preregistration": preregistration,
        "dataset": dataset,
        "model": model,
        "expected": {
            successor.MODEL_CANDIDATE_ARTIFACT_TYPE: candidates,
            successor.RANDOM_BASELINE_ARTIFACT_TYPE: baseline,
            successor.CHECKPOINT_ARTIFACT_TYPE: checkpoint,
            successor.PREDRAW_REPORT_ARTIFACT_TYPE: report,
            successor.PREDRAW_REPLAY_ARTIFACT_TYPE: replay,
        },
    }


def test_reference_run_is_exact_and_tamper_fails_closed() -> None:
    bundle = _reference_bundle()
    result = runtime.run_reference_bundle(bundle)
    assert result["status"] == "EXACT_REFERENCE_EQUIVALENCE_VERIFIED"
    assert result["probability_sum"] == 6.0
    assert len(result["probability_vector"]) == 33
    assert result["configuration_drift"] is False

    tampered = copy.deepcopy(bundle)
    tampered["expected"][successor.MODEL_CANDIDATE_ARTIFACT_TYPE]["body"][
        "candidate_count"
    ] = 99
    with pytest.raises(runtime.P3PerformanceRuntimeError, match="predraw output"):
        runtime.run_reference_bundle(tampered)


def test_benchmark_matrix_covers_frozen_outer_inner_hybrid_and_affinity() -> None:
    matrix = runtime.benchmark_matrix()
    identities = {
        (item["outer"], item["inner"], item["affinity"]) for item in matrix
    }
    assert all((value, 1, "all") in identities for value in runtime.OUTER_VALUES)
    assert all((1, value, "all") in identities for value in runtime.INNER_VALUES)
    assert all((outer, inner, "all") in identities for outer, inner in runtime.HYBRID_VALUES)
    assert all((1, 1, name) in identities for name in runtime.AFFINITIES)
    assert len(identities) == len(matrix)


def test_benchmark_selects_complete_median_wall_not_internal_phase(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def measured(_fixture, *, config, measured_runs):
        inner = int(config["inner"])
        affinity = str(config["affinity"])
        wall = 1.0 if (inner, affinity) == (2, "all") else 2.0
        internal = 10.0 if wall == 1.0 else 0.1
        return {
            **dict(config),
            "measured_runs": measured_runs,
            "median_wall_seconds": wall,
            "median_reference_seconds": internal,
        }

    monkeypatch.setattr(runtime, "_measure_config", measured)
    result = runtime.run_benchmark(
        fixture=tmp_path / "unused.json",
        runs=5,
        selected_only=False,
        selected_inner=1,
        selected_affinity="all",
    )
    assert result["selected"]["inner"] == 2
    assert result["selected"]["median_wall_seconds"] == 1.0
    assert result["selected"]["median_reference_seconds"] == 10.0


def _fake_power_sysfs(root: Path, *, msr: int, mmio: int) -> None:
    values = {
        runtime.MSR_RELATIVE: msr,
        runtime.MMIO_RELATIVE: mmio,
        runtime.MSR_MAX_RELATIVE: 40_000_000,
        runtime.MMIO_MAX_RELATIVE: 28_000_000,
        runtime.MSR_PL2_RELATIVE: 55_000_000,
        runtime.MMIO_PL2_RELATIVE: 43_000_000,
    }
    for relative, value in values.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(value), encoding="utf-8")


def test_power_reconcile_reads_compares_writes_drift_only_and_reads_back(
    tmp_path: Path,
) -> None:
    _fake_power_sysfs(tmp_path, msr=40_000_000, mmio=20_000_000)
    writes: list[tuple[Path, int]] = []

    def writer(relative: Path, value: int) -> None:
        writes.append((relative, value))
        (tmp_path / relative).write_text(str(value), encoding="utf-8")

    unchanged = runtime.reconcile_power_limits(
        msr_watts=40,
        mmio_watts=20,
        apply=True,
        sysfs_root=tmp_path,
        writer=writer,
    )
    assert unchanged["write_count"] == 0
    assert writes == []

    (tmp_path / runtime.MMIO_RELATIVE).write_text("19000000", encoding="utf-8")
    repaired = runtime.reconcile_power_limits(
        msr_watts=40,
        mmio_watts=20,
        apply=True,
        sysfs_root=tmp_path,
        writer=writer,
    )
    assert repaired["write_count"] == 1
    assert writes == [(runtime.MMIO_RELATIVE, 20_000_000)]
    assert repaired["after"]["mmio_pl1_uw"] == 20_000_000


@pytest.mark.parametrize("msr,mmio", [(39, 20), (40, 19), (40, 29)])
def test_power_profiles_outside_frozen_pair_fail_closed(msr: int, mmio: int) -> None:
    with pytest.raises(runtime.P3PerformanceRuntimeError, match="outside frozen"):
        runtime._validated_targets(msr_watts=msr, mmio_watts=mmio)


def test_watchdog_active_reapply_count_and_passive_no_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config = {
        "power_profile": {"msr_watts": 40, "mmio_watts": 20},
    }
    mode_path = tmp_path / "mode.json"
    state_path = tmp_path / "state.json"
    runtime.set_mode(mode="active", path=mode_path)
    monkeypatch.setattr(runtime, "_p3_unit_state", lambda: "activating")
    monkeypatch.setattr(
        runtime,
        "reconcile_power_limits",
        lambda **_kwargs: {"status": "APPLIED_AND_VERIFIED", "write_count": 1},
    )
    monkeypatch.setattr(
        runtime,
        "reconcile_platform_profile",
        lambda **_kwargs: {"changed": True, "after": "performance"},
    )
    active = runtime.watchdog_once(
        config=config,
        state_path=state_path,
        apply=True,
        mode_path=mode_path,
    )
    assert active["mode"] == "active"
    assert active["reapply_count"] == 2

    runtime.set_mode(mode="passive", path=mode_path)
    monkeypatch.setattr(
        runtime,
        "read_power_limits",
        lambda: {"msr_pl1_uw": 40_000_000, "mmio_pl1_uw": 20_000_000},
    )
    passive = runtime.watchdog_once(
        config=config,
        state_path=state_path,
        apply=True,
        mode_path=mode_path,
    )
    assert passive["mode"] == "passive"
    assert passive["reapply_count"] == 2
    assert passive["last_result"]["status"] == "PASSIVE_MONITOR"


def test_watchdog_recovers_stale_active_mode_after_reboot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    mode_path = tmp_path / "mode.json"
    state_path = tmp_path / "state.json"
    runtime.set_mode(mode="active", path=mode_path)
    monkeypatch.setattr(runtime, "_p3_unit_state", lambda: "inactive")
    monkeypatch.setattr(
        runtime,
        "read_power_limits",
        lambda: {
            "msr_pl1_uw": 40_000_000,
            "mmio_pl1_uw": 20_000_000,
            "msr_pl2_uw": 55_000_000,
            "mmio_pl2_uw": 43_000_000,
        },
    )
    result = runtime.watchdog_once(
        config={"power_profile": {"msr_watts": 40, "mmio_watts": 20}},
        state_path=state_path,
        apply=True,
        mode_path=mode_path,
    )
    assert result["mode"] == "passive"
    assert result["stale_active_recovered"] is True
    assert runtime._mode(mode_path) == "passive"


def test_runtime_config_and_operator_authority_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    runtime._json_write(
        path,
        {
            "schema_version": "dehps.p3.performance.v1",
            "selected": {
                "outer": 2,
                "inner": 22,
                "affinity": "all",
                "thread_profile": "native_default_explicit",
            },
            "power_profile": {"msr_watts": 40, "mmio_watts": 20},
            "active_interval_seconds": 2,
            "passive_interval_seconds": 60,
            "operator": {},
        },
    )
    with pytest.raises(runtime.P3PerformanceRuntimeError, match="selection changed"):
        runtime._load_runtime_config(path)
    with pytest.raises(runtime.P3PerformanceRuntimeError, match="authorization"):
        runtime.verify_operator_governance({})


def test_systemd_templates_wrap_existing_p3_service_without_competing_exec() -> None:
    watchdog = (
        ROOT_DIR / "deploy/systemd/dehps-p3-performance-watchdog.service"
    ).read_text(encoding="utf-8")
    dropin = (
        ROOT_DIR
        / "deploy/systemd/dehps-forward-prequential-successor.service.d/10-performance-runtime.conf"
    ).read_text(encoding="utf-8")
    assert "run_m4_p3_performance_runtime.py watch --apply" in watchdog
    assert "ExecStartPre=" in dropin and " enter --apply" in dropin
    assert "ExecStopPost=" in dropin and " exit --apply" in dropin
    assert "ExecStart=" not in dropin
    assert "Requires=dehps-p3-performance-watchdog.service" in dropin
    assert "CPUAffinity=0-21" in dropin


def test_install_dry_run_is_non_mutating_and_replaces_old_guard(tmp_path: Path) -> None:
    config_path = tmp_path / "does-not-exist.json"
    output = runtime.install_runtime(
        apply=False,
        config_path=config_path,
        operator={
            "request_key": "operator",
            "request_id": 1,
            "approval_decision_id": 2,
            "execution_id": 3,
            "payload_sha256": "a" * 64,
            "merged_commit": "b" * 40,
        },
        selected_inner=22,
        selected_affinity="all",
        selected_thread_profile="native_default_explicit",
        mmio_watts=20,
    )
    assert output["status"] == "DRY_RUN_VERIFIED"
    assert output["old_guard_replaced"] == runtime.OLD_GUARD_UNIT
    assert output["p3_unit_unchanged"] == runtime.P3_UNIT
    assert not config_path.exists()
