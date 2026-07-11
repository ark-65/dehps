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

    summary = capability.compute_capability_summary()

    assert summary["accelerator"]["installed_accelerator_modules"] == [
        "torch",
        "openvino",
    ]
    assert summary["accelerator"]["validated_gpu_backend"] is None
    assert summary["accelerator"]["gpu_backend_validated"] is False
    assert summary["accelerator"]["gpu_training_enabled"] is False


def test_installed_accelerator_modules_ignores_broken_specs(monkeypatch):
    def fake_find_spec(name: str):
        if name == "torch":
            return object()
        if name == "jax":
            raise ModuleNotFoundError(name)
        return None

    monkeypatch.setattr(capability.importlib.util, "find_spec", fake_find_spec)

    assert capability.installed_accelerator_modules() == ["torch"]
