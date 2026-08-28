from __future__ import annotations

import copy
import json
import subprocess
from datetime import date, datetime
from pathlib import Path

import pytest
from dehps.config import ROOT_DIR
from dehps.research_os.information_theory.measurement_system_v2 import (
    forward_prequential_confirmatory as successor,
)

from scripts import run_m4_p3_performance_runtime as runtime


def _git(root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _compatibility_repository(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "compatibility-repository"
    root.mkdir(parents=True)
    _git(root, "init", "--initial-branch=main")
    _git(root, "config", "user.name", "DEHPS Test")
    _git(root, "config", "user.email", "dehps-test@example.invalid")
    for index, relative in enumerate(runtime.RUNTIME_COMPATIBILITY_PATHS):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"frozen compatibility source {index}\n", encoding="utf-8")
    _git(root, "add", "--all")
    _git(root, "commit", "-m", "frozen compatibility closure")
    return root, _git(root, "rev-parse", "HEAD")


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
    identities = {(item["outer"], item["inner"], item["affinity"]) for item in matrix}
    assert all((value, 1, "all") in identities for value in runtime.OUTER_VALUES)
    assert all((1, value, "all") in identities for value in runtime.INNER_VALUES)
    assert all(
        (outer, inner, "all") in identities for outer, inner in runtime.HYBRID_VALUES
    )
    assert all((1, 1, name) in identities for name in runtime.AFFINITIES)
    assert len(identities) == len(matrix)


def test_benchmark_selects_frozen_workload_end_to_end_not_process_startup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def measured(_fixture, *, config, measured_runs):
        inner = int(config["inner"])
        affinity = str(config["affinity"])
        internal = 1.0 if (inner, affinity) == (2, "all") else 2.0
        wall = 10.0 if internal == 1.0 else 0.1
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
    assert result["selected"]["median_wall_seconds"] == 10.0
    assert result["selected"]["median_reference_seconds"] == 1.0


def _synthetic_measurement(config: dict, *, value: float, warmup: int) -> dict:
    measurement = {
        "wall_seconds": value + 1.0,
        "workloads": int(config["outer"]),
        "workloads_per_second": int(config["outer"]) / (value + 1.0),
        "median_reference_seconds": value,
        "median_phase_seconds": {
            "refit": value / 4,
            "candidate": value / 2,
            "replay": value / 8,
            "end_to_end": value,
        },
        "peak_rss_kib_sum": 100,
    }
    return runtime._summarize_config(
        config=config,
        measurements=[measurement],
        telemetry={
            "sample_count": 1,
            "pkg_watt_mean": 20.0,
            "pkg_watt_peak": 21.0,
            "temperature_c_peak": 80.0,
            "frequency_mhz_mean": 3500.0,
            "frequency_mhz_peak": 3600.0,
            "busy_percent_mean": 10.0,
            "busy_percent_peak": 20.0,
            "thermal_throttle_count_delta": 0,
            "thermal_throttle_time_ms_delta": 0,
        },
        warmup_runs=warmup,
    )


def test_power_profiles_are_counterbalanced_and_select_frozen_workload_median(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    current = {"mmio": 20}

    def reconcile(*, mmio_watts, **_kwargs):
        current["mmio"] = mmio_watts
        return {
            "after": {
                "msr_pl1_uw": 40_000_000,
                "mmio_pl1_uw": mmio_watts * 1_000_000,
                "msr_pl2_uw": 55_000_000,
                "mmio_pl2_uw": 43_000_000,
            }
        }

    def measured(_fixture, *, config, measured_runs, perform_warmup=True):
        assert measured_runs == 1
        value = 0.1 if current["mmio"] == 20 else 0.2
        return _synthetic_measurement(
            dict(config), value=value, warmup=int(perform_warmup)
        )

    monkeypatch.setattr(runtime, "reconcile_power_limits", reconcile)
    monkeypatch.setattr(runtime, "_measure_config", measured)
    output = runtime.run_power_profile_benchmark(
        fixture=tmp_path / "unused.json",
        selected={
            "inner": 1,
            "affinity": "all",
            "thread_profile": "uniform_1",
        },
        runs=5,
    )
    assert output["trial_order_mmio_watts"] == [20, 28, 28, 20, 20, 28, 28, 20, 20, 28]
    assert output["selected"] == {"msr_watts": 40, "mmio_watts": 20}
    assert all(item["benchmark"]["measured_runs"] == 5 for item in output["profiles"])


def test_near_tie_finalists_extend_to_nine_in_alternating_order(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    extension_order: list[int] = []

    def measured(_fixture, *, config, measured_runs, perform_warmup=True):
        identity = (int(config["outer"]), int(config["inner"]), str(config["affinity"]))
        if identity == (1, 1, "all"):
            value = 1.0
        elif identity == (1, 2, "all"):
            value = 1.01
        else:
            value = 2.0
        if not perform_warmup:
            extension_order.append(int(config["inner"]))
        single = _synthetic_measurement(
            dict(config), value=value, warmup=int(perform_warmup)
        )
        return runtime._summarize_config(
            config=dict(config),
            measurements=single["measurements"] * measured_runs,
            telemetry=single["telemetry"],
            warmup_runs=int(perform_warmup),
        )

    monkeypatch.setattr(runtime, "_measure_config", measured)
    output = runtime.run_benchmark(
        fixture=tmp_path / "unused.json",
        runs=5,
        selected_only=False,
        selected_inner=1,
        selected_affinity="all",
    )
    assert extension_order == [1, 2, 2, 1, 1, 2, 2, 1]
    finalists = {
        item["inner"]: item
        for item in output["matrix"]
        if item["outer"] == 1 and item["affinity"] == "all" and item["inner"] in {1, 2}
    }
    assert finalists[1]["measured_runs"] == 9
    assert finalists[2]["measured_runs"] == 9


def test_real_drift_fixture_uses_watchdog_reconcile_and_restores_passive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    limits = {
        "msr_pl1_uw": 40_000_000,
        "mmio_pl1_uw": 20_000_000,
        "msr_pl2_uw": 55_000_000,
        "mmio_pl2_uw": 43_000_000,
        "msr_pl1_max_uw": 28_000_000,
        "mmio_pl1_max_uw": 28_000_000,
    }

    def writer(path: Path, value: int) -> None:
        limits["msr_pl1_uw" if path == runtime.MSR_RELATIVE else "mmio_pl1_uw"] = value

    def reconcile(*, msr_watts, mmio_watts, apply, **_kwargs):
        targets = {
            "msr_pl1_uw": msr_watts * 1_000_000,
            "mmio_pl1_uw": mmio_watts * 1_000_000,
        }
        write_count = sum(limits[key] != value for key, value in targets.items())
        if apply:
            limits.update(targets)
        return {
            "status": "APPLIED_AND_VERIFIED",
            "write_count": write_count,
            "after": dict(limits),
        }

    monkeypatch.setattr(runtime, "_docker_sysfs_write", writer)
    monkeypatch.setattr(runtime, "read_power_limits", lambda: dict(limits))
    monkeypatch.setattr(runtime, "reconcile_power_limits", reconcile)
    monkeypatch.setattr(
        runtime,
        "reconcile_platform_profile",
        lambda **_kwargs: {"changed": False, "after": "performance"},
    )
    monkeypatch.setattr(
        runtime,
        "read_runtime_telemetry",
        lambda: {
            "pkg_watt_mean": 20.0,
            "frequency_mhz_mean": 3500.0,
            "temperature_c_peak": 80.0,
        },
    )
    output = runtime.run_drift_fixture(
        config={
            "power_profile": {
                "msr_watts": 40,
                "mmio_watts": 20,
                "msr_pl2_watts": 55,
                "mmio_pl2_watts": 43,
            }
        },
        state_path=tmp_path / "state.json",
        mode_path=tmp_path / "mode.json",
    )
    assert output["status"] == "DRIFT_REAPPLY_READBACK_VERIFIED"
    assert output["reapply_delta"] == 2
    assert output["final_state"]["mode"] == "passive"
    assert limits["msr_pl1_uw"] == 40_000_000
    assert limits["mmio_pl1_uw"] == 20_000_000


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
        "power_profile": {
            "msr_watts": 40,
            "mmio_watts": 20,
            "msr_pl2_watts": 55,
            "mmio_pl2_watts": 43,
        },
    }
    mode_path = tmp_path / "mode.json"
    state_path = tmp_path / "state.json"
    runtime.set_mode(mode="active", path=mode_path)
    monkeypatch.setattr(runtime, "_p3_unit_state", lambda: "activating")
    monkeypatch.setattr(
        runtime,
        "reconcile_power_limits",
        lambda **_kwargs: {
            "status": "APPLIED_AND_VERIFIED",
            "write_count": 1,
            "after": {
                "msr_pl1_uw": 40_000_000,
                "mmio_pl1_uw": 20_000_000,
                "msr_pl2_uw": 55_000_000,
                "mmio_pl2_uw": 43_000_000,
            },
        },
    )
    monkeypatch.setattr(
        runtime,
        "reconcile_platform_profile",
        lambda **_kwargs: {"changed": True, "after": "performance"},
    )
    monkeypatch.setattr(
        runtime,
        "read_runtime_telemetry",
        lambda: {
            "pkg_watt_mean": 20.0,
            "frequency_mhz_mean": 3500.0,
            "temperature_c_peak": 80.0,
        },
    )
    active = runtime.watchdog_once(
        config=config,
        state_path=state_path,
        apply=True,
        mode_path=mode_path,
    )
    assert active["mode"] == "active"
    assert active["reapply_count"] == 2
    assert active["target_msr_pl2_w"] == 55
    assert active["actual_mmio_pl2_w"] == 43
    assert active["package_power_w"] == 20.0

    runtime.set_mode(mode="passive", path=mode_path)
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
        config={
            "power_profile": {
                "msr_watts": 40,
                "mmio_watts": 20,
                "msr_pl2_watts": 55,
                "mmio_pl2_watts": 43,
            }
        },
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
            "schema_version": "dehps.p3.performance.v2",
            "selected": {
                "outer": 2,
                "inner": 22,
                "affinity": "all",
                "thread_profile": "native_default_explicit",
            },
            "power_profile": {
                "msr_watts": 40,
                "mmio_watts": 20,
                "msr_pl2_watts": 55,
                "mmio_pl2_watts": 43,
            },
            "active_interval_seconds": 2,
            "passive_interval_seconds": 60,
            "operator": {},
            "runtime_compatibility_closure": {},
        },
    )
    with pytest.raises(runtime.P3PerformanceRuntimeError, match="closure shape"):
        runtime._load_runtime_config(path)
    with pytest.raises(runtime.P3PerformanceRuntimeError, match="authorization"):
        runtime.verify_operator_governance({})


