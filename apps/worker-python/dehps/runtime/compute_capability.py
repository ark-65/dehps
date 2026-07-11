from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import numpy as np


ACCELERATOR_MODULE_NAMES = (
    "torch",
    "intel_extension_for_pytorch",
    "dpctl",
    "dpnp",
    "pyopencl",
    "openvino",
    "onnxruntime",
    "jax",
    "cupy",
    "tensorflow",
)
def _lspci_text() -> str:
    if not shutil.which("lspci"):
        return ""
    try:
        return subprocess.check_output(
            ["lspci"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""


def installed_accelerator_modules() -> list[str]:
    installed: list[str] = []
    for module_name in ACCELERATOR_MODULE_NAMES:
        try:
            available = importlib.util.find_spec(module_name) is not None
        except (ImportError, ModuleNotFoundError, ValueError):
            available = False
        if available:
            installed.append(module_name)
    return installed


def compute_capability_summary(
    supervisor_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    supervisor = supervisor_status if isinstance(supervisor_status, dict) else {}
    pci_text = _lspci_text()
    render_node = Path("/dev/dri/renderD128").exists()
    intel_arc_visible = "Intel Arc Graphics" in pci_text
    nvidia_tool_visible = bool(shutil.which("nvidia-smi"))
    installed_modules = installed_accelerator_modules()
    gpu_device_visible = bool(render_node or intel_arc_visible or nvidia_tool_visible)
    validated_gpu_backend = None
    gpu_backend_validated = False

    return {
        "protocol": "dehps-compute-capability-v1",
        "status": (
            "cpu_parallel_gpu_backend_unvalidated"
            if gpu_device_visible
            else "cpu_parallel_no_gpu_device"
        ),
        "action": (
            "keep_cpu_parallel_require_pinned_gpu_equivalence_probe"
            if gpu_device_visible
            else "keep_cpu_parallel"
        ),
        "cpu": {
            "logical_count": os.cpu_count(),
            "configured_workers": supervisor.get("workers"),
            "matrix_backend": supervisor.get("matrix_backend"),
            "numpy_version": np.__version__,
            "parallel_protocol": "ordered_target_parallel_v1",
            "equivalence_requirement": "serial_parallel_exact_summary_match",
        },
        "accelerator": {
            "gpu_device_visible": gpu_device_visible,
            "dri_render_node_visible": render_node,
            "intel_arc_visible": intel_arc_visible,
            "nvidia_tool_visible": nvidia_tool_visible,
            "installed_accelerator_modules": installed_modules,
            "validated_gpu_backend": validated_gpu_backend,
            "gpu_backend_validated": gpu_backend_validated,
            "gpu_training_enabled": False,
        },
        "selection_changed": False,
        "promotion_allowed": False,
        "interpretation": (
            "CPU target-level parallelism remains the only accepted training backend. A visible GPU "
            "is capability evidence only; GPU training stays disabled until a pinned backend enumerates "
            "the device, matches CPU results deterministically, and improves end-to-end wall time after "
            "transfer overhead."
        ),
    }
