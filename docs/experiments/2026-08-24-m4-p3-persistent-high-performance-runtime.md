# M4-P3 persistent high-performance runtime

Date: 2026-08-24 (Asia/Shanghai)

## Round contract

Primary goal: add a result-blind, runtime-only performance envelope and a single
power-limit watchdog around the existing singular P3 service.

Governance:

- Research Request 657 / Reviewer Decision 2766.
- Engineering Request 658 / Reviewer Decision 2769 / Execution 534.
- Acceptance-closure Engineering Request 659 / Reviewer Decision 2774 /
  Execution 535.
- Frozen P3 source artifact `139ddc97ce1d81ea4e6182359f8391532ed1911090db004bcdf9ebcdea5f9493`.
- Frozen P3 source set `a3b34318d784d9477fe82f7e66c3c04e5640eaed87e2b4c49cd8b397fc27cd9c`.
- Starting mainline commit `e3e1730da18b49b174bde3fea240c37b496a820f`.

Non-goals: no estimator, features, threshold, interim looks, candidate semantics,
baseline, blue strategy, P4 logic, P5, Promotion, result read, or scientific
execution change.

## Live baseline

- CPU: Intel Core Ultra 7 155H, 16 physical cores / 22 logical CPUs.
- Topology: six SMT P-cores on logical CPUs 0-11, eight E-cores on 12-19,
  two LP-E cores on 20-21.
- Memory: 30 GiB RAM and 8 GiB swap.
- BLAS: NumPy 2.4.6, scipy-openblas 0.3.31.188.0, 64-bit integer ABI,
  Haswell dynamic architecture, maximum 64 threads.
- Power readback before changes: MSR PL1 40 W, MMIO PL1 20 W,
  MSR PL2 55 W, MMIO PL2 43 W.
- Platform profile: `performance`.
- Supported reversible voltage-offset interface: none found. Voltage offset is
  therefore `NONE`; no raw voltage register was accessed.

The old `dehps-p26-mmio-pl1-guard.service` was found and its proven privileged
Docker sysfs write pattern was adopted. The new unit replaces that guard during
Operator deployment; the two may not run together.

Phase-0 also found an unrelated runtime integration defect: the current P3
service could not import the exact successor `2026097:DRAW_SYNCED` external
event because the historical bounded validator rejected the new canonical event
prefix. The additive repository repair accepts only three exact P3 runtime
transitions: the registered draw event, one Ready-to-Running state transition,
or the next five frozen issue tasks after registered settlement replay. It
rejects mixed deltas, scientific changes, additional facts, and non-P3 changes.

## Frozen reference equivalence

The registered 2026097 preregistration, dataset, model, candidate set, random
baseline, checkpoint, report and replay were recomputed without target-result
access. Exact equality passed for all artifact bodies and digests, including:

- probability vector length 33 and sum 6.0;
- Top100 digest `1f1e8e429e09d00cf9dddefbc624b0c4d9e1b42c52be40b082803728d01e754e`;
- baseline digest `b70c6f48e3588c03591c27f692ef9077c03c6a32a7404051aa02d221f17a582e`;
- checkpoint digest `1b448f9090feed24c64aff5ad0bcdb40281c0df5372347345bf4b91a4b9e137c`;
- replay digest `72b6ddedb727777d07986b8dbb14ac8ef084d3ac464d3575fc16257bc2063645`;
- configuration drift `false`.

## Concurrency and affinity benchmark

Every configuration had one warm-up and at least five measured cold-process
runs. A less-than-2% near tie is extended to nine measurements for both
finalists in alternating order. All configurations reproduced the exact frozen
outputs. The selection endpoint is the frozen workload's internal
`refit -> candidate -> replay` end-to-end timer, not process startup or batch
throughput.

Outer batch throughput results (inner threads = 1, all CPUs):

| Outer | Median workloads/s | Median one-workload seconds | Peak aggregate RSS KiB |
|---:|---:|---:|---:|
| 1 | 0.7837 | 0.0879 | 275,820 |
| 2 | 1.3574 | 0.0995 | 552,208 |
| 4 | 2.2907 | 0.1174 | 1,103,936 |
| 6 | 2.5527 | 0.1495 | 1,654,964 |
| 8 | 2.4281 | 0.1658 | 2,207,772 |
| 12 | 2.8814 | 0.1685 | 3,310,868 |
| 22 | 3.1881 | 0.4838 | 6,079,392 |

Outer 22 is the highest duplicate-batch throughput, but it has no deployment
credit: P3 has one canonical issue workload and one completion path, so running
duplicates would compete to publish the same prediction. The frozen task remains
singular and selected outer workers is 1.

The acceptance-closure search covered outer 1/2/4/6/8/12/22, uniform inner
1/2/4/6/8/12/22, hybrids 2x2/4x2/6x2/8x2/2x4/4x4, and five affinities.
With the final explicit uniform-one thread environment, affinity medians were:

