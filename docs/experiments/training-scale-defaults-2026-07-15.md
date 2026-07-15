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

## Live acceptance after capacity rollback

Operator Request `operator-validate-neural-rollback-209a1a4` (request id 95, execution id 17) ran merged commit `209a1a4` in bounded observability-only mode. Supervisor run `20260715-144158` completed one 8×120 round in 282.70 seconds, generated 96 configurations, and selected 26. The main stage timings were:

| Stage | Seconds | Active workers |
| --- | ---: | ---: |
| candidate generation | 4.531 | 1 |
| prefilter | 16.510 | 16 |
| main evaluation | 66.177 | 16 |
| target-weight inversion | 50.547 | 16 |
| dynamic KDJ | 40.095 | 16 |
| near dynamic KDJ | 4.698 | 9 |

`/usr/bin/time` reported maximum RSS 10,108,012 KiB and zero swaps. Six process-tree samples taken across generation, evaluation, inversion, and dynamic training all reported `VmSwap=0`; the maximum sampled aggregate RSS was 11,499,464 KiB, below the 24 GB budget. The observability-only database guard skipped persistence. Durable markers remained unchanged at 10,010 `training_round_results` rows and 11 `training_supervisor_best` rows.

After acceptance, the normal watchdog was invoked. It parked intentionally on `watch_forward_wait_ready:2026080->2026081` rather than repeat training on unchanged history. The existing issue `2026081` prediction remains `waiting_draw` with three lines and 30,000 candidates; no continuous supervisor is active. Forward-promotion cohorts and champion-state rows remain zero because no challenger is yet eligible.

Operational acceptance is complete for the 96-config, 20% neural-share, 8×120 defaults. A second live round was neither required nor forced because the forward-evidence wait boundary was already satisfied. This acceptance establishes runtime safety and operability only; it does not establish predictive lift.
