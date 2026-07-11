from __future__ import annotations

import dehps.runtime.compute_capability as capability


def test_compute_capability_keeps_visible_intel_gpu_unvalidated(monkeypatch):
    monkeypatch.setattr(
        capability,
        "_lspci_text",
        lambda: "00:02.0 VGA compatible controller: Intel Corporation Intel Arc Graphics",
    )
    monkeypatch.setattr(
        capability,
        "installed_accelerator_modules",
        lambda: [],
    )
    monkeypatch.setattr(capability.shutil, "which", lambda _name: None)
    monkeypatch.setattr(capability.Path, "exists", lambda _path: True)
    monkeypatch.setattr(
        capability,
        "load_accelerator_probe",
        lambda _path=capability.DEFAULT_ACCELERATOR_PROBE_PATH: {"status": "missing"},
    )

    summary = capability.compute_capability_summary(
        {"workers": 16, "matrix_backend": "NumPy feature matrix"}
    )

    assert summary["status"] == "cpu_parallel_gpu_backend_unvalidated"
    assert summary["cpu"]["configured_workers"] == 16
    assert summary["accelerator"]["gpu_device_visible"] is True
    assert summary["accelerator"]["intel_arc_visible"] is True
    assert summary["accelerator"]["gpu_backend_validated"] is False
    assert summary["accelerator"]["gpu_training_enabled"] is False
    assert summary["selection_changed"] is False
    assert summary["promotion_allowed"] is False


def test_compute_capability_does_not_treat_installed_module_as_validation(monkeypatch):
    monkeypatch.setattr(capability, "_lspci_text", lambda: "")
    monkeypatch.setattr(
        capability,
        "installed_accelerator_modules",
        lambda: ["torch", "openvino"],
    )
    monkeypatch.setattr(capability.shutil, "which", lambda _name: None)
    monkeypatch.setattr(capability.Path, "exists", lambda _path: True)
    monkeypatch.setattr(
        capability,
        "load_accelerator_probe",
        lambda _path=capability.DEFAULT_ACCELERATOR_PROBE_PATH: {"status": "missing"},
    )

    summary = capability.compute_capability_summary()

    assert summary["accelerator"]["installed_accelerator_modules"] == [
        "torch",
        "openvino",
    ]
    assert summary["accelerator"]["validated_gpu_backend"] is None
    assert summary["accelerator"]["gpu_backend_validated"] is False
    assert summary["accelerator"]["gpu_training_enabled"] is False


def test_compute_capability_surfaces_rejected_real_score_probe(monkeypatch, tmp_path):
    probe_path = tmp_path / "probe.json"
    probe_path.write_text(
        """
        {
          "protocol": "dehps-opencl-score-equivalence-v1",
          "generated_at": "2026-07-11T08:00:00Z",
          "status": "completed",
          "backend": {
            "name": "pyopencl",
            "device": "Intel(R) Arc(TM) Graphics",
            "driver": "26.05.037020"
          },
          "timing_seconds": {"full_end_to_end_speedup": 0.851},
          "equivalence": {
            "rounded_score_matrix_exact": false,
            "rounded_changed_cell_count": 9,
            "top_set_match_count": 28,
            "top_set_config_count": 28,
            "target_ranks_equal": true
          },
          "acceptance": {
            "accepted_for_training": false,
            "blockers": [
              "rounded_score_matrix_not_exact",
              "insufficient_full_end_to_end_speedup"
            ]
          }
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(capability, "_lspci_text", lambda: "Intel Arc Graphics")
    monkeypatch.setattr(capability, "_opencl_device_text", lambda: "Device #0: GPU Intel Arc")
    monkeypatch.setattr(capability.Path, "exists", lambda _path: True)

    summary = capability.compute_capability_summary(
        {"workers": 16, "matrix_backend": "NumPy feature matrix"},
        probe_path=probe_path,
    )

    assert summary["status"] == "cpu_parallel_gpu_probe_rejected"
    assert summary["action"] == "keep_cpu_parallel_optimize_gpu_kernel_before_reprobe"
    accelerator = summary["accelerator"]
    assert accelerator["opencl_runtime_visible"] is True
    assert accelerator["probe_status"] == "completed"
    assert accelerator["probe_accepted_for_training"] is False
    assert accelerator["probe_rounded_score_matrix_exact"] is False
    assert accelerator["probe_rounded_changed_cell_count"] == 9
    assert accelerator["probe_top_set_match_count"] == 28
    assert accelerator["probe_target_ranks_equal"] is True
    assert accelerator["probe_full_end_to_end_speedup"] == 0.851
    assert accelerator["gpu_backend_validated"] is False
    assert accelerator["gpu_training_enabled"] is False


def test_installed_accelerator_modules_ignores_broken_specs(monkeypatch):
    def fake_find_spec(name: str):
        if name == "torch":
            return object()
        if name == "jax":
            raise ModuleNotFoundError(name)
        return None

    monkeypatch.setattr(capability.importlib.util, "find_spec", fake_find_spec)

    assert capability.installed_accelerator_modules() == ["torch"]
