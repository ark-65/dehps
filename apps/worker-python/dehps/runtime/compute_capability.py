from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from dehps.config import ROOT_DIR


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
DEFAULT_ACCELERATOR_PROBE_PATH = (
    ROOT_DIR
    / "data/output/optimization/compute-probe/opencl-score-probe-latest.json"
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


def _opencl_device_text() -> str:
    if not shutil.which("clinfo"):
        return ""
    try:
        return subprocess.check_output(
            ["clinfo", "-l"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return ""


def load_accelerator_probe(path: Path = DEFAULT_ACCELERATOR_PROBE_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"status": "missing", "path": str(path)}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "status": "invalid",
            "path": str(path),
            "error": f"{type(exc).__name__}: {exc}",
        }
    if not isinstance(payload, dict):
        return {"status": "invalid", "path": str(path), "error": "invalid_root"}
    return {**payload, "path": str(path)}


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
    *,
    probe_path: Path = DEFAULT_ACCELERATOR_PROBE_PATH,
) -> dict[str, Any]:
    supervisor = supervisor_status if isinstance(supervisor_status, dict) else {}
    pci_text = _lspci_text()
    render_node = Path("/dev/dri/renderD128").exists()
    intel_arc_visible = "Intel Arc Graphics" in pci_text
    nvidia_tool_visible = bool(shutil.which("nvidia-smi"))
    installed_modules = installed_accelerator_modules()
    gpu_device_visible = bool(render_node or intel_arc_visible or nvidia_tool_visible)
    opencl_device_text = _opencl_device_text()
    opencl_runtime_visible = "GPU" in opencl_device_text or "Arc" in opencl_device_text
    probe = load_accelerator_probe(probe_path)
    acceptance = probe.get("acceptance") if isinstance(probe.get("acceptance"), dict) else {}
    backend = probe.get("backend") if isinstance(probe.get("backend"), dict) else {}
    timing = probe.get("timing_seconds") if isinstance(probe.get("timing_seconds"), dict) else {}
    equivalence = probe.get("equivalence") if isinstance(probe.get("equivalence"), dict) else {}
    probe_completed = probe.get("status") == "completed"
    probe_accepted = probe_completed and acceptance.get("accepted_for_training") is True
    probe_rejected = probe_completed and acceptance.get("accepted_for_training") is False
    validated_gpu_backend = backend.get("name") if probe_accepted else None
    gpu_backend_validated = probe_accepted

    if probe_accepted:
        status = "cpu_parallel_gpu_probe_accepted_not_enabled"
        action = "review_gpu_enablement_with_fresh_supervisor_equivalence"
    elif probe_rejected:
        status = "cpu_parallel_gpu_probe_rejected"
        action = "keep_cpu_parallel_optimize_gpu_kernel_before_reprobe"
    elif opencl_runtime_visible:
        status = "cpu_parallel_opencl_runtime_ready_probe_required"
        action = "run_pinned_gpu_equivalence_probe"
    elif gpu_device_visible:
        status = "cpu_parallel_gpu_backend_unvalidated"
        action = "keep_cpu_parallel_require_pinned_gpu_equivalence_probe"
    else:
        status = "cpu_parallel_no_gpu_device"
        action = "keep_cpu_parallel"

    return {
        "protocol": "dehps-compute-capability-v1",
        "status": status,
        "action": action,
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
            "opencl_runtime_visible": opencl_runtime_visible,
            "opencl_device_text": opencl_device_text.strip(),
            "probe_status": probe.get("status"),
            "probe_protocol": probe.get("protocol"),
            "probe_generated_at": probe.get("generated_at"),
            "probe_path": probe.get("path"),
            "probe_accepted_for_training": acceptance.get("accepted_for_training"),
            "probe_blockers": acceptance.get("blockers") or [],
            "probe_full_end_to_end_speedup": timing.get("full_end_to_end_speedup"),
            "probe_rounded_score_matrix_exact": equivalence.get(
                "rounded_score_matrix_exact"
            ),
            "probe_rounded_changed_cell_count": equivalence.get(
                "rounded_changed_cell_count"
            ),
            "probe_top_set_match_count": equivalence.get("top_set_match_count"),
            "probe_top_set_config_count": equivalence.get("top_set_config_count"),
            "probe_target_ranks_equal": equivalence.get("target_ranks_equal"),
            "probed_gpu_backend": backend.get("name"),
            "probed_gpu_device": backend.get("device"),
            "probed_gpu_driver": backend.get("driver"),
            "validated_gpu_backend": validated_gpu_backend,
            "gpu_backend_validated": gpu_backend_validated,
            "gpu_training_enabled": False,
        },
        "selection_changed": False,
        "promotion_allowed": False,
        "interpretation": (
            "CPU target-level parallelism remains the only enabled training backend. OpenCL device "
            "visibility and a completed probe are operational evidence only; GPU training stays disabled "
            "until the pinned real-score probe preserves deterministic outputs and improves full "
            "end-to-end wall time after component construction and transfer overhead."
        ),
    }
