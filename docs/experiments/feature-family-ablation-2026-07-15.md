# Feature-family ablation diagnostics — 2026-07-15

## Round contract

- Primary goal: add a deterministic leave-one-feature-family-out diagnostic and run it against identical target issues.
- Non-goals: no production scoring change, weight tuning, new model, hypothesis decision, database mutation, supervisor restart, or strategy promotion.
- Authorization: Agent Request `engineering-feature-ablation-diagnostics-5febd6a` (request id 89, execution id 11).
- Base commit: `5febd6a9a3899c031ca8916c520741547f48d53a`.

## Tool contract

The 32 `FrequencyRankerConfig` weight fields are assigned to exactly one of six explicit families: structural, frequency, omission, recent state, shape/trend, and temporal stability. Import-time validation rejects missing, unknown, or duplicated fields. Each challenger is produced from the unchanged full configuration by zeroing only one declared family.

All seven configurations are evaluated together over the same ranked mmap universe, training protocol, and target issues. The artifact records full and frozen metrics plus raw ablated-minus-full deltas. It is fail-closed with `status=diagnostic_only` and `promotion_allowed=false`.

## Execution

- as-of issue: `2026080`
- history scope: current 10-year regime proxy
- train mode/window: expanding / 900
- evaluation/frozen windows: 100 / 20
- Top-N: 10,000
- ranked universe: 1,105,506
- workers: 16
- mmap cache hit/open: 0.004 seconds
- evaluation elapsed: 164.968 seconds
- target history fingerprint: `34de80e61758227179a123e38a127aa3fc1a46ef5757d8b23757b5c6b7a84b6c`
- full-model config hash: `5e17c66ecf148bfa2787431597eaba77011fee46e22e44203e0d52923e09e033`
- base source: latest durable `training_round_results` matching the protocol
- identical target issues: true

The generated runtime JSON and Markdown remain under `apps/worker-python/data/output/optimization/feature-ablation-20260715-5febd6a/` and are intentionally not committed.

## Results

Positive hit/objective deltas mean the ablated model scored higher; positive rank/tail deltas mean it was worse.

| Removed family | Overall objective delta | Exact Top100/1000/10000 delta | Red5 Top100/1000/10000 delta | Median-rank delta | Frozen objective delta |
| --- | ---: | --- | --- | ---: | ---: |
| structural | -3.455 | 0 / 0 / 0 | 0 / -4 / -3 | -5,294 | +5.745 |
| frequency | -2,581.930 | -2 / -1 / 0 | 0 / -5 / +6 | -5,627.5 | -0.750 |
| omission | -1,203.431 | -1 / 0 / 0 | 0 / -3 / 0 | +6,806.5 | +0.244 |
| recent state | -3,970.262 | -3 / -2 / 0 | -1 / -4 / +6 | -7,134 | +0.206 |
| shape/trend | -3,982.175 | -3 / -2 / -1 | -2 / -6 / -9 | +37,817.5 | -5.660 |
| temporal stability | -5.720 | 0 / 0 / 0 | 0 / -5 / +2 | +14,970 | -0.114 |

The full model produced 3 exact Top100/1000/10000 hits over the 100-issue evaluation, but zero exact Top10000 hits in the trailing 20 frozen issues. Its Red5 counts were 3 / 11 / 29 overall and 0 / 1 / 5 frozen.

## Interpretation boundary

The overall slice is most sensitive to removing recent-state and shape/trend families, and shape/trend removal worsens both overall and frozen objectives. Frequency and omission also carry substantial overall objective contribution. Structural and temporal-stability effects are small overall and directionally mixed on frozen data.

This is not a license to increase, decrease, or delete any family. The frozen slice has no exact Top10000 hits, several families change Red5 and median-rank metrics in opposite directions, and historical ablations are selected after observing the same history. The smallest defensible conclusion is that shape/trend and recent-state deserve finer preregistered diagnostics, while all weight changes remain blocked pending genuinely forward unseen evidence.

## Validation

Focused feature-ablation and control tests:

```text
14 passed in 0.37s
```

Final worker suite after the renderer edge-case regression:

```text
969 passed in 47.66s
```

Durable post-run markers remained:

```text
training_round_results             10010  2026-07-14 22:12:08.512835+08
training_supervisor_best              11  2026-07-14 21:31:26.150290+08
training_line_round_results          2034  2026-07-14 22:12:08.512835+08
training_target_weight_inversions  700050  2026-07-14 22:12:08.512835+08
forward runs for 2026081                 3
forward candidates for 2026081        30000
```

Only Agent Request audit rows and ignored local evidence artifacts were added.

## Champion/challenger audit

The current system deliberately quarantines every non-initial historical frozen promotion with `missing_forward_evidence`. Forward evaluation aggregation requires 20 complete paired issues across static, dynamic, and near-dynamic lines, validates leakage boundaries, and reports exact/Red5 deltas against the static baseline.

However, the aggregation is explicitly `review_only=true`, `promotion_eligible=false`, and `automatic_quarantine_release=false`. The production runtime never consumes durable `forward_evaluation_runs` / `training_prediction_evaluations` to construct a config-bound candidate/incumbent `EvaluationResult` or release quarantine. Therefore the evaluation data loop now closes operationally, but the champion/challenger promotion loop is not implemented. Adding it is a separate behavior-changing round requiring a frozen promotion contract; it must not be inferred from this diagnostic run.
