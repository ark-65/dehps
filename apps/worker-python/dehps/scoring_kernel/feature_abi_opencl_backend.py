from __future__ import annotations

from dataclasses import dataclass, replace
import importlib
import os
import threading
import time
from typing import Any

import numpy as np

from dehps.contracts import canonical_digest
from dehps.feature_runtime.compiler import FeatureRuntimeViolation
from dehps.scoring_kernel.contracts import (
    KernelRequest,
    KernelResult,
    KernelWorkspace,
    WeightMatrix,
)
from dehps.scoring_kernel.feature_abi_backend import (
    FeatureABINumpyReferenceBackend,
    FeatureABITileResult,
    PreparedFeatureABIRuntime,
)
from dehps.unified_runtime import VerifiedRuntimePackage


OPENCL_BACKEND_NAME = "feature_abi_opencl_gpu"
OPENCL_BACKEND_VERSION = "feature_abi_opencl_gpu.v1"
OPENCL_PLATFORM_ENV = "DEHPS_OPENCL_PLATFORM_INDEX"
OPENCL_DEVICE_ENV = "DEHPS_OPENCL_DEVICE_INDEX"
OPENCL_LOCAL_SIZE_ENV = "DEHPS_OPENCL_LOCAL_SIZE"
DEFAULT_LOCAL_SIZE = 64

OPENCL_SOURCE = r"""
#pragma OPENCL EXTENSION cl_khr_fp64 : enable
#pragma OPENCL FP_CONTRACT OFF

__kernel void score_rank_tile(
    __global const double *values,
    __global const ulong *candidate_masks,
    __global const double *weights,
    __global const double *target_scores,
    const long start,
    __global const long *target_ids,
    const ulong target_mask,
    const int exact_rank,
    const int red5,
    const int row_count,
    const int config_count,
    __global double *scores,
    __global uchar *better_flags,
    __global uchar *equal_flags,
    __global uchar *red5_flags
) {
    const int row = (int)get_global_id(0);
    const int config = (int)get_global_id(1);
    if (row >= row_count || config >= config_count) {
        return;
    }

    double score = 0.0;
    const int value_offset = row * 32;
    const int weight_offset = config * 32;
    for (int component = 0; component < 32; ++component) {
        score += values[value_offset + component] * weights[weight_offset + component];
    }
    score = rint(score * 100000000.0) / 100000000.0;
    const int cell = row * config_count + config;
    scores[cell] = score;
    better_flags[cell] = (uchar)(exact_rank && score > target_scores[config]);
    equal_flags[cell] = (uchar)(
        exact_rank && score == target_scores[config] && (start + row) < target_ids[config]
    );
    if (config == 0) {
        red5_flags[row] = (uchar)(
            red5 && popcount(candidate_masks[row] & target_mask) == 5
        );
    }
}
"""

OPENCL_KERNEL_DIGEST = canonical_digest(
    {
        "backend_version": OPENCL_BACKEND_VERSION,
        "source": OPENCL_SOURCE,
        "build_options": ["-cl-std=CL1.2"],
        "score_round_digits": 8,
    },
    domain="dehps.feature-abi-opencl-kernel.v1",
)


def _reject(code: str, message: str, **context: Any) -> None:
    raise FeatureRuntimeViolation(code, message, **context)


def _load_pyopencl() -> Any:
    try:
        return importlib.import_module("pyopencl")
    except (ImportError, OSError) as exc:
        _reject(
            "opencl_dependency_unavailable",
            "OpenCL backend requires the optional pyopencl dependency",
            cause_type=type(exc).__name__,
            cause=str(exc),
        )


def _optional_index(name: str) -> int | None:
    value = str(os.getenv(name) or "").strip()
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        _reject("opencl_device_selector_invalid", f"{name} must be a non-negative integer")
    if parsed < 0:
        _reject("opencl_device_selector_invalid", f"{name} must be a non-negative integer")
    return parsed


