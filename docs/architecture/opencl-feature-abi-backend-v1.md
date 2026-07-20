# OpenCL Feature ABI Backend v1

## Boundary

`feature_abi_opencl_gpu.v1` is an explicit, research-only implementation of the existing
Feature ABI and strict scoring/ranking contracts. It does not define features, candidate identity,
score meaning, or ordering. Its only trusted input is a sealed `VerifiedRuntimePackage`.

```text
VerifiedRuntimePackage
        -> KernelPlanner("opencl_gpu")
        -> OpenCL capability verifier
        -> Feature ABI float64 tiles + Candidate ABI masks
        -> strict_v1 score/rank flags/Red5 on device
        -> existing strict TopK reducer on host
        -> Runtime Envelope v1 / KernelResult
```

The production default remains `numpy_reference`. `opencl_gpu` cannot be selected through the shared
`DEHPS_SCORING_BACKEND` environment variable; research code must request it explicitly. A missing
dependency, incompatible device, allocation violation, digest mismatch, build failure, or execution
failure is a structured rejection. There is no fallback to another backend.

## Capability identity

The backend selects the first GPU deterministically unless both platform and device indices are
explicitly configured. The capability digest binds the backend/kernel versions and source, platform,
device, driver, address width, endianness, FP64 support, work-group limits, allocation limits, and
local size. A prepared Runtime cannot execute after capability identity changes.

Required device properties are:

- GPU device type;
- little-endian, 64-bit addressing;
- available OpenCL compiler;
- `cl_khr_fp64`;
- requested local size within the device work-group limit.

## Numerical contract

Each work item scores one Candidate/config cell using the frozen 32-component Feature ABI order,
FP64 accumulation, and strict eight-decimal rounding. The device also emits exact-rank comparison
flags and Red5 membership. The shared `TopKReducer` remains the sole implementation of
`score DESC, lex_id ASC`, including Red5 selection and hierarchical merge.

Changing tile size, reduction worker count, or device scheduling must not change target scores,
exact ranks, TopK candidate IDs/scores, Red5 IDs/scores/ranks, or the artifact payload digest.

## Current transfer model

Feature tiles, masks, weights, targets, and target IDs are transferred per score pass. Score and flag
buffers return to the host for strict TopK and final reductions. Telemetry separately records device
kernel time, host rank reduction, transfer-in/out time, device workspace, and capability identity.

This is the first portable device backend and a correctness/performance probe, not a promotion
candidate. Device-resident Feature buffers, persistent weights, fused device TopK, or subgroup/SIMD
specialization require separate measured rounds under the same contracts.

## Iteration and production gates

The following are production governance gates only:

- refusing a duplicate active formal prediction;
- accumulating three complete shadow issues;
- approving a production backend promotion.

They do not block new fingerprinted research, backend experiments, diagnostics, or historical
benchmarks. A failed performance hypothesis remains useful research evidence and must not be hidden by
changing the production backend.