def test_frozen_base_runtime_compatibility_closure_is_exact() -> None:
    closure = runtime.build_runtime_compatibility_closure(
        "29bab44ac655d05ea710d7fd758adf96dec9f6c6"
    )
    assert closure["schema_version"] == runtime.RUNTIME_COMPATIBILITY_CLOSURE_SCHEMA
    assert closure["closure_digest"] == (
        "bda283c9081b77774364aa61b085641f1222e961aa4443e61dcea1ecce71b497"
    )
    assert [item["path"] for item in closure["records"]] == list(
        runtime.RUNTIME_COMPATIBILITY_PATHS
    )
    assert all(
        set(item) == {"path", "git_mode", "git_type", "git_blob", "bytes", "sha256"}
        and item["git_mode"] == "100644"
        and item["git_type"] == "blob"
        for item in closure["records"]
    )


def test_runtime_compatibility_allows_only_unprotected_descendant_change(
    tmp_path: Path,
) -> None:
    root, operator_commit = _compatibility_repository(tmp_path)
    closure = runtime.build_runtime_compatibility_closure(
        operator_commit, root_dir=root
    )
    unrelated = root / "docs/unprotected-descendant.txt"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text("allowed unrelated change\n", encoding="utf-8")
    _git(root, "add", "--all")
    _git(root, "commit", "-m", "unprotected descendant")

    runtime.verify_runtime_compatibility_closure(
        operator_commit=operator_commit,
        closure=closure,
        root_dir=root,
    )


