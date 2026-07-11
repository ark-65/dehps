# Intel Arc OpenCL Real-Score Probe — 2026-07-11

## Primary Goal

Determine whether the visible Intel Arc GPU can safely reduce DEHPS training wall time while preserving the existing CPU score and ranking contract.

## Non-Goals

- No model, feature, advisor, candidate source, weight, threshold, or promotion change.
- No GPU enablement based only on device visibility or a synthetic matrix benchmark.
- No tolerance-based substitution for the existing deterministic rounded-score contract.
- No same-history supervisor restart while forward issue `2026079` is pending.

## Environment

- Device: Intel Arc Graphics, Meteor Lake, PCI `8086:7d55`.
- Kernel driver: `i915`.
- OpenCL driver: `26.05.037020`.
- OpenCL device: available GPU, 128 compute units, FP16 and FP64 support.
- Vulkan device: Intel open-source Mesa driver `26.0.3`.
- Python probe binding: PyOpenCL `2025.1`.

The following Ubuntu runtime packages were installed for the probe: `intel-opencl-icd`, `libze-intel-gpu1`, `libze1`, `clinfo`, `vulkan-tools`, and `python3-pyopencl`. No project dependency or virtual-environment package was replaced.

## Probe Protocol

`dehps-opencl-score-equivalence-v1` uses:

- real history through issue `2026078`;
- the cached 1,105,506-row ranked universe;
- the real 32-component DEHPS scoring surface;
- 28 deterministic control perturbation configs;
- FP64 OpenCL with contraction disabled and compiler optimization disabled;
- the project production rounding rule of eight decimal places;
- Top10,000 set and target-rank comparisons;
- full wall time including CPU component construction and GPU transfer/copy overhead.

Acceptance requires exact rounded score matrices, identical Top-N sets, identical target ranks, and at least `1.05x` full end-to-end speedup.

## Result

```json
{
  "status": "rejected",
  "full_cpu_score_seconds": 1.122886,
  "full_gpu_score_seconds": 1.318997,
  "full_end_to_end_speedup": 0.851318,
  "rounded_score_matrix_exact": false,
  "rounded_changed_cell_count": 9,
  "rounded_max_abs_difference": 1.0000000050247593e-08,
  "top_set_match_count": 28,
  "top_set_config_count": 28,
  "target_ranks_equal": true,
  "blockers": [
    "rounded_score_matrix_not_exact",
    "insufficient_full_end_to_end_speedup"
  ]
}
```

The raw GPU kernel is not the limiting comparison. On the real scoring surface, CPU matrix multiplication plus rounding took about `0.139s`, while the GPU kernel alone took about `0.208s`; transfer, kernel, copy, and rounding took about `0.335s`. CPU component construction remained about `0.984s` for both paths.

## Decision

GPU training remains disabled. The watcher now reports `cpu_parallel_gpu_probe_rejected` instead of treating the device as merely unvalidated. It exposes the probe speedup, equivalence result, changed-cell count, Top-N agreement, target-rank agreement, and blockers in JSON, Markdown, and the operator summary.

The next acceptable GPU experiment must accelerate component construction or avoid repeated host-device transfers while preserving deterministic outputs across a predeclared multi-issue corpus. Re-running the same matrix multiply without changing that bottleneck is not a useful experiment.
