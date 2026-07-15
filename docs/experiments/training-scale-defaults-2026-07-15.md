# Training scale defaults — 2026-07-15

## Round contract

- Primary goal: make the validated larger training budget the explicit, overrideable production-launcher default.
- Non-goals: no score, feature, weight, gate, data, worker-count, BLAS-thread, train/eval-window, or TopN change; no predictive-lift claim.
- Authorization: Agent Request `engineering-training-scale-defaults-b3533fc` (request id 92, execution id 14).
- Starting commit: `b3533fc`.

## Change

| Setting | Prior | New default | Environment override |
| --- | ---: | ---: | --- |
| max configs / round | 28 | 96 | `DEHPS_MAX_CONFIGS_PER_ROUND` |
| memory budget GB | 20 | 24 | `DEHPS_MEMORY_BUDGET_GB` |
| neural budget share | 0.10 | 0.20 | `DEHPS_NEURAL_KDJ_BUDGET_SHARE` |
| neural hidden units | implicit 8 | 8 | `DEHPS_NEURAL_KDJ_HIDDEN_UNITS` |
| neural epochs | implicit 120 | 120 | `DEHPS_NEURAL_KDJ_EPOCHS` |
| inversion candidates | 4 | 8 | `DEHPS_TARGET_INVERSION_MAX_CANDIDATES` |
| inversion deltas / target | 8 | 12 | `DEHPS_TARGET_INVERSION_MAX_DELTAS` |

Workers remain 16 by default and `--cpu-threads 1` remains fixed to prevent nested BLAS oversubscription.

## Evidence boundary

The earlier controlled 28/48/96 runs established that 96 generated configurations fit inside the 24 GB bound with zero swap and only 10.30% more wall time than 28 for that one-round workload. All three selected the same round-best config. Therefore this change increases route capacity and neural/inversion opportunity; it does not establish improved prediction quality.

The 32-hidden-unit / 500-epoch neural budget was requested but was not part of the earlier 96-config capacity run. Operator run `20260715-142155` tested it after merge in observability-only mode: the round completed in 306.17 seconds, generated 96 configurations, selected 26, and reached a maximum RSS of 9,691,156 KiB. However, repeated `/proc/<pid>/status` samples showed `VmSwap` rise from 0 to 87,740 KiB. The run made no database writes and was rejected; the normal watchdog was not activated.

The corrective round is authorized by Agent Request `engineering-rollback-neural-capacity-bd09e96` (request id 94, execution id 16). It restores the previously validated per-model capacity of 8 hidden units and 120 epochs while retaining 96 configurations, a 20% neural share, the 24 GB bound, and the expanded inversion budget. This is a capacity rollback, not a scoring or model-selection change.

## Validation before live run

```text
bash -n scripts/ensure_training_supervisor.sh
10 launcher/forward-wait contract tests passed in 0.22s
981 full worker tests passed in 34.97s
```

Capacity-rollback validation:

```text
bash -n scripts/ensure_training_supervisor.sh
17 launcher/forward-wait contract tests passed in 0.10s
981 full worker tests passed in 43.96s
```

## Remaining acceptance after capacity rollback

After merge, an approved Operator restart must record the new run id and observe at least one completed 8×120 round, including generated/selected config counts, stage durations, active workers, maximum memory, repeated process-level swap samples, forward-promotion cohort count, and prediction status. Only a run whose sampled `VmSwap` remains zero may activate the normal watchdog. A second round should be observed when the supervisor does not park at its forward-wait boundary after round 1.
