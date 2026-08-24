# M4-P3 persistent high-performance runtime

Date: 2026-08-24 (Asia/Shanghai)

## Round contract

Primary goal: add a result-blind, runtime-only performance envelope and a single
power-limit watchdog around the existing singular P3 service.

Governance:

- Research Request 657 / Reviewer Decision 2766.
- Engineering Request 658 / Reviewer Decision 2769 / Execution 534.
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
runs. Near-tie candidates received 9 or 20 measured runs. All configurations
reproduced the exact frozen outputs.

Outer batch throughput results (inner threads = 1, all CPUs):

| Outer | Median workloads/s | Median one-workload seconds | Peak aggregate RSS KiB |
|---:|---:|---:|---:|
| 1 | 0.7566 | 0.0915 | 274,920 |
| 2 | 1.3493 | 0.1014 | 549,752 |
| 4 | 2.0449 | 0.1294 | 1,099,920 |
| 6 | 2.5136 | 0.1580 | 1,651,548 |
| 8 | 2.4582 | 0.1653 | 2,198,844 |
| 12 | 2.9458 | 0.1671 | 3,297,232 |
| 22 | 3.2102 | 0.4946 | 6,051,124 |

Outer 22 is the highest duplicate-batch throughput, but it has no deployment
credit: P3 has one canonical issue workload and one completion path, so running
duplicates would compete to publish the same prediction. The frozen task remains
singular and selected outer workers is 1.

The complete search covered outer 1/2/4/6/8/12/22, uniform inner
1/2/4/6/8/12/22, hybrids 2x2/4x2/6x2/8x2/2x4/4x4, and five affinities.
With the final explicit uniform-one thread profile, affinity medians were:

| Affinity | CPUs | Median cold-process wall seconds |
|---|---|---:|
| all | 0-21 | 1.4035 (20-run confirmation) |
| P + E, no LP-E | 0-19 | 1.4188 |
| P physical | 0,1,3,6,8,10 | 1.4289 |
| P physical + E | 0,1,3,6,8,10,12-19 | 1.4516 |
| P logical | 0-11 | 1.4816 |

Selection uses complete cold-process median wall clock. Selected affinity is all
logical CPUs and the selected explicit thread profile is `OMP=1`, `OPENBLAS=1`,
`MKL=1`, `NUMEXPR=1`. In 20-run cold-process comparison, the prior implicit
environment and selected profile measured:

| Phase | Prior seconds | Selected seconds |
|---|---:|---:|
| refit | 0.02411 | 0.02554 |
| candidate | 0.06736 | 0.07094 |
| replay | 0.00119 | 0.00125 |
| pure workload end-to-end | 0.09451 | 0.09982 |
| complete cold-process wall | 1.41391 | 1.40345 |

Overall complete-cycle median speedup was 1.007x. The phase-only computation is
slightly slower, but the required full wall-clock selection is faster; no larger
speedup is claimed. Selected telemetry across 20 runs was mean CPU Busy 5.37%,
peak Busy 7.74%, mean busy frequency 3549 MHz, peak package power 24.44 W, peak
package temperature 82 C, peak RSS 275,488 KiB, and zero recorded
thermal-throttle time. Selection was based on median wall clock, not utilization
or configured wattage.

## Runtime design

The watchdog uses read -> compare -> write only on drift -> readback. Active
cadence is 2 seconds and passive WAIT_FORWARD cadence is 60 seconds. Its state
records both MSR/MMIO PL1, both PL2 readbacks, mode, heartbeat, reapply count,
last reapply, and stale-active recovery. A stale active mode after reboot becomes
passive unless the P3 unit is active/activating/deactivating.

The P3 drop-in adds only environment, affinity, `ExecStartPre=enter`, and
`ExecStopPost=exit`; it does not replace the original P3 `ExecStart`. Restarting
the watchdog cannot dispatch P3 or create a model/checkpoint. Thermal shutdown,
PROCHOT, current protection, voltage protection and firmware emergency controls
are untouched.

## Engineering validation checkpoint

- Runtime focused tests: 12 passed.
- Exact repository transition tests: 6 passed.
- Full P3/P4/repository compatibility run: 191 passed and 5 skipped. Three
  initial failures were audited: two historical recovery tests needed isolation
  from the new read-only P3 preflight and were corrected; the remaining failure
  is the historical bounded-lineage source sentinel correctly observing that
  this explicitly authorized repository repair changes `repository.py` bytes.
  Its frozen source identity was not rewritten or falsely resealed.
- Post-correction P3/runtime/repository run, excluding only that historical
  sentinel: 135 passed, 5 skipped, 1 deliberately deselected.
- Current successor P3 source binding: all seven source entries match their
  frozen byte counts and SHA-256 values; source artifact and source-set digests
  remain exact.
- Python compilation: passed.
- Ruff: passed.
- systemd verification: passed for the new unit/drop-in; the only warning was
  an unrelated installed `spice-vdagent.service` key.
- Production power writes, 20 W versus 28 W MMIO profile selection, drift
  injection, service/reboot recovery and soak remain Operator-only and were not
  performed in Engineering Execution 534.

Integration matrix at this checkpoint:

| Link | State |
|---|---|
| Goal -> runtime contract -> approved Engineering | complete |
| Frozen reference -> exact output replay | complete |
| Concurrency/threads/affinity -> selected runtime profile | complete |
| P3 lifecycle -> watchdog enter/exit wiring | code complete |
| Operator deployment -> drift/readback/soak/recovery | pending Operator Request |

Mainline integration answer at this checkpoint:
`NO — INTEGRATION_PENDING` until merged-main Operator deployment and recovery
validation complete.
