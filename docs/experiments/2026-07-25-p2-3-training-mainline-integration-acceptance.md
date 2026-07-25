# P2.3 Training Mainline Integration Acceptance

Date: 2026-07-25

Primary role: Engineering Agent (reporting only)

Implementation PR: [#221](https://github.com/ark-65/dehps/pull/221)

Merged commit: `37cfd85e3bbba60f4afa3b690e9d28dc04f2ca7c`

Operator Request: `operator-release-training-mainline-p2-3-37cfd85`

Operator execution: `144`

## 1. Outcome

M4-P2.3 is no longer merely code-complete. It was dispatched from the persisted
Ready Queue by the unified Research Evidence Supervisor, consumed the canonical
P2.1/P2.2 inputs, executed the existing strict harness, registered immutable
artifacts, projected completion, unlocked P2.4, and passed replay without manual
input assembly.

## 2. Primary goal and non-goals

The only primary goal was to repair the P2.3 integration boundary and make
mainline integration a permanent Definition of Done.

Non-goals remained intact:

- no P2.4 injected-signal implementation or execution;
- no P2.5 resampling, P2.6 power, or P2.7 gate implementation;
- no real-data or forward Evidence creation;
- no legacy adaptive training restart;
- no Promotion Gate or production strategy change;
- no Evidence Progress increase.

## 3. Root cause

Commit `d61e147` contained the P2.3 harness, but the control manifest classified
P2.3 as completed without a supervisor dispatch, immutable execution event, or
registered mainline artifact. The resident `dehps-research-runtime.service` was
not a consumer of the canonical Task DAG and had exhausted its daily budget
while remaining active. Therefore the correct pre-round classification was
`INTEGRATION_PENDING`, not `COMPLETE`.

## 4. Canonical execution chain

```text
M4_INFORMATION_THEORY_EVIDENCE
-> m4-p2-walk-forward-probe-harness
-> dependency resolver
-> persisted Ready Queue
-> Research Evidence Supervisor
-> m4_p2_3_walk_forward_harness
-> immutable fold/prediction/settlement/run/execution artifacts
-> unified M4 status projection
-> m4-p2-injected-signal-calibration
```

## 5. Required design answers

| Question | Accepted answer |
| --- | --- |
| Mainline problem | P2.3 could be declared complete without mainline execution |
| Node affected | Ready Queue to Supervisor to artifact/status boundary |
| Canonical Goal | `M4_INFORMATION_THEORY_EVIDENCE` |
| Formal Task | `m4-p2-walk-forward-probe-harness` |
| Ready condition | P2.2 complete plus frozen P2.1/P2.2/P2.3 artifact identities |
| Runner | Research Evidence Supervisor |
| Upstream artifacts | P2.1 dataset, P2.2 Metric Kernel, P2.3 harness |
| Downstream artifacts | folds, states, checkpoints, settlements, runs, execution |
| Status projection | unified M4 status plus resident supervisor state |
| Next consumer | `m4-p2-injected-signal-calibration` |
| Progress rule | Engineering 26→30; Evidence remains 0 |
| Decision consumer | later P2 Gate; P2.3 itself cannot open Promotion Gate |

## 6. Lifecycle proof

The lifecycle advanced in order:

```text
CODE_COMPLETE
-> INTEGRATION_PENDING
-> INTEGRATED
-> VALIDATED_IN_MAINLINE
-> COMPLETE
```

The source manifest placed P2.3 in `INTEGRATION_PENDING`. The supervisor changed
it to `RUNNING / INTEGRATED`, wrote the completed execution event and artifacts,
then projected `completed / COMPLETE`. The external replay result reported
`VALIDATED_IN_MAINLINE`.

## 7. Pre-execution resolver state

- Source manifest digest:
  `8c03e82f97190ead5c2d9002a71316ca381083c54a2fc62f5d420e40a5c2f573`
- Ready Task: `m4-p2-walk-forward-probe-harness`
- P2.4 state: `dependency_wait`
- Engineering Progress: 26%
- Evidence Progress: 0%
- Promotion Gate: `CLOSED`
- Production action: `none`

## 8. Execution identity

- Task digest:
  `0a493b3618f2b180719b360b17702d7587c25a8c6c59a577a0c099fccce01a62`
- Execution ID:
  `de52c376117bf308e0608b75e1418d58acf6b5a1e5cf4a66925fe06b8219d3cb`
- Execution artifact digest:
  `4e3d81cbee28b529091a11603e3a5683c1f265d9accc4f01d4c7076192c20363`
- Completed manifest digest:
  `ff1f8499c9a865bb339f61217ba35eb9a49c1d447ee58b84eb5576d713fb71fe`
- Git commit:
  `37cfd85e3bbba60f4afa3b690e9d28dc04f2ca7c`
- Working tree: clean

## 9. Upstream artifact verification

The supervisor discovered the P2.1 dataset from its digest-addressed canonical
runtime path. No dataset path was supplied to the dispatch command.

| Input | Verified digest |
| --- | --- |
| P2.1 synthetic dataset | `5354b9f7f6c72996cff16d6c161b03ff49922bf92589bd43b823d107019ebd86` |
| P2.2 Metric Kernel | `56b9d0a62d43d167069e5222c7095383c9c5106bb3361b0b1def75cf2b6c86a2` |
| P2.3 walk-forward harness | `177a3d591b7557a4231a276bfb007f0d42a94d942824403f5376f94fe904d2ca` |

## 10. Actual execution

The existing strict harness ran two null smoke probes:

- `THEORETICAL_BASELINE`
- `REGULARIZED_LOGISTIC_REGRESSION`

Each probe completed two chronological folds, for four actual folds total.
Prediction checkpoints remained target-free until settlement. Results are
descriptive measurement-system validation only and are ineligible for P2 Gate
Evidence.

## 11. Immutable artifact registration

The execution registered 22 unique artifacts across these types:

- `fold_feature_view_identity`;
- `immutable_preprocessing_state`;
- `immutable_probe_state`;
- `prediction_checkpoint`;
- `settled_fold_metric`;
- `synthetic_walk_forward_smoke`;
- `research_os_mainline_execution`;
- other typed run/fold manifests.

The PostgreSQL ledger contains exactly one `started` and one `completed` event
for the execution. The completion fact is accepted only because the completed
event and registered artifacts physically exist.

## 12. Post-execution status projection

- P2.3 declared status: `completed`
- P2.3 completion classification: `COMPLETE`
- Actual fold count: 4
- Registered artifact count: 22
- Engineering Progress: 30%
- Evidence Progress: 0%
- Promotion Gate: `CLOSED`
- Production action: `none`
- Formal real-data run: `NOT_STARTED`

## 13. Downstream transition

After P2.3 completion, the sole Ready M4 task became:

```text
m4-p2-injected-signal-calibration
```

The resident supervisor does not yet register the P2.4 capability, so it remains
healthy in `WAITING_FOR_CAPABILITY`. This is an explicit integration boundary,
not a claim that P2.4 is complete.

## 14. Engineering and Evidence separation

P2.3 proves that the measurement runner works, so Engineering Progress advanced
from 26% to 30%. It does not establish predictive evidence; Evidence Progress
therefore remained 0%. No Evidence, Decision, Promotion, prediction, or betting
artifact was created.

## 15. Replay

The replay command required only the control-plane key and Task key. It did not
accept or require dataset, Metric Kernel, harness, fold, or output paths.

Replay result:

- status: `REPLAY_VERIFIED`;
- same execution identity: true;
- same artifact identity: true;
- manual input assembly: false;
- actual fold count: 4;
- registered artifact count: 22.

## 16. State-regression protection

Re-importing a source manifest may not downgrade an already completed executable
Task with the same Task digest. The repository rejects that operation as a
mainline completion regression. A revised Task definition may still supersede
an old definition through the normal digest-addressed revision path.

## 17. Interrupted-finalization recovery

The supervisor accepts a persisted `RUNNING` Task. If the completed event exists
but the completed status projection was interrupted, restart finalizes the same
execution rather than rerunning it. A clean-tree Git commit mismatch fails
closed.

## 18. Resident service cutover

| Unit | Accepted state |
| --- | --- |
| `dehps-research-runtime.service` | disabled, inactive |
| `dehps-research-evidence-supervisor.service` | enabled, active |
| `dehps-forward-runtime.service` | active, untouched |

The new unit runs merged commit `37cfd85`. It conflicts with the superseded
free-running research unit.

## 19. No-spin observation

Across two additional 15-second resident cycles:

- state remained `WAITING_FOR_CAPABILITY`;
- Ready Task remained P2.4;
- process CPU time remained `00:00:04`;
- no traceback, failed cycle, restart, or error was logged;
- forward runtime remained active.

This is a legal wait and not the old per-second budget-exhaustion loop.

## 20. Validation

- Local full Worker suite: 1765 passed, 4 skipped.
- Targeted Research OS/M4/runtime suite: 207 passed.
- Focused mainline supervisor suite after CI fixture repair: 6 passed.
- GitHub Actions Worker Python Tests: passed.
- Ready PR #221: squash merged.
- PostgreSQL schema assurance: passed.
- Production mainline execution: passed.
- Deterministic replay: passed.
- Resident two-cycle health observation: passed.

The first GitHub run exposed a test-only dependency on an ignored local
`runtime/` dataset. The test was corrected to generate the canonical P2.1
dataset with the formal generator and verify the same digest. The rerun passed.

## 21. Integration matrix

| Integration item | Evidence | Result |
| --- | --- | --- |
| Canonical Goal | `M4_INFORMATION_THEORY_EVIDENCE` | PASS |
| Dependency Graph | P2.2 → P2.3 → P2.4 | PASS |
| Ready Queue | P2.3 before run; P2.4 after run | PASS |
| Unified Runner | execution `de52c376…` | PASS |
| Upstream artifacts | three frozen digests verified | PASS |
| Downstream artifacts | 22 immutable registrations | PASS |
| Status projection | completed manifest `ff1f8499…` | PASS |
| Engineering Progress | 26→30 | PASS |
| Evidence Progress | 0→0 by policy | PASS |
| Downstream consumer | P2.4 sole Ready Task | PASS |
| End-to-end replay | same execution/artifact identities | PASS |
| No old bypass | old runtime disabled; manual path non-canonical | PASS |

## 22. Path audit

Canonical completion is available only through:

```text
persisted Ready Task
-> Research Evidence Supervisor capability registry
-> immutable execution/artifact ledgers
-> completion fact validation
-> persisted status projection
```

The manual harness CLI remains a validator and development surface. It cannot
create the physical mainline completion fact by itself. The old continuous
research runtime is disabled and is not a canonical Task consumer.

## 23. Remaining work

P2.4 is intentionally `INTEGRATION_PENDING` at the capability boundary. Its
future implementation must use the same Goal, resolver, Ready Queue, supervisor,
artifact ledger, status projection, replay, and downstream-unlock requirements.
It may not reuse this P2.3 acceptance as evidence that P2.4 exists.

## 24. Final classification

YES — validated by unified mainline execution and replay
