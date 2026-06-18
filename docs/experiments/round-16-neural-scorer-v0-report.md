# Round 16 Report: Explicit Neural CPU MLP Scorer V0

## Summary

- Extended the neural feasibility probe with an explicit `neural_cpu_mlp_v0` full-universe scorer.
- The scorer is opt-in via `--score-top-k`; it is not connected to the default supervisor.
- The scorer trains a tiny NumPy CPU MLP, scores the existing full universe matrix, and writes Top-K neural candidates into the ignored local report/JSON.
- The smoke confirms the machine can score the full filtered universe quickly, but validation AUC remains near null.

## Command

```bash
/usr/bin/time -f 'elapsed=%E maxrss=%MKB' apps/worker-python/.venv/bin/python apps/worker-python/scripts/run_neural_feasibility_probe.py --as-of-issue 2026067 --max-sample-rows 20000 --negative-ratio 10 --epochs 2 --hidden-units 32 --batch-size 4096 --learning-rate 0.03 --score-top-k 10
```

## Result

```text
report: data/output/optimization/neural-feasibility-20260618-103322.md
elapsed: 0:15.47
maxrss: 1056460 KB
universe_rows: 1105506
sampled_rows: 16434
feature_count: 61
validation_auc_epoch_2: 0.484790
score_seconds_full_universe: 2.981
score_min_median_max: 0.43833679 / 0.50586486 / 0.56689465
```

Top 10 neural candidates from the smoke:

```text
1. 05 19 20 21 31 32  score=0.56689465
2. 04 05 06 21 31 32  score=0.56670535
3. 05 06 14 15 32 33  score=0.56620026
4. 05 18 19 21 31 32  score=0.56451756
5. 06 07 14 15 32 33  score=0.56330383
6. 05 06 07 15 31 32  score=0.56306618
7. 05 06 07 15 32 33  score=0.56287956
8. 05 18 19 20 31 32  score=0.56252545
9. 04 05 06 19 31 32  score=0.56249458
10. 05 06 07 21 31 32 score=0.56177181
```

## Interpretation

This proves the project now has a concrete neural scorer path on the current machine. It does not prove signal. The validation AUC near 0.5 says this static historical-positive-vs-sampled-negative setup is still null-like.

The useful next experiment is not a bigger model. It is a frozen walk-forward comparison where `neural_cpu_mlp_v0` is treated like another scorer and compared against structural, frequency, omission, null, and current-best controls.

## Promotion Gate

Keep the scorer outside the default supervisor until all are true:

- Frozen validation beats same-budget controls on the objective score.
- Tail risk does not rise versus the current best frozen baseline.
- Top-K output is stable across seeds and adjacent time windows.
- Results are recorded to DB with the same per-round protocol as other training summaries.

## Guardrail

The neural score is a historical hypothesis artifact, not a prediction claim.
