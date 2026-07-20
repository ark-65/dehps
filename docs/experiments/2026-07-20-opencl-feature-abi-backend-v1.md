# OpenCL Feature ABI Backend v1 acceptance report

## Round contract

- Primary goal: implement and measure the first device backend behind the sealed Feature ABI Kernel
  boundary.
- Non-goals: no production backend switch, prediction generation, candidate rewrite, database write,
  supervisor restart, scoring/ranking/feature change, or shadow promotion claim.
- Production default: unchanged at `numpy_reference`.
- OpenCL selection: explicit research call only; the shared backend environment variable rejects it.

## Implementation

The new backend lazily loads the optional PyOpenCL dependency, deterministically selects and verifies
a GPU, compiles a digest-bound OpenCL 1.2 FP64 kernel, and rejects incompatible capabilities without
fallback. The device computes all 32-component scores, strict eight-decimal rounding, exact-rank
flags, and Red5 membership. Existing host `TopKReducer` logic remains authoritative for strict
`score DESC, lex_id ASC` ordering.

An initial Intel driver segmentation fault was traced to an implementation error: Python bound the
`target_ids` buffer to the kernel's scalar `start` argument because those two argument positions were
reversed. Aligning the host tuple with the OpenCL signature removed the fault. This is covered by
end-to-end exactness tests rather than ignored as a driver instability.

## Full legal-space evidence

The repeatable command was:

```text
python -m scripts.benchmark_opencl_feature_abi --tile-size 262144 --top-k 10000 --workers 8
```

It used the real history window ending before issue `2026082`, all `C(33,6) = 1,107,568` candidates,
eight weight configurations, two score passes, exact rank, Top10000, and Red5. NumPy and OpenCL
consumed the same `VerifiedRuntimePackage`.

All seven result fields were bit-exact:

- target scores;
- exact ranks;
- TopK candidate IDs;
- TopK scores;
- Red5 candidate IDs;
- Red5 scores;
- Red5 ranks.

Both backends produced result digest
`d5a0e0be28e61adc0b6f6e8823bd6c891ca17866f5908d6438860b988693c8e5` and artifact payload digest
`3baa933a383ad131955f5e6bf59615c28bab5e4460c4d252055517adeb51ace0`.

| Measurement | NumPy reference | OpenCL GPU |
| --- | ---: | ---: |
| Hot-path wall time | 0.346 s | 0.372 s |
| Device/kernel time | 0.071 s | 0.102 s |
| Rank reduction time | 0.158 s | 0.065 s |
| TopK merge time | 0.115 s | 0.054 s |
| Transfer in | 0 | 0.019 s |
| Transfer out | 0 | 0.006 s |
| Peak RSS | 767.6 MiB | 767.6 MiB |
| Swap | 0 | 0 |
| Strict exact | yes | yes |

Cold control-plane stages were 22.032 s for candidate construction, 23.595 s for Candidate ABI
construction, and 3.153 s for Runtime compilation. OpenCL device workspace peaked at about 86.3 MiB.
The tested device was Intel Arc Graphics with 128 compute units; its capability and kernel identities
are present in Kernel telemetry.

Focused OpenCL, Feature ABI, Planner, and boundary regression passed `60` tests. The complete Worker
suite passed `1281` tests with four existing Python 3.14 multiprocessing/fork deprecation warnings.

## Decision

Correctness passes. The first transfer-per-pass design does not beat NumPy on this workload: OpenCL is
about 7.5% slower on the measured hot path. It therefore remains a research backend and is not a
production-promotion candidate.

This negative performance result is not an iteration blocker. The next falsifiable device hypotheses
are persistent Feature/weight buffers and device-side hierarchical TopK. They should be tested as new
fingerprinted research rounds while duplicate formal prediction, three-issue shadow, and promotion
approval continue to govern only their respective production actions.
