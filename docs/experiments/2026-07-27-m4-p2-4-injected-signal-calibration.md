# M4-P2.4 Injected Signal Calibration

## Round contract

Primary goal: implement the frozen injected-signal generators and exact
calibration kernel, run four descriptive P2.3/P2.2 smoke paths, and integrate
the capability into the unified Research Evidence Supervisor.

Non-goals: bootstrap, permutation, formal false-positive or power runs, MDE,
PE2 finalization, real-history analysis, production checkpoints, evidence
promotion, or any change to the practical-null threshold.

The contract audit found that preregistration v1.0.2 did not contain an
executable information binding or numerical acceptance tolerances. The
preceding repair round froze preregistration v1.0.3
(`4fff51c58e4a46d664e414bfe4cc0d7269c8e3712734153faec548648144d0d9`)
and synthetic manifest v1.0.1
(`f84c2da3565f7eda41c3782517c78211805f57ea8f3bfd00659a93c380826a3c`).
This round consumes those repaired identities and does not reinterpret the
original ambiguous contract.

## Frozen inputs

- Decision policy:
  `824f91d5d012caed9c7a273c7a3fb9fcf1b6c3fb6a4f0465707441c7c261790d`
- Metric Kernel:
  `56b9d0a62d43d167069e5222c7095383c9c5106bb3361b0b1def75cf2b6c86a2`
- Walk-forward Harness:
  `177a3d591b7557a4231a276bfb007f0d42a94d942824403f5376f94fe904d2ca`
- Calibration run manifest:
  `f30186e3f5aeefb07565d25c4e0de68d955a07e87d1894fdaedbe8bedf4a2317`
- Information binding: joint draw information
  `I(S_t;Y_{t+1})`, measured in bits per issue over the exact legal
  `C(33,6) = 1,107,568` sample space.
- Requested strengths: `0.001`, `0.01`, and `0.05` bits/issue.
- Solver: deterministic bisection after a 65-point monotonicity/bracket audit.
- Acceptance: absolute error at most `1e-10` bits/issue and relative error at
  most `1e-6`.
- Independent audit: Monte Carlo standard error at most `0.00025`
  bits/issue and agreement within four standard errors.

## Mechanisms and truth

IS1 uses an exact contains/excludes-number-1 legal-space mixture. IS2 uses
the two equal lexicographic halves of the legal draw space as a local temporal
state. IS3 uses the pair event `{(1,2),(3,4)}` and reports number-level
marginal leakage separately from pair information. IS4 uses an exact
hypergeometric construction whose perturbation weights preserve every
unconditional and conditional number marginal.

All 12 frozen scenarios converged. The maximum absolute calibration error was
`8.796547518175046e-11` bits/issue and the maximum relative error was
`8.35004643554016e-08`. All probability normalization, null-limit,
monotonicity, legal-draw, and independent Monte Carlo checks passed.

The weak IS3 scenario qualified as `PAIR_DOMINANT`; medium and strong IS3
were explicitly classified
`PAIR_CONDITIONAL_WITH_MARGINAL_LEAKAGE`. No pair-only claim is made for
those two scenarios. IS4's maximum conditional and unconditional marginal
deviation was exactly zero under the frozen analytic construction.

## Boundary and seed audit

Calibration datasets carry all five immutable flags:

```text
CALIBRATION_ONLY
NOT_EVALUATION_DATA
NOT_POWER_DATA
NOT_FALSE_POSITIVE_DATA
NOT_P2_GATE_EVIDENCE
```

The P2.3 loader rejects a missing truth digest, changed flags, use of the
evaluation seed domain, or any evaluation/power/FPR/Gate eligibility. All
calibration seeds are derived from `M4_P2_CALIBRATION`; wall-clock seeds and
best-seed selection are forbidden, while retry, resume, and sharding preserve
the child seed identity.

## Local end-to-end acceptance

The calibration Runner generated 12 truth artifacts, four calibration-only
datasets, four Walk-forward run artifacts, and eight completed folds. Each
mechanism smoke used the frozen P2.3 timestamp guard and P2.2 Metric Kernel.
The second execution against the same output directory produced the same
artifact graph with no immutable collisions.

The local acceptance execution used an intentionally synthetic execution
identity and is not the formal mainline record:

- Calibration artifact:
  `25a9277dce75f807396caf18bfc8d5c2228947501886b825b93a79b1bfd64be3`
- Completion artifact:
  `5f4110234f8f4f8443e597fc133a833eeb9d35d962cd2e9eb6be42d4ba410002`
- Registered child paths: `58`
- Completed folds: `8`
- Evidence eligibility: `false`

The Supervisor integration test additionally proved the canonical transition
`P2.4 Ready -> dispatch -> VALIDATED_IN_MAINLINE -> P2.5 Ready`, followed by
an exactly-once replay and a heartbeat with no duplicate P2.4 execution.
Formal PostgreSQL execution identities and the final control-plane snapshot
are recorded by the post-merge operator run rather than fabricated here.

## Validation

- Focused P2.4, mainline, and status tests: `45 passed`.
- Worker: `1817 passed, 4 skipped`.
- API: `117 passed`.
- Web: `19 passed`.
- Web build: passed.
- Engineering progress after formal completion: `34%`.
- Evidence progress: `0%`.
- Promotion Gate: closed.
- Adaptive training: stopped.
- Legacy training mainline: frozen.

## Scope audit

No bootstrap or permutation was implemented. No formal power, false-positive,
MDE, PE2, real-history, or production-checkpoint operation was run. Signal
strengths, practical-null, Evidence Progress, and promotion authority were not
changed.