| Affinity | CPUs | Median frozen end-to-end seconds | Median cold-process wall seconds |
|---|---|---:|---:|
| all | 0-21 | 0.0879 | 1.2760 |
| P + E, no LP-E | 0-19 | 0.0987 | 1.4365 |
| P physical | 0,1,3,6,8,10 | 0.0989 | 1.4117 |
| P physical + E | 0,1,3,6,8,10,12-19 | 0.0995 | 1.4370 |
| P logical | 0-11 | 0.1063 | 1.4937 |

Selection uses the frozen end-to-end endpoint. Selected configuration is
outer 1, inner 1, all logical CPUs, with the explicit deployment profile
`OMP=1`, `OPENBLAS=1`, `MKL=1`, `NUMEXPR=1`. Its five-run medians and telemetry
were:

| Field | Value |
|---|---:|
| refit median | 0.022458 s |
| candidate median | 0.062651 s |
| replay median | 0.001104 s |
| frozen workload end-to-end median | 0.087912 s |
| cold-process wall median | 1.275953 s |
| mean CPU busy | 5.42% |
| mean busy frequency | 3897 MHz |
| peak package power | 22.43 W |
| peak package temperature | 82 C |
| peak RSS | 275,820 KiB |
| thermal-throttle time delta | 0 ms |

The earlier complete-process-wall comparison remains diagnostic only and has no
selection credit. The 20 W versus 28 W MMIO winner and the deployment speedup
remain Operator measurements. Their trials are counterbalanced by alternating
`20,28` and `28,20`; a less-than-2% tie extends both profiles to nine samples.
The winner must be stable, exact-output equivalent, and fastest on this same
frozen end-to-end endpoint.

## Runtime design

The watchdog uses read -> compare -> write only on drift -> readback. Active
cadence is 2 seconds and passive WAIT_FORWARD cadence is 60 seconds. Its state
records timestamps; exact MSR/MMIO PL1 and PL2 targets and readbacks; package
power, busy frequency and package temperature while active; mode, heartbeat,
reapply count, last reapply, and stale-active recovery. PL2 remains monitor-only
at MSR 55 W / MMIO 43 W and fails closed on drift. A stale active mode after
reboot becomes passive unless the P3 unit is active/activating/deactivating.

The Operator-only real drift fixture first aligns the selected profile, changes
both MSR and MMIO PL1 to different legal values, activates the real watchdog
reconciliation path, requires exactly two corrective writes and exact readback,
and restores the selected profile plus passive mode in `finally`. It cannot
dispatch P3 or persist a scientific artifact.

The P3 drop-in adds only environment, affinity, `ExecStartPre=enter`, and
`ExecStopPost=exit`; it does not replace the original P3 `ExecStart`. Restarting
the watchdog cannot dispatch P3 or create a model/checkpoint. Thermal shutdown,
PROCHOT, current protection, voltage protection and firmware emergency controls
are untouched.

## Engineering validation checkpoint

- Runtime focused tests after the acceptance closure: 15 passed, including
  exact alternating-order, near-tie extension, active telemetry/PL2 and real
  drift/reapply/restore regression coverage.
- Exact repository transition tests: 6 passed.
- Full P3/P4/repository compatibility run: 191 passed and 5 skipped. Three
  initial failures were audited: two historical recovery tests needed isolation
  from the new read-only P3 preflight and were corrected; the remaining failure
  is the historical bounded-lineage source sentinel correctly observing that
  this explicitly authorized repository repair changes `repository.py` bytes.
  Its frozen source identity was not rewritten or falsely resealed.
- Post-correction P3/runtime/repository run, excluding only that historical
  sentinel: 135 passed, 5 skipped, 1 deliberately deselected.
- Final P3/P4/runtime compatibility subset: 77 passed, with only the same
  historical bounded-lineage source sentinel deliberately deselected.
- Current successor P3 source binding: all seven source entries match their
  frozen byte counts and SHA-256 values; source artifact and source-set digests
  remain exact.
- Python compilation: passed.
- Ruff: passed.
- Git diff check and exact three-file Request-659 boundary: passed; the
  repository, Supervisor, P3/P4 sources and systemd files are byte-identical to
  merged mainline.
- systemd verification: passed for the new unit/drop-in; the only warning was
  an unrelated installed `spice-vdagent.service` key.
- Acceptance-closure matrix: 23 configurations, all exact-output equivalent;
  selected outer 1 / inner 1 / all CPUs / uniform-one environment by the frozen
  workload end-to-end endpoint.
- Production power writes, 20 W versus 28 W MMIO profile selection, drift
  injection, service/reboot recovery and soak remain Operator-only and were not
  performed in Engineering Executions 534 or 535.

Integration matrix at this checkpoint:

| Link | State |
|---|---|
| Goal -> runtime contract -> approved Engineering | complete |
| Frozen reference -> exact output replay | complete |
| Concurrency/threads/affinity -> frozen-endpoint selected runtime profile | complete |
| Counterbalanced power selection / real drift fixture | code complete |
| P3 lifecycle -> watchdog enter/exit wiring | code complete |
| Operator deployment -> drift/readback/soak/recovery | pending Operator Request |

Mainline integration answer at this checkpoint:
`NO — INTEGRATION_PENDING` until merged-main Operator deployment and recovery
validation complete.
