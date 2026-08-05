# P2.6.1 current-host RAPL limit trial — Round 14

Date: 2026-08-05
Role: Operator
Request: `operator-current-host-rapl-28w-round-14-20260805`
Execution: `192`

## Primary goal

Determine whether raising the current host's effective CPU package long-term
power limit can materially accelerate the live exact P2.6.1 workload without
changing its scientific contract, execution identity, worker count, or
artifacts.

## Non-goals

- No firmware-limit bypass, undervolting, overclocking, governor change, or
  worker-count change.
- No training-service restart.
- No algorithm, strategy, statistical target, or evidence decision change.
- No statistical result payload inspection.

## Ready and safety conditions

- The live user service must remain active with PID `2364013`, invocation ID
  `2ba05ff3b4d043e5951921326def4dd7`, and zero restarts.
- The MMIO RAPL limit may only move from the verified 20 W baseline to the
  platform-advertised maximum of 28 W. The requested 30 W exceeds the kernel's
  advertised 28 W maximum and was therefore not attempted.
- Roll back to 20 W on instability, a temperature of 100 C or higher, identity
  drift, or failure to improve live result-blind throughput.

## Observations

The initial hardware inspection found two package RAPL views. The MSR long-term
limit was already 40 W, while the lower MMIO long-term limit was 20 W. The MMIO
interface advertised 28 W as its maximum; PL2 remained 43 W throughout.

| Window | MMIO PL1 | Elapsed | Mean sampled frequency | Maximum sampled frequency | Maximum core temperature | Advanced fold entries | Fold rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Pre-change baseline | 20 W | 31.10 s | 729 MHz | 900 MHz | 84 C | 489 | 15.72/s |
| Initial post-change | 28 W | 30.75 s | 553 MHz | 3,100 MHz | 85 C | 247 | 8.03/s |
| Extended post-change | 28 W | 121.78 s | 896 MHz | 3,600 MHz | 85 C | 1,018 | 8.36/s |
| Same-stage reverse control | 20 W | 121.48 s | 856 MHz | 3,433 MHz | 85 C | 1,162 | 9.57/s |

Root-level `turbostat` sampling during the 28 W window observed approximately
19.09-22.73 W package power, 628-966 MHz busy frequency, and 83-85 C package
temperature. Raising the configured limit did not make the package sustain
28 W.

The same-stage reverse control was the decision sample because fold complexity
changes over time. Restoring 20 W improved the observed rate from 8.36/s to
9.57/s despite occurring later in the workload. That is a 14.4% improvement
relative to the 28 W window, or equivalently a 12.6% regression for the 28 W
candidate relative to the restored 20 W control. Short-window rates remain
operational observations rather than statistical performance claims.

## Decision

Reject the 28 W candidate and keep the MMIO long-term limit at 20 W. No
persistent boot-time unit was installed. Final readback was:

- MMIO PL1: 20 W
- advertised MMIO PL1 maximum: 28 W
- MMIO PL2: 43 W
- package temperature: 81 C

The live supervisor remained active with the same PID and invocation ID and
with `NRestarts=0`. The low all-core frequency is therefore not resolved by
raising this RAPL limit; further diagnosis should focus on platform/EC current
or thermal policy and workload behavior rather than assuming PL1 starvation.

## Integration matrix

| Link | Evidence |
| --- | --- |
| Goal | Bounded result-blind current-host power-limit trial |
| Resolver | Approved typed Operator request #271 |
| Ready Queue | Execution #192 authorized with 20 W rollback guard |
| Supervisor | Existing unified supervisor stayed active and unchanged |
| Capability | Transient MMIO PL1 20 W -> 28 W -> 20 W |
| Artifacts | This report plus immutable Agent Request execution record |
| Status | Candidate rejected; original production state restored |
| Decision consumer | Do not persist 28 W; diagnose another limiting mechanism |
| Replay | Readback and reverse-control measurement proved rollback |

Mainline integration answer: **YES — validated by unified mainline execution and replay.**
