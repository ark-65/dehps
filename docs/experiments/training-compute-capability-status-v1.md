# Training Compute Capability Status v1

## Primary Goal

Expose the actual CPU and accelerator capability boundary in every training-watch payload so operators cannot confuse a visible GPU device with a validated or active GPU training backend.

## Non-Goals

- Do not install accelerator dependencies.
- Do not enable GPU training, migrate a rank kernel, or change the model.
- Do not change worker counts, BLAS thread caps, candidate generation, ranking, validation, or promotion.
- Do not treat faster computation as predictive improvement.

## Evidence Boundary

- Host CPU: Intel Core Ultra 7 155H, 22 logical CPUs.
- Accepted CPU configuration: 16 target workers with one BLAS thread per worker.
- Matrix backend: NumPy 2.4.6 with OpenBLAS.
- Device: Intel Meteor Lake-P Arc Graphics using the `i915` kernel driver; `/dev/dri/renderD128` is visible.
- NVIDIA tooling: unavailable.
- Project environment: no PyTorch, Intel Extension for PyTorch, `dpctl`, `dpnp`, PyOpenCL, OpenVINO, ONNX Runtime, JAX, CuPy, or TensorFlow.
- Existing measured CPU evidence: exact serial/parallel summary equality, about 3.4x faster Dynamic KDJ, about 4.2x faster Near Dynamic KDJ, and about 30% lower whole-round wall time in the accepted 16-worker run.

## Implementation

- Add `dehps-compute-capability-v1` as a read-only runtime summary.
- Report logical CPUs, configured workers, matrix backend, NumPy version, thread environment, and the ordered-target parallel protocol.
- Detect the DRI render node, Intel Arc PCI label, NVIDIA tool availability, and installed accelerator-related Python modules.
- Keep `validated_gpu_backend=null`, `gpu_backend_validated=false`, and `gpu_training_enabled=false`; installed modules alone never count as validation.
- Publish the summary in full watcher JSON, compact operator JSON, and Markdown.
- Require scheduled self-iteration to read the status before making any acceleration claim.

## Acceptance And Falsification

Accept the status only if it distinguishes device visibility from backend validation, preserves `selection_changed=false` and `promotion_allowed=false`, works while the supervisor is parked, and does not alter the forward-wait decision.

Reject any future GPU enablement unless a pinned backend enumerates the Intel device, a representative CPU/device kernel produces deterministic equivalent results, transfer-inclusive end-to-end timing improves under the same work, memory remains stable, and all leakage/frozen/promotion boundaries stay unchanged.

## Validation

- Compute-capability, watcher, and forward-wait targeted suites: `88 passed`.
- Full worker suite: `539 passed`.
- Python compilation and shell syntax passed.

## Live Verification

The parked run `20260711-132111` produced:

- `status=cpu_parallel_gpu_backend_unvalidated`;
- CPU `22` logical, `16` configured workers, NumPy feature matrix, NumPy `2.4.6`;
- Intel Arc and DRI render node visible;
- NVIDIA tooling absent;
- installed accelerator modules empty;
- validated GPU backend absent and GPU training disabled;
- selection and promotion unchanged.

The watcher simultaneously remained on `await_new_forward_issue` for `2026078 -> 2026079`, proving that capability observation neither restarted training nor bypassed the evidence wait.

## Next Verification

Keep the CPU path for the next forward issue. If a pinned Intel-compatible backend is deliberately added later, first implement a standalone device-enumeration and CPU/device equivalence probe; do not wire it into the supervisor until that probe and transfer-inclusive benchmark pass.
