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
| neural hidden units | implicit 8 | 32 | `DEHPS_NEURAL_KDJ_HIDDEN_UNITS` |
| neural epochs | implicit 120 | 500 | `DEHPS_NEURAL_KDJ_EPOCHS` |
| inversion candidates | 4 | 8 | `DEHPS_TARGET_INVERSION_MAX_CANDIDATES` |
| inversion deltas / target | 8 | 12 | `DEHPS_TARGET_INVERSION_MAX_DELTAS` |

Workers remain 16 by default and `--cpu-threads 1` remains fixed to prevent nested BLAS oversubscription.

## Evidence boundary

The earlier controlled 28/48/96 runs established that 96 generated configurations fit inside the 24 GB bound with zero swap and only 10.30% more wall time than 28 for that one-round workload. All three selected the same round-best config. Therefore this change increases route capacity and neural/inversion opportunity; it does not establish improved prediction quality.

The 32-hidden-unit / 500-epoch neural budget was requested but was not part of the earlier 96-config capacity run. It requires a fresh merged-code supervisor and 1–2 completed live rounds before operational acceptance.

## Validation before live run

```text
bash -n scripts/ensure_training_supervisor.sh
10 launcher/forward-wait contract tests passed in 0.22s
981 full worker tests passed in 34.97s
```

## Remaining acceptance

After merge, an approved Operator restart must record the new run id and observe at least one completed round, including generated/selected config counts, stage durations, active workers, maximum memory/swap, forward-promotion cohort count, and prediction status. A second round should be observed when the supervisor does not park at its forward-wait boundary after round 1.
