from __future__ import annotations

from dataclasses import replace

import pytest

from dehps.feature_runtime.compiler import FeatureRuntimeViolation
from dehps.scoring_kernel.feature_abi_opencl_backend import (
    OPENCL_KERNEL_DIGEST,
    OpenCLCapability,
    _load_pyopencl,
)


def capability() -> OpenCLCapability:
    return OpenCLCapability(
        platform_index=0,
        device_index=0,
        platform_name="fixture-platform",
        platform_vendor="fixture-vendor",
        platform_version="OpenCL 3.0",
        device_name="fixture-gpu",
        device_vendor="fixture-vendor",
        device_version="OpenCL 3.0",
        driver_version="fixture-driver",
        device_type=4,
        address_bits=64,
        endian_little=True,
        compiler_available=True,
        extensions=("cl_khr_fp64",),
        compute_units=128,
        max_clock_mhz=2250,
        global_memory_bytes=32 * 1024**3,
        max_allocation_bytes=4 * 1024**3,
        max_work_group_size=1024,
        local_memory_bytes=64 * 1024,
        local_size=64,
    )


def test_opencl_capability_identity_is_deterministic_and_kernel_bound() -> None:
    first = capability()
    second = capability()

    assert first.capability_digest == second.capability_digest
    assert first.telemetry()["kernel_digest"] == OPENCL_KERNEL_DIGEST
    assert first.telemetry()["device_name"] == "fixture-gpu"


@pytest.mark.parametrize(
    ("change", "code"),
    [
        ({"device_type": 2}, "opencl_device_not_gpu"),
        ({"endian_little": False}, "opencl_device_endian_mismatch"),
        ({"address_bits": 32}, "opencl_device_address_width_mismatch"),
        ({"compiler_available": False}, "opencl_compiler_unavailable"),
        ({"extensions": ()}, "opencl_fp64_unavailable"),
        ({"local_size": 2048}, "opencl_local_size_unsupported"),
    ],
)
def test_opencl_capability_rejects_incompatible_devices(change, code) -> None:
    with pytest.raises(FeatureRuntimeViolation) as error:
        replace(capability(), **change).validate(gpu_type=4)

    assert error.value.code == code


def test_opencl_missing_dependency_is_structured_and_never_falls_back(monkeypatch) -> None:
    def missing(name: str):
        raise ModuleNotFoundError(name)

    monkeypatch.setattr(
        "dehps.scoring_kernel.feature_abi_opencl_backend.importlib.import_module",
        missing,
    )

    with pytest.raises(FeatureRuntimeViolation) as error:
        _load_pyopencl()

    assert error.value.code == "opencl_dependency_unavailable"