@pytest.mark.parametrize("relative", runtime.RUNTIME_COMPATIBILITY_PATHS)
@pytest.mark.parametrize(
    "mutation", ("dirty", "bytes", "delete", "rename", "symlink", "mode", "nonregular")
)
def test_runtime_compatibility_rejects_every_protected_path_mutation(
    tmp_path: Path, relative: str, mutation: str
) -> None:
    root, operator_commit = _compatibility_repository(tmp_path)
    closure = runtime.build_runtime_compatibility_closure(
        operator_commit, root_dir=root
    )
    path = root / relative
    should_commit = mutation not in {"dirty", "nonregular"}
    if mutation in {"dirty", "bytes"}:
        path.write_text(
            path.read_text(encoding="utf-8") + f"{mutation} drift\n",
            encoding="utf-8",
        )
    elif mutation == "delete":
        path.unlink()
    elif mutation == "rename":
        path.rename(path.with_name(path.name + ".renamed"))
    elif mutation == "symlink":
        path.unlink()
        target_relative = (
            runtime.RUNTIME_COMPATIBILITY_PATHS[1]
            if relative == runtime.RUNTIME_COMPATIBILITY_PATHS[0]
            else runtime.RUNTIME_COMPATIBILITY_PATHS[0]
        )
        path.symlink_to(root / target_relative)
    elif mutation == "mode":
        path.chmod(0o755)
    else:
        path.unlink()
        path.mkdir()
    if should_commit:
        _git(root, "add", "--all")
        _git(root, "commit", "-m", f"protected {mutation} drift")

    with pytest.raises(runtime.P3PerformanceRuntimeError):
        runtime.verify_runtime_compatibility_closure(
            operator_commit=operator_commit,
            closure=closure,
            root_dir=root,
        )


