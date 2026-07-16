# Research Task Randomness Contract — 2026-07-16

## Round contract

- Primary goal: replace the suite-wide seed/fingerprint model with task-level deterministic and stochastic contracts.
- Engineering authorization: Agent Request `107` (`engineering-task-randomness-contract-2f88eea`), execution `30`.
- Non-goals: no production prediction generation, no pending-run mutation, no model promotion, no strategy-weight change, and no database migration.
- Historical boundary used for the operational check: latest history `2026080`; target prediction `2026081` remains pending.

## Root cause

The previous isolated research lane put one seed list into the suite-level configuration and then hashed the entire configuration. This created two identity errors:

1. deterministic diagnostics, fixed walk-forward, and complete weight-grid tasks inherited irrelevant random configuration;
2. a single replicate seed could be mistaken for a new research identity instead of one execution under a stochastic experiment protocol.

The default suite also included Monte Carlo frozen controls, so a control task made the whole suite appear stochastic.

## Implemented contract

The research identity is now hierarchical:

```text
suite fingerprint
  -> deterministic task experiment fingerprint = deterministic run fingerprint
  -> stochastic task experiment fingerprint
       -> replicate run fingerprint(seed)
```

Each `ResearchTaskSpec` declares `execution_mode`, a task-projected configuration, an evaluation contract, and—only for stochastic tasks—a normalized `SeedPolicy`.

Deterministic tasks reject seed policies and random configuration fields. Their fingerprints contain the history snapshot, code commit, task type, model/feature/candidate versions, task-projected config hash, and evaluation contract. They contain no seed field.

Stochastic experiment fingerprints additionally contain the complete normalized seed set, aggregation policy, and `no_best_seed` selection policy. A replicate run fingerprint is the experiment fingerprint plus one seed from that set. Seed-list ordering and duplicate entries are normalized; adding or removing a seed changes the experiment protocol, while the novelty detector still classifies seed-only changes as non-innovative stability work.

## Suite separation

The default `idle-optimization-v3` suite is now purely deterministic:

- training diagnostics;
- fixed walk-forward optimization;
- complete weight-grid search;
- analytic uniform-rank null baseline.

Monte Carlo frozen controls are an explicit `frozen-controls` stochastic task and require `--random-seeds`. A deterministic suite rejects that argument. The supervisor watchdog continues to park duplicate production prediction while allowing this seed-free research suite.

## Randomness inventory

The source audit covered `apps/worker-python/dehps`, `apps/worker-python/scripts`, SQL-bearing source, and supervisor entry points.

| Location | Random behavior | Seed contract after this round |
| --- | --- | --- |
| `dehps/training/runtime.py` | stagnation restart choices/samples; exploratory, replay, and surrogate parameter proposals | explicit deterministic seed or explicit caller-injected seed |
| `dehps/candidates/null_model.py` | red-combination sampling | `Random(seed)`; caller must provide seed; candidate script no longer falls back to system date |
| `dehps/optimization/control_experiments.py` | Monte Carlo uniform random ranks | explicit normalized seed set; aggregate mean, population variance, p05/p50/p95, and worst case; no best seed |
| `scripts/run_neural_feasibility_probe.py` | negative sampling, row shuffling, MLP initialization, batch permutation | explicit seed is passed to every RNG; default validation split changed from random to temporal-positive |
| `dehps/optimization/neural_kdj_advisor.py` | NumPy MLP initialization | explicit seed, with deterministic per-weight derivation |
| `scripts/run_near_residual_backtest.py` | shuffled residual control | seed deterministically derived from issue hash |
| `dehps/experiments/ranking_disagreement/baselines.py` | budget-matched random baseline via `choice` | already used `default_rng(seed + stratum_index)`; no unseeded defect was present |
| `dehps/experiments/ranking_disagreement/statistics.py` | bootstrap resampling and sign-flip permutation | explicit caller seed for bootstrap; fixed explicit seed for sign flips |
| `scripts/probe_opencl_score_backend.py` | randomized probe configurations | explicit caller seed |

No zero-argument or `None`-seed `random.Random` / `numpy.random.default_rng` construction was found. No SQL `RANDOM()` / `ORDER BY RANDOM()` and no sklearn-style randomized parameter-search implementation was found. Randomized parameter proposals in the training runtime are listed above and are explicitly seeded.

Static AST regression tests now reject unseeded RNG construction and system-time-derived seed variables in worker runtime source.

## Deterministic null model

`generate_analytic_null_baseline.py` computes the uniform-rank expectation over the legal双色球 red-ball sample space without sampling. It records `seed: null` and `random_sampling_performed: false` and is reproducible for the same history/configuration inputs.

## Validation

- Worker test suite: `1009 passed in 33.18s`.
- Focused randomness/lane/control tests passed before the full suite.
- Python byte-code compilation passed for changed modules.
- `bash -n scripts/ensure_training_supervisor.sh` passed.
- `git diff --check` passed.
- Static RNG audit found no unseeded constructors and no system-time-derived seed variables.

Read-only database verification after implementation and tests:

```json
{
  "latest_history": "2026080",
  "runs": [{"target_issue": "2026081", "status": "pending", "count": 3}],
  "candidates": 30000,
  "evaluation_runs": 0
}
```

No database schema or data changes were made. Existing production prediction runs and candidates remain unchanged.

## Gauss verification pass

- Identity invariant: a deterministic task has exactly one run identity for the same historical snapshot, code, effective task configuration, versions, window, and evaluation contract.
- Replicate invariant: changing the selected replicate changes only its stochastic run fingerprint; changing the normalized seed set changes the experiment contract.
- Null-model boundary: the analytic baseline uses the full legal combination count and makes no predictive-lift claim.
- Leakage boundary: the default suite remains historical and read-only; the change does not promote weights or write forward predictions.

This round fixes reproducibility and research-governance semantics. It does not claim improved prediction quality.
