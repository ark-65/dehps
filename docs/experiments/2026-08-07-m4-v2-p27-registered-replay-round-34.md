# M4 Measurement v2 P2.7 Registered Replay — Round 34

## Round contract

- Primary goal: remove the automatic P2.7 consumer's duplicate 31,000-journal
  physical replay after the immutable P2.6.3 completion has already been
  accepted and registered.
- Non-goals: no statistic, threshold, null model, decision, Evidence,
  Prediction v2 promotion, strategy promotion, or P3 execution change.
- Ready condition: round-33 raw replay, P2.7 gate replay, marginal binding, and
  marginal decision replay are complete and individually `REPLAY_VERIFIED`.
- Runner: unified Research Evidence Supervisor; normal replay calls
  `verify_completion_replay`, while an explicit corruption audit calls
  `verify_completion_deep_replay` directly.
- Upstream artifacts: exact P2.6.3 execution, completion, update-policy digest,
  ordered replicate/journal roots, 31 aggregate identities, and P2.7 execution.
- Downstream artifacts: unchanged P2.7 automatic-gate digest and Measurement v2
  gate-replay lineage.
- Status projection: `CODE_COMPLETE -> INTEGRATION_PENDING`; merged runtime
  validation is required before `VALIDATED_IN_MAINLINE` and `COMPLETE`.
- Evidence rule: normal replay must reject completion/policy identity drift and
  must not call the 31,000-replicate assembler. The separate deep replay must
  still call the assembler.
- Decision consumer: Measurement v2 marginal binding only.
- Next consumer: branch-identifiability preflight design remains unsupported;
  Prediction v2 and P3 remain closed.

## Incident and correction

Round 33 showed that the Measurement v2 P2.7 consumer still nested the canonical
P2.7 replay. That replay rebuilt the P2.6.3 completion from 31,000 checkpoint
journals after the raw source-binding task had already verified the immutable
registered content. The repeated read consumed approximately 40 GiB and about
11.5 minutes without changing the gate decision.

Normal replay now verifies the digest-addressed completion payload, parent
execution, manifest, git commit, and exact update-policy digest. The completion
digest covers its ordered replicate and checkpoint roots, aggregate identities,
MDE identity, and all completion counters. It returns the explicit mode
`REGISTERED_COMPLETION_IDENTITY` and does not assemble journals.

`verify_completion_deep_replay` retains the prior full physical behavior and
returns `FULL_CHECKPOINT_REASSEMBLY`. It is deliberately not routed through the
normal automatic consumer and is reserved for a requested corruption audit.

## Validation evidence

- Focused replay guards: `4 passed`.
- Measurement validation + unified Supervisor + M4 hardening + P2.6.3 source
  governance: `127 passed in 106.06s`.
- Full Worker suite in a clean detached worktree at implementation commit:
  `2061 passed, 4 skipped, 4 warnings in 217.24s`.
- The first full-suite run in the live development root produced 42 unrelated
  legacy-pipeline failures because the existing untracked Prediction v2
  activation runtime retires those legacy paths. The clean detached rerun above
  contains no runtime state and passes all 2,061 tests.
- Ruff on the touched Python surface: passed.
- `git diff --check`: passed.
- Read-only replay against the completed local mainline P2.7 execution:
  `REPLAY_VERIFIED`, unchanged automatic-gate digest
  `4b8a881c2d093d608d3e9c23e184034628f1440c9c0a08f868aea1028e78e3f8`,
  unchanged decision `REPAIR_MEASUREMENT_SYSTEM`, 1.33 seconds wall time,
  284 MiB peak RSS, and 13,328 filesystem input blocks (about 6.5 MiB).
- Observed comparison: about 690 seconds / 40 GiB before versus 1.33 seconds /
  about 6.5 MiB after; approximately 519x lower wall time on this replay.

## Integration matrix

| Link | Round-34 state | Proof |
| --- | --- | --- |
| Goal -> Resolver | Integrated contract, no DAG change | Existing exact P2.7 task identity |
| Resolver -> Ready Queue | Previously validated | Round-33 immutable completed chain |
| Ready Queue -> Supervisor | Code complete | Normal Supervisor replay uses registered completion mode |
| Supervisor -> Capability | Code complete | P2.7 reconstructs the unchanged automatic gate without journal assembly |
| Capability -> Artifacts | Preserved | Completion and gate digests unchanged |
| Artifacts -> Status | Integration pending | Fresh merged Supervisor required |
| Status -> Next Task | Closed | Unsupported preflight remains next; no Prediction/P3 execution |
| Deterministic replay | Isolated verified | Completed local P2.7 replay in 1.33 seconds |

Final integration answer at engineering handoff:

`NO — INTEGRATION_PENDING` until the merged commit runs under the fresh unified
Supervisor and the registered P2.7 replay is reverified.
