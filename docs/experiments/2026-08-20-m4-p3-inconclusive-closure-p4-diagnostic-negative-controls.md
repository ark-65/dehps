# M4-P3 Inconclusive Closure and P4 Diagnostic Negative Controls

## Round contract

- Primary goal: preserve the formal inconclusive P3 closure and execute a
  separate, diagnostic-only P4 negative-control chain.
- Non-goals: predictive P3, confirmatory P4, P5, Promotion, new models, new
  features, hyperparameter search, forward samples, and production numbers.
- Canonical goal: `M4_P4_DIAGNOSTIC_NEGATIVE_CONTROLS`.
- Formal P4 task: `m4-p4-negative-controls-and-robustness`, unchanged and still
  dependent on a formal `PASS_TO_P4` fact.

## Result-blind preregistration

The Research Agent request was approved before any registered negative-control
result was read. The frozen contract binds the historical dataset, evaluator
source, 2,581 historical folds, primary endpoint, six controls, deterministic
PCG64 seeds, 64 randomized repetitions, a 2,000-replicate moving-block
bootstrap, Holm family-wise correction, and the decision priority.

The six frozen controls are:

1. `DATE_PERMUTATION`
2. `TARGET_LABEL_PERMUTATION`
3. `NUMBER_RELABELING`
4. `FEATURE_TIME_SHIFT`
5. `RANDOM_FEATURE_SENTINEL`
6. `BASELINE_IMPLEMENTATION_SENTINEL`

Randomized repetitions are Monte Carlo precision only. They do not increase
the 2,581 independent historical folds and cannot repair the P3 power deficit.

## P3 closure preserved

- Scientific disposition: `INCONCLUSIVE_DUE_TO_POWER`.
- Governance status: `CLOSED_NOT_AUTHORIZED_AFTER_DEEPER_VALIDATION`.
- Existing folds: 2,581.
- Required folds: 4,676.
- Missing independent folds: 2,095.
- Independent holdout: unavailable.
- Deeper Validation decision: `FORWARD_EVIDENCE_REQUIRED`.
- `PASS_TO_P4`: not emitted.

## Mainline acceptance matrix

| Link | Required proof | Status |
| --- | --- | --- |
| Goal | Separate diagnostic-only goal | Complete |
| Resolver | Formal P4 remains dependency-wait | Verified |
| Ready Queue | Six diagnostic tasks become ready sequentially | Verified; final queue empty |
| Supervisor | Frozen capability runner | Validated in merged main |
| Capability | Six controls, Evidence Compiler, typed decision | Complete |
| Artifacts | Closure, preregistration, execution, evidence, decision, replay | Registered |
| Status | Diagnostic status without P3/P4 promotion | `COMPLETE` |
| Next Task | Forward evidence or evaluator/leakage repair only | `FORWARD_EVIDENCE_REQUIRED` |

Mainline integration answer:
`YES — validated by unified mainline execution and replay`.

## Validation record

Focused synthetic tests verify the frozen source contract, P3 closure, all six
control paths, unique-fold accounting, decision priority, registered replay,
and the independent diagnostic Goal. The result-blind preregistration was
registered before the historical negative-control execution began.

- Ruff: passed on the changed Python surface.
- Focused diagnostic tests: 6 passed.
- Research OS compatibility regression: 153 passed, 5 skipped.
- GitHub Actions: job did not start because account payment/spending-limit
  runner allocation was unavailable; PR #359 was squash-merged under the
  repository's exhausted-CI-quota rule after local validation.
- Unified mainline commit:
  `b3b905aa3cbf9ee39f88d07f559d9159c4b58a42`.
- Final manifest:
  `7fedbd48cc7b1f27d7c5868720d167d707f796e84447f569ee1a2f80c92f0e78`.
- Final snapshot:
  `1c3c21cb92e634f4162a2784079f0c5d411e45abc12acd864ef30a7df05fd1d2`.

## Final result

Typed decision: `NEGATIVE_CONTROLS_CLEAN`.

All six controls completed on the 2,581 frozen historical folds. The 64
randomized repetitions per randomized control remain Monte Carlo precision,
not additional independent information. No frozen signal-destruction control
retained a positive advantage:

| Control | Registered result |
| --- | --- |
| `DATE_PERMUTATION` | mean -0.007846 bits/issue; Holm p=1.0; positive gate false |
| `TARGET_LABEL_PERMUTATION` | mean -0.000539 bits/issue; Holm p=1.0; positive gate false |
| `NUMBER_RELABELING` | equivariance passed; maximum score difference 2.22e-16 |
| `FEATURE_TIME_SHIFT` | past-shift mean -0.008160; Holm p=1.0; future sentinel rejected 2,581/2,581 attempts before reading values |
| `RANDOM_FEATURE_SENTINEL` | mean -0.016077 bits/issue; Holm p=1.0; positive gate false |
| `BASELINE_IMPLEMENTATION_SENTINEL` | independent implementation passed; maximum difference 0.0 |

This means only that the frozen historical pipeline showed no obvious leakage,
number-encoding artifact, evaluator hallucination, time-availability violation,
or systematically degraded null baseline under the preregistered controls. It
is not predictive evidence and does not repair P3's power deficit.

Registered artifact identities:

- Execution:
  `8d17fc0fba0a29d7ae8eef50d228d31af920c3d770f6095db8ca2448147448c7`.
- Evidence:
  `c54ad7b645a189a5cde6e1770baed08f59805e0a935cb2eb684e5fc33e7afc10`.
- Decision:
  `f3f019e82b4391cbbbda88a11a6c1fc0373050a67a67d164ed65432c232ab56d`.
- Decision registration:
  `9855b6a2ab51428c6dd73a3ae39910b75aa3eb88e10d32fa675b801241323e46`.
- Typed replay:
  `5767580c5072d3c73cb4d04f67f7b17a4c92d4d199c56ef405b558a5d50b9daa`.

All six generic Supervisor replays returned `REPLAY_VERIFIED` with identical
execution and artifact identities. The typed replay returned
`REGISTERED_REPLAY_VERIFIED` without rerunning the workload.

## Terminal state

```text
P3 SCIENTIFIC DISPOSITION:
INCONCLUSIVE_DUE_TO_POWER

P3 GOVERNANCE STATUS:
CLOSED_NOT_AUTHORIZED_AFTER_DEEPER_VALIDATION

PASS_TO_P4:
NOT_EMITTED

DIAGNOSTIC P4:
COMPLETE

DIAGNOSTIC P4 DECISION:
NEGATIVE_CONTROLS_CLEAN

FORMAL P4:
DEPENDENCY_WAIT

P5:
NOT_AUTHORIZED

PROMOTION:
NOT_TRIGGERED

MODEL TRAINING:
NOT_STARTED

NEW MODEL:
NONE

NEXT LEGAL SCIENTIFIC TASK:
FORWARD_EVIDENCE_REQUIRED
```