def _local_size() -> int:
    value = str(os.getenv(OPENCL_LOCAL_SIZE_ENV) or DEFAULT_LOCAL_SIZE).strip()
    try:
        parsed = int(value)
    except ValueError:
        _reject(
            "opencl_local_size_invalid",
            f"{OPENCL_LOCAL_SIZE_ENV} must be a positive integer",
        )
    if parsed < 1:
        _reject(
            "opencl_local_size_invalid",
            f"{OPENCL_LOCAL_SIZE_ENV} must be a positive integer",
        )
    return parsed


@dataclass(frozen=True)
class OpenCLCapability:
    platform_index: int
    device_index: int
    platform_name: str
    platform_vendor: str
    platform_version: str
    device_name: str
    device_vendor: str
    device_version: str
    driver_version: str
    device_type: int
    address_bits: int
    endian_little: bool
    compiler_available: bool
    extensions: tuple[str, ...]
    compute_units: int
    max_clock_mhz: int
    global_memory_bytes: int
    max_allocation_bytes: int
    max_work_group_size: int
    local_memory_bytes: int
    local_size: int

    def identity_payload(self) -> dict[str, Any]:
        return {
            "backend_version": OPENCL_BACKEND_VERSION,
            "kernel_digest": OPENCL_KERNEL_DIGEST,
            "platform_index": self.platform_index,
            "device_index": self.device_index,
            "platform_name": self.platform_name,
            "platform_vendor": self.platform_vendor,
            "platform_version": self.platform_version,
            "device_name": self.device_name,
            "device_vendor": self.device_vendor,
            "device_version": self.device_version,
            "driver_version": self.driver_version,
            "device_type": self.device_type,
            "address_bits": self.address_bits,
            "endian_little": self.endian_little,
            "compiler_available": self.compiler_available,
            "extensions": list(self.extensions),
            "compute_units": self.compute_units,
            "max_clock_mhz": self.max_clock_mhz,
            "global_memory_bytes": self.global_memory_bytes,
            "max_allocation_bytes": self.max_allocation_bytes,
            "max_work_group_size": self.max_work_group_size,
            "local_memory_bytes": self.local_memory_bytes,
            "local_size": self.local_size,
        }

    @property
    def capability_digest(self) -> str:
        return canonical_digest(
            self.identity_payload(),
            domain="dehps.feature-abi-opencl-capability.v1",
        )

    def telemetry(self) -> dict[str, int | str]:
        return {
            "backend_version": OPENCL_BACKEND_VERSION,
            "kernel_digest": OPENCL_KERNEL_DIGEST,
            "platform_index": self.platform_index,
            "device_index": self.device_index,
            "platform_name": self.platform_name,
            "device_name": self.device_name,
            "driver_version": self.driver_version,
            "compute_units": self.compute_units,
            "global_memory_bytes": self.global_memory_bytes,
            "max_allocation_bytes": self.max_allocation_bytes,
            "local_size": self.local_size,
        }

    def validate(self, *, gpu_type: int) -> None:
        if not self.device_type & gpu_type:
            _reject("opencl_device_not_gpu", "selected OpenCL device is not a GPU")
        if not self.endian_little:
            _reject("opencl_device_endian_mismatch", "OpenCL backend requires little endian")
        if self.address_bits != 64:
            _reject("opencl_device_address_width_mismatch", "OpenCL backend requires 64-bit addressing")
        if not self.compiler_available:
            _reject("opencl_compiler_unavailable", "OpenCL device compiler is unavailable")
        if "cl_khr_fp64" not in self.extensions:
            _reject("opencl_fp64_unavailable", "strict_v1 OpenCL execution requires cl_khr_fp64")
        if self.local_size > self.max_work_group_size:
            _reject(
                "opencl_local_size_unsupported",
                "requested OpenCL local size exceeds device work-group capacity",
                requested=self.local_size,
                maximum=self.max_work_group_size,
            )


@dataclass(frozen=True)
class _OpenCLRuntime:
    cl: Any
    context: Any
    queue: Any
    program: Any
    device: Any
    capability: OpenCLCapability


_RUNTIME_CACHE: dict[tuple[str, str, str], _OpenCLRuntime] = {}
_RUNTIME_CACHE_LOCK = threading.RLock()


