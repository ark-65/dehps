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
| Goal | Separate diagnostic-only goal | Implemented |
| Resolver | Formal P4 remains dependency-wait | Pending merged-main verification |
| Ready Queue | Six diagnostic tasks become ready sequentially | Pending merged-main execution |
| Supervisor | Frozen capability runner | Implemented |
| Capability | Six controls, Evidence Compiler, typed decision | Implemented |
| Artifacts | Closure, preregistration, execution, evidence, decision, replay | Pending registered execution |
| Status | Diagnostic status without P3/P4 promotion | Pending registered execution |
| Next Task | Forward evidence or evaluator/leakage repair only | Pending typed decision |

Mainline integration answer: `NO — INTEGRATION_PENDING` until merged-main
execution and registered replay complete.

## Validation record

Focused synthetic tests verify the frozen source contract, P3 closure, all six
control paths, unique-fold accounting, decision priority, registered replay,
and the independent diagnostic Goal. Real historical negative-control results
are intentionally deferred until the preregistration artifact is registered by
the unified mainline.

## Final result

Pending merged-main diagnostic execution. This section will be replaced with
the typed decision, artifact identities, replay evidence, and final integration
matrix after the registered run.
