# M4-P2.6 Measurement-Validation Contract Freeze

## Round contract

- Primary goal: resolve the fail-closed P2.6 numeric and decision-contract gap
  before any formal false-positive, power, bias, RMSE, coverage, or MDE result
  exists.
- Role: Engineering Agent implementing approved Research request
  `research-m4-p2-6-measurement-validation-contract-20260727`.
- Engineering authorization:
  `engineering-m4-p2-6-contract-freeze-20260727`.
- Baseline commit:
  `d26d3053defee8bba831af0394a214421a672f18`.
- Formal P2.6 executions in this round: zero.
- Evidence Progress in this round: zero.

Non-goals: no P2.6 capability, no synthetic replicate, no P2.7 decision, no
real-history analysis, no P2.1-P2.5 artifact change, and no production or
Promotion action.

## Why the repair was required

The canonical P2.6 Task contained:

```text
coverage_tolerance = fail_closed_pending_frozen_numeric_contract
```

The accepted contracts also named PE2 without an executable estimator,
required BCa when valid without defining validity or fallback, listed MDE
outputs without an estimator, and did not represent `PASS_TO_P3` and
`REPAIR_MEASUREMENT_SYSTEM` as mutually exclusive dependency facts. P2.6
could not legally fill those values from implementation defaults.

The repair was frozen before any P2.6 dataset or result. It does not supersede
P2.1-P2.5; it references their accepted digests as immutable upstream
identities.

## Frozen identity and workload

The P2.6/P2.7 measurement-validation manifest digest is:

```text
953ae76e2e28523b7d067c2b73dac8bec63ff2417db283fd516fe900e52402f8
```

It preserves the full P2.1 planned workload:

| Scale | Outer issues | Scenarios | Replicates per scenario |
| --- | ---: | ---: | ---: |
| `FORWARD_61` | 61 | 13 | 1,000 |
| `HISTORICAL` | 2,581 | 13 | 1,000 |
| `LONG` | 6,062 | 5 | 1,000 |

Total identities remain 31,000 scenario-replicates and 64,656,000 outer issue
predictions per probe. All four frozen probes must be reported; regularized
logistic regression remains the Gate probe. Missing, failed, duplicate, or
partially pooled cells fail closed.

## Estimator and interval contract

- PE1 is the arithmetic mean of P2.2 per-issue theoretical-baseline minus
  probe log-loss gain, in bits per issue.
- The null center is the mean of the complete 2,000-replicate P2.5
  block-permutation PE1 distribution for the same immutable replicate.
- PE2 is `PE1 - permutation_null_center`.
- Synthetic bias and RMSE compare PE2 with the P2.4 exact joint-draw
  information truth. RMSE is mandatory and must be finite, but no result-driven
  numeric RMSE threshold is invented.
- Absolute estimator bias remains capped at the preregistered
  `0.0025 bits/issue`.
- The primary interval is a 2,000-replicate moving-block BCa interval with
  primary block size five and a frozen delete-one-contiguous-block jackknife.
- BCa validity has four explicit numerical conditions. Failure falls back to
  the two-sided Type-7 percentile interval and must record the failed
  condition; silent fallback is forbidden.
- Primary PE2 empirical 95% coverage must lie in `[0.925, 0.975]` in every
  executed injected-signal cell. PE1 coverage is reported but is not a Gate.

## Detection, false-positive, power, and MDE contract

A replicate is detected only when both PE1 and PE2:

1. pass upper-tail plus-one permutation inference after Holm correction over
   the two-endpoint primary family; and
2. have a 95% interval lower bound above zero.

No one-endpoint override is legal.

At every scheduled null scale, the final decision false-positive rate must be
at most `0.075`, and its 95% Wilson upper bound must be at most `0.09`.

Power is cell-local:

- `0.001 bits/issue`: mandatory report, no pass threshold;
- `0.01 bits/issue`: at least `0.80` in every scheduled mechanism × scale
  cell;
- `0.05 bits/issue`: at least `0.95` in every scheduled mechanism × scale
  cell.

Mechanism or scale averaging is forbidden.

MDE is deliberately conservative. Only the executed strengths
`0.001 / 0.01 / 0.05` may be used. Interpolation is forbidden. Each cell
reports the smallest tested strength reaching 80% power or `>0.05`; the
decision-policy MDE at 61 outer issues is the worst of the four mechanism
upper bounds. Required issue count uses only the executed grid
`61 / 2581 / 6062`.

## Automatic branch

P2.7 may emit exactly one fact:

```text
m4-p2-measurement-decision:PASS_TO_P3
```

or:

```text
m4-p2-measurement-decision:REPAIR_MEASUREMENT_SYSTEM
```

The control-plane loader rejects coexistence. P3 now requires the explicit
PASS fact as well as completed P2. The repair Task requires the explicit
REPAIR fact. Without either fact, both branches remain closed.

## Gauss–Riemann cross-review

Historical boundary: these are historically grounded reasoning lenses, not
literal minds; Wilson, Holm, BCa, simulation power, and deterministic software
replay are later methods.

Gauss pass:

- strongest claim: without numeric coverage, PE2, detection, and denominator
  definitions, FPR and power are undefined;
- weakest assumption: three effect sizes and three sample scales support only
  discrete conservative MDE brackets;
- cross-test: every reported denominator and seed set must match the immutable
  workload exactly.

Riemann pass:

- strongest claim: the object is the full scale × mechanism × strength
  response surface, not a pooled scalar;
- weakest assumption: the frozen grid sparsely samples that surface;
- cross-test: no locally failed pair, temporal, single-number, or
  marginal-preserving cell may be hidden by another cell.

Disagreement was about scope: the old preregistration explicitly gates the
practical signal, while the user also required failed strong-signal cells to
block passage. The result-blind resolution freezes a 95% strong-cell power
Gate. The smallest shared conclusion is cellwise, fail-closed validation with
conservative grid MDE and no result-driven threshold.

## Validation

Focused contract, mutation, Ready Queue, branch, and Supervisor tests:

```text
72 passed
```

The focused suite verifies:

- immutable digest and accepted upstream identities;
- exact 31,000-replicate / 64,656,000-outer-prediction workload;
- rejection of recomputed-digest threshold mutations;
- P2.6 as the sole Ready Task after a completed P2.5 runtime overlay;
- P3 inaccessible without PASS;
- repair inaccessible without REPAIR;
- mutual exclusion of PASS and REPAIR.

Repository-wide Worker, API, Web, build, GitHub CI, ready-PR merge, and fresh
Supervisor synchronization are recorded after they complete.

Local repository-wide validation:

- Worker: `1854 passed, 4 skipped`;
- API: `117 passed`;
- Web: `19 passed`;
- Angular production build: passed.

## Training-mainline integration matrix

| Link | Contract-round state |
| --- | --- |
| Goal | `M4_INFORMATION_THEORY_EVIDENCE` |
| Resolver | P2.6 binds the new artifact fact |
| Ready Queue | P2.6 is uniquely Ready after the accepted P2.5 overlay |
| Supervisor | capability intentionally absent in this contract-only round |
| Capability | `INTEGRATION_PENDING` |
| Artifacts | immutable contract source only; no P2.6 result |
| Status | Engineering 37%, Evidence 0% |
| Next Task | P2.6 implementation and unified execution |

Final integration answer for this contract-only round:

```text
NO — INTEGRATION_PENDING
```

The contract becomes consumed and validated only when the P2.6 capability uses
this exact digest in the unified mainline execution and deterministic replay.