def _select_device(cl: Any) -> tuple[Any, Any, int, int]:
    try:
        platforms = list(cl.get_platforms())
    except Exception as exc:
        _reject(
            "opencl_platform_discovery_failed",
            "OpenCL platform discovery failed",
            cause_type=type(exc).__name__,
            cause=str(exc),
        )
    if not platforms:
        _reject("opencl_platform_unavailable", "no OpenCL platform is available")

    platform_index = _optional_index(OPENCL_PLATFORM_ENV)
    device_index = _optional_index(OPENCL_DEVICE_ENV)
    if platform_index is not None:
        if platform_index >= len(platforms):
            _reject("opencl_platform_index_out_of_range", "selected OpenCL platform does not exist")
        platform = platforms[platform_index]
        devices = list(platform.get_devices())
        selected_device_index = 0 if device_index is None else device_index
        if selected_device_index >= len(devices):
            _reject("opencl_device_index_out_of_range", "selected OpenCL device does not exist")
        return platform, devices[selected_device_index], platform_index, selected_device_index

    if device_index is not None:
        _reject(
            "opencl_device_selector_incomplete",
            f"{OPENCL_DEVICE_ENV} requires {OPENCL_PLATFORM_ENV}",
        )
    for pi, platform in enumerate(platforms):
        for di, device in enumerate(platform.get_devices()):
            if int(device.type) & int(cl.device_type.GPU):
                return platform, device, pi, di
    _reject("opencl_gpu_unavailable", "no OpenCL GPU device is available")


def _capability(cl: Any, platform: Any, device: Any, pi: int, di: int) -> OpenCLCapability:
    capability = OpenCLCapability(
        platform_index=pi,
        device_index=di,
        platform_name=str(platform.name),
        platform_vendor=str(platform.vendor),
        platform_version=str(platform.version),
        device_name=str(device.name),
        device_vendor=str(device.vendor),
        device_version=str(device.version),
        driver_version=str(device.driver_version),
        device_type=int(device.type),
        address_bits=int(device.address_bits),
        endian_little=bool(device.endian_little),
        compiler_available=bool(device.compiler_available),
        extensions=tuple(sorted(str(device.extensions).split())),
        compute_units=int(device.max_compute_units),
        max_clock_mhz=int(device.max_clock_frequency),
        global_memory_bytes=int(device.global_mem_size),
        max_allocation_bytes=int(device.max_mem_alloc_size),
        max_work_group_size=int(device.max_work_group_size),
        local_memory_bytes=int(device.local_mem_size),
        local_size=_local_size(),
    )
    capability.validate(gpu_type=int(cl.device_type.GPU))
    return capability


def _create_runtime() -> _OpenCLRuntime:
    cl = _load_pyopencl()
    platform, device, pi, di = _select_device(cl)
    capability = _capability(cl, platform, device, pi, di)
    try:
        context = cl.Context(devices=[device])
        queue = cl.CommandQueue(
            context,
            device=device,
            properties=cl.command_queue_properties.PROFILING_ENABLE,
        )
        program = cl.Program(context, OPENCL_SOURCE).build(options=["-cl-std=CL1.2"])
    except Exception as exc:
        _reject(
            "opencl_program_build_failed",
            "OpenCL context or strict_v1 kernel build failed",
            cause_type=type(exc).__name__,
            cause=str(exc),
            capability_digest=capability.capability_digest,
        )
    return _OpenCLRuntime(
        cl=cl,
        context=context,
        queue=queue,
        program=program,
        device=device,
        capability=capability,
    )


def _shared_runtime() -> _OpenCLRuntime:
    key = (
        str(os.getenv(OPENCL_PLATFORM_ENV) or ""),
        str(os.getenv(OPENCL_DEVICE_ENV) or ""),
        str(os.getenv(OPENCL_LOCAL_SIZE_ENV) or ""),
    )
    with _RUNTIME_CACHE_LOCK:
        runtime = _RUNTIME_CACHE.get(key)
        if runtime is None:
            runtime = _create_runtime()
            _RUNTIME_CACHE[key] = runtime
        return runtime


def opencl_backend_available() -> bool:
    try:
        _shared_runtime()
    except (FeatureRuntimeViolation, ValueError, OSError):
        return False
    return True