@pytest.mark.parametrize(
    "field", ["path", "git_mode", "git_type", "git_blob", "bytes", "sha256"]
)
def test_runtime_compatibility_rejects_each_record_field_drift(
    tmp_path: Path, field: str
) -> None:
    root, operator_commit = _compatibility_repository(tmp_path)
    closure = runtime.build_runtime_compatibility_closure(
        operator_commit, root_dir=root
    )
    tampered = copy.deepcopy(closure)
    record = tampered["records"][0]
    replacements = {
        "path": "unexpected/path.py",
        "git_mode": "100755",
        "git_type": "tree",
        "git_blob": "f" * 40,
        "bytes": int(record["bytes"]) + 1,
        "sha256": "f" * 64,
    }
    record[field] = replacements[field]
    preimage = {
        "schema_version": tampered["schema_version"],
        "records": tampered["records"],
    }
    tampered["closure_digest"] = runtime._closure_digest(preimage)

    with pytest.raises(runtime.P3PerformanceRuntimeError):
        runtime.verify_runtime_compatibility_closure(
            operator_commit=operator_commit,
            closure=tampered,
            root_dir=root,
        )


@pytest.mark.parametrize("mutation", ("missing", "extra", "reordered"))
def test_runtime_compatibility_rejects_record_set_and_order_drift(
    tmp_path: Path, mutation: str
) -> None:
    root, operator_commit = _compatibility_repository(tmp_path)
    closure = runtime.build_runtime_compatibility_closure(
        operator_commit, root_dir=root
    )
    tampered = copy.deepcopy(closure)
    if mutation == "missing":
        tampered["records"].pop()
    elif mutation == "extra":
        tampered["records"].append(copy.deepcopy(tampered["records"][-1]))
    else:
        tampered["records"][0], tampered["records"][1] = (
            tampered["records"][1],
            tampered["records"][0],
        )
    preimage = {
        "schema_version": tampered["schema_version"],
        "records": tampered["records"],
    }
    tampered["closure_digest"] = runtime._closure_digest(preimage)
    with pytest.raises(runtime.P3PerformanceRuntimeError):
        runtime.verify_runtime_compatibility_closure(
            operator_commit=operator_commit,
            closure=tampered,
            root_dir=root,
        )


def test_runtime_compatibility_rejects_non_ancestor_head(
    tmp_path: Path,
) -> None:
    root, operator_commit = _compatibility_repository(tmp_path)
    closure = runtime.build_runtime_compatibility_closure(
        operator_commit, root_dir=root
    )
    _git(root, "checkout", "--orphan", "unrelated-history")
    _git(root, "rm", "-rf", ".")
    marker = root / "unrelated.txt"
    marker.write_text("unrelated history\n", encoding="utf-8")
    _git(root, "add", "--all")
    _git(root, "commit", "-m", "unrelated history")

    with pytest.raises(
        runtime.P3PerformanceRuntimeError,
        match="operator merged commit is not an ancestor",
    ):
        runtime.verify_runtime_compatibility_closure(
            operator_commit=operator_commit,
            closure=closure,
            root_dir=root,
        )


def test_runtime_config_round_trip_binds_exact_compatibility_closure(
    tmp_path: Path,
) -> None:
    root, operator_commit = _compatibility_repository(tmp_path)
    closure = runtime.build_runtime_compatibility_closure(
        operator_commit, root_dir=root
    )
    path = tmp_path / "config.json"
    config = {
        "schema_version": "dehps.p3.performance.v2",
        "selected": {
            "outer": 1,
            "inner": 22,
            "affinity": "all",
            "thread_profile": "native_default_explicit",
        },
        "power_profile": {
            "msr_watts": 40,
            "mmio_watts": 20,
            "msr_pl2_watts": 55,
            "mmio_pl2_watts": 43,
        },
        "active_interval_seconds": 2,
        "passive_interval_seconds": 60,
        "operator": {
            "request_key": "operator",
            "request_id": 1,
            "approval_decision_id": 2,
            "execution_id": 3,
            "payload_sha256": "a" * 64,
            "merged_commit": operator_commit,
        },
        "runtime_compatibility_closure": closure,
    }
    runtime._json_write(path, config)
    assert runtime._load_runtime_config(path) == config

    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["runtime_compatibility_closure"]["closure_digest"] = "0" * 64
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(runtime.P3PerformanceRuntimeError, match="digest changed"):
        runtime._load_runtime_config(path)


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
    merged_commit = _git(ROOT_DIR, "rev-parse", "HEAD")
    output = runtime.install_runtime(
        apply=False,
        config_path=config_path,
        operator={
            "request_key": "operator",
            "request_id": 1,
            "approval_decision_id": 2,
            "execution_id": 3,
            "payload_sha256": "a" * 64,
            "merged_commit": merged_commit,
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