def _event_seconds(event: Any) -> float:
    event.wait()
    return max(0.0, float(event.profile.end - event.profile.start) / 1_000_000_000.0)


def _round_up(value: int, multiple: int) -> int:
    return ((value + multiple - 1) // multiple) * multiple


class FeatureABIOpenCLBackend(FeatureABINumpyReferenceBackend):
    """Research-only OpenCL implementation of the sealed Feature ABI boundary."""

    name = OPENCL_BACKEND_NAME

    def __init__(self) -> None:
        self._opencl: _OpenCLRuntime | None = None

    def _runtime(self) -> _OpenCLRuntime:
        if self._opencl is None:
            self._opencl = _shared_runtime()
        return self._opencl

    def prepare(
        self,
        verified_runtime: VerifiedRuntimePackage,
        *,
        code_commit: str,
    ) -> PreparedFeatureABIRuntime:
        runtime = self._runtime()
        prepared = super().prepare(verified_runtime, code_commit=code_commit)
        return replace(
            prepared,
            backend_capability_digest=runtime.capability.capability_digest,
            backend_capabilities=runtime.capability.telemetry(),
        )

    def score_rank(
        self,
        prepared: PreparedFeatureABIRuntime,
        weights: WeightMatrix,
        request: KernelRequest,
        workspace: KernelWorkspace | None = None,
    ) -> KernelResult:
        runtime = self._runtime()
        if prepared.backend_capability_digest != runtime.capability.capability_digest:
            _reject(
                "opencl_prepared_device_mismatch",
                "prepared OpenCL runtime belongs to another device capability identity",
                prepared=prepared.backend_capability_digest,
                selected=runtime.capability.capability_digest,
            )
        return super().score_rank(prepared, weights, request, workspace)

    def _tile(
        self,
        *,
        values: np.ndarray,
        candidate_masks: np.ndarray,
        start: int,
        weights: np.ndarray,
        target_scores: np.ndarray,
        target_ids: np.ndarray,
        exact_rank: bool,
        target_mask: np.uint64,
        red5: bool,
        workspace: KernelWorkspace,
    ) -> FeatureABITileResult:
        runtime = self._runtime()
        cl = runtime.cl
        row_count = len(values)
        config_count = int(weights.shape[0])
        scores = workspace.score_view(row_count, config_count)
        red5_flags = workspace.red5_view(row_count)
        better_flags = np.empty((row_count, config_count), dtype=np.uint8)
        equal_flags = np.empty((row_count, config_count), dtype=np.uint8)

        sizes = {
            "values": int(values.nbytes),
            "candidate_masks": int(candidate_masks.nbytes),
            "weights": int(weights.nbytes),
            "target_scores": int(target_scores.nbytes),
            "target_ids": int(target_ids.nbytes),
            "scores": int(scores.nbytes),
            "better_flags": int(better_flags.nbytes),
            "equal_flags": int(equal_flags.nbytes),
            "red5_flags": int(red5_flags.nbytes),
        }
        too_large = {
            name: size
            for name, size in sizes.items()
            if size > runtime.capability.max_allocation_bytes
        }
        if too_large:
            _reject(
                "opencl_allocation_limit_exceeded",
                "an OpenCL tile buffer exceeds max_mem_alloc_size",
                buffers=too_large,
                maximum=runtime.capability.max_allocation_bytes,
            )
        total_bytes = sum(sizes.values())
        if total_bytes > runtime.capability.global_memory_bytes:
            _reject(
                "opencl_global_memory_exceeded",
                "OpenCL tile workspace exceeds device global memory",
                required=total_bytes,
                available=runtime.capability.global_memory_bytes,
            )

        mf = cl.mem_flags
        buffers: list[Any] = []
        try:
            values_buffer = cl.Buffer(runtime.context, mf.READ_ONLY, size=values.nbytes)
            masks_buffer = cl.Buffer(runtime.context, mf.READ_ONLY, size=candidate_masks.nbytes)
            weights_buffer = cl.Buffer(runtime.context, mf.READ_ONLY, size=weights.nbytes)
            targets_buffer = cl.Buffer(runtime.context, mf.READ_ONLY, size=target_scores.nbytes)
            target_ids_buffer = cl.Buffer(runtime.context, mf.READ_ONLY, size=target_ids.nbytes)
            scores_buffer = cl.Buffer(runtime.context, mf.WRITE_ONLY, size=scores.nbytes)
            better_buffer = cl.Buffer(runtime.context, mf.WRITE_ONLY, size=better_flags.nbytes)
            equal_buffer = cl.Buffer(runtime.context, mf.WRITE_ONLY, size=equal_flags.nbytes)
            red5_buffer = cl.Buffer(runtime.context, mf.WRITE_ONLY, size=red5_flags.nbytes)
            buffers.extend(
                (
                    values_buffer,
                    masks_buffer,
                    weights_buffer,
                    targets_buffer,
                    target_ids_buffer,
                    scores_buffer,
                    better_buffer,
                    equal_buffer,
                    red5_buffer,
                )
            )
            write_events = [
                cl.enqueue_copy(runtime.queue, values_buffer, values, is_blocking=False),
                cl.enqueue_copy(runtime.queue, masks_buffer, candidate_masks, is_blocking=False),
                cl.enqueue_copy(runtime.queue, weights_buffer, weights, is_blocking=False),
                cl.enqueue_copy(runtime.queue, targets_buffer, target_scores, is_blocking=False),
                cl.enqueue_copy(runtime.queue, target_ids_buffer, target_ids, is_blocking=False),
            ]
            local_size = runtime.capability.local_size
            global_size = (_round_up(row_count, local_size), config_count)
            kernel = cl.Kernel(runtime.program, "score_rank_tile")
            kernel_args = (
                values_buffer,
                masks_buffer,
                weights_buffer,
                targets_buffer,
                np.int64(start),
                target_ids_buffer,
                np.uint64(target_mask),
                np.int32(bool(exact_rank)),
                np.int32(bool(red5)),
                np.int32(row_count),
                np.int32(config_count),
                scores_buffer,
                better_buffer,
                equal_buffer,
                red5_buffer,
            )
            for index, argument in enumerate(kernel_args):
                kernel.set_arg(index, argument)
            kernel_event = cl.enqueue_nd_range_kernel(
                runtime.queue,
                kernel,
                global_size,
                (local_size, 1),
                wait_for=write_events,
            )
            read_events = [
                cl.enqueue_copy(runtime.queue, scores, scores_buffer, is_blocking=False, wait_for=[kernel_event]),
                cl.enqueue_copy(runtime.queue, better_flags, better_buffer, is_blocking=False, wait_for=[kernel_event]),
                cl.enqueue_copy(runtime.queue, equal_flags, equal_buffer, is_blocking=False, wait_for=[kernel_event]),
                cl.enqueue_copy(runtime.queue, red5_flags, red5_buffer, is_blocking=False, wait_for=[kernel_event]),
            ]
            for event in read_events:
                event.wait()
            transfer_in_seconds = sum(_event_seconds(event) for event in write_events)
            kernel_seconds = _event_seconds(kernel_event)
            transfer_out_seconds = sum(_event_seconds(event) for event in read_events)
        except FeatureRuntimeViolation:
            raise
        except Exception as exc:
            _reject(
                "opencl_kernel_execution_failed",
                "OpenCL strict_v1 tile execution failed",
                cause_type=type(exc).__name__,
                cause=str(exc),
                capability_digest=runtime.capability.capability_digest,
                row_count=row_count,
                config_count=config_count,
            )
        rank_started = time.perf_counter()
        better = better_flags.sum(axis=0, dtype=np.int64)
        equal_before = equal_flags.sum(axis=0, dtype=np.int64)
        rank_seconds = time.perf_counter() - rank_started
        return FeatureABITileResult(
            scores=scores,
            better=np.ascontiguousarray(better),
            equal_before=np.ascontiguousarray(equal_before),
            red5_mask=red5_flags.view(np.bool_),
            kernel_seconds=kernel_seconds,
            rank_seconds=rank_seconds,
            transfer_in_seconds=transfer_in_seconds,
            transfer_out_seconds=transfer_out_seconds,
            device_workspace_bytes=total_bytes,
        )
