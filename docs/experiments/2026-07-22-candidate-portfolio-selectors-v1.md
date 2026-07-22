# Candidate Portfolio Selectors v1

- Date: 2026-07-22
- Role: Engineering Agent
- Status: implementation acceptance candidate
- Evidence level: `RESEARCH_ONLY`
- Production TopK change: none

## Round contract

### Primary goal

Implement the preregistered immutable `PortfolioSelector` boundary and four research backends while preserving exact `score_topk` control parity and keeping every selector disconnected from production.

### Non-goals

- no coefficient, cluster-count, quota-mode, or seed policy selection;
- no target-outcome read, backtest conclusion, or predictive-lift claim;
- no walk-forward executor or bootstrap inference;
- no production reducer, training, prediction, storage, API, or dashboard integration;
- no overlap threshold or automatic promotion path.

## Interface

`PortfolioRequest` seals:

- one legal, unique, consecutive, strict-v1 scored candidate pool;
- explicit budget and one of four closed selector keys;
- deeply immutable selector config and issue/line/replicate context;
- verified candidate-pool, history, and score-config digests;
- explicit pre-target cutoff (`as_of_issue < target_issue`);
- optional master seed.

`PortfolioSelection` records:

- source-rank-sorted selected rows plus separate marginal choice order;
- selector config, request, candidate-pool, and portfolio digests;
- geometry, score-retention, red3+, and red4+ ESS diagnostics;
- selector protocol, code commit, Python version, algorithm provenance, and backend-specific trace;
- fixed `evidence_level=RESEARCH_ONLY` and `automatic_promotion_allowed=false`.

The selector layer consumes already-scored rows. It cannot score candidates, read a target draw, write runtime state, or mutate production selection.

## Backends

### `score_topk`

- accepts only an empty config;
- selects strict-v1 score descending, then lex_id ascending;
- matches the current production reducer on the same sealed pool;
- serves only as the exact control backend.

### `random_from_top_pool`

- requires `sampling_contract=uniform_without_replacement` and a master seed;
- derives a domain-separated seed from selector config, pool digest, budget, line, as-of issue, target issue, and replicate id;
- records master/derived seeds, derivation digest, MT19937, and Python version;
- samples distinct candidates from the same sealed scored pool.

### `greedy_score_diversity`

- requires all five coefficients `alpha`, `lambda`, `nu`, `mu2`, and `mu3`; there are no defaults;
- evaluates the exact preregistered marginal utility `alpha*Q-lambda*R-nu*E+mu2*C2+mu3*C3`;
- normalizes rank quality inside the pool and uses final-budget denominators;
- maintains number counts plus covered pair/triple sets incrementally;
- breaks equal marginal utility by higher rank quality and lower lex_id;
- uses no overlap threshold.

### `cluster_quota`

- represents each candidate by its 33-bit membership mask and uses Jaccard distance;
- requires explicit cluster count, initialization, quota mode, within-cluster rule, redistribution rule, and maximum iterations;
- implements deterministic score-first farthest medoid initialization and k-medoids updates;
- resolves geometric ties by higher score then lower lex_id;
- supports equal and size-proportional quotas with capacity-safe deterministic redistribution;
- records medoids, cluster sizes, quotas, redistribution trace, iterations, and convergence status.

## Fail-closed checks

The selector request or result is rejected for:

- illegal, duplicate, non-finite, non-consecutive, or non-strict-v1 pool rows;
- pool/history/config digest failure;
- missing or invalid issue/line/replicate context;
- history cutoff at or after the target issue;
- budget outside the sealed pool;
- unregistered selector key, missing required config, hidden defaults, or non-finite coefficients;
- missing random seed or changed sampling contract;
- duplicate, wrong-sized, mutated, or out-of-pool output.

## Validation

```text
apps/worker-python/.venv/bin/python -m pytest -q \
  apps/worker-python/tests/test_candidate_portfolio_selectors.py \
  apps/worker-python/tests/test_candidate_portfolio_audit.py \
  apps/worker-python/tests/test_candidate_abi_contract.py \
  apps/worker-python/tests/test_evaluation_contract.py \
  apps/worker-python/tests/test_postgres_store.py \
  apps/worker-python/tests/test_topk_reducer.py \
  apps/worker-python/tests/test_ranking_contract.py
```

Result: `107 passed`.

Compileall and diff checks passed. Reference search found no selector import outside `dehps.portfolio` and its tests.

The parity test calls the production `ordered_topk` reducer, including an equal-score tie, and compares ordered lex_ids and scores with `score_topk`.

## Live Top10K runtime smoke

Source: `static_100:2026084:training-next-2026083-3a021a36e6bb`

- sealed pool: Top10K;
- budget: 100;
- random master seed: `20260722`;
- greedy smoke coefficients: all five set to `1.0`;
- cluster smoke config: 20 clusters, equal quotas, maximum 5 iterations;
- purpose: runtime and contract validation only, not tuning or outcome evidence.

| Backend | Runtime | Mean overlap | Max exposure | Pair coverage | Triple coverage | red4+ ESS | Score retention |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| score_topk | 0.37s | 2.580 | 90% | 42.42% | 11.90% | 16.08 | 100.00% |
| random_from_top_pool | 0.38s | 1.413 | 41% | 71.78% | 24.27% | 62.68 | 97.69% |
| greedy_score_diversity | 28.02s | 1.332 | 39% | 84.85% | 28.81% | 79.34 | 98.37% |
| cluster_quota | 2.40s | 1.973 | 79% | 52.84% | 15.52% | 28.32 | 99.60% |

`score_topk` exactly reproduced the previously verified current snapshot metrics. The cluster run converged. The other backends produced exactly 100 unique in-pool rows and valid research-only diagnostics.

The smoke coefficients and cluster configuration were chosen only to exercise code paths. The table demonstrates controllable geometry/score tradeoffs and realistic runtime, not a preferred selector. No target outcome was read.

Because the smoke ran before this implementation had a commit, its recorded selector code commit identifies the clean parent checkout rather than the uncommitted diff. It is therefore runtime evidence only. Formal walk-forward artifacts must be generated after this round is merged.

## Scientific cross-review

### Gauss pass: verification

- Exact check: `score_topk` shares the production strict-v1 ordering implementation in its parity test.
- Exact check: greedy marginal terms algebraically match the preregistered final-set utility; no threshold is hidden in the implementation.
- Exact check: every output is a unique exact subset of the sealed pool and preserves its source records.
- Weakest assumption: float equality determines rare exact marginal ties; lower lex_id remains a deterministic final tie-break.
- Required next test: paired issue-level outcomes and confidence intervals, never ticket-level pseudo-replication.

### Riemann pass: structure

- The four backends span scalar ordering, pool-random coverage, continuous set utility, and candidate-space partitioning.
- Selection order and presentation order are separated so marginal geometry remains auditable without corrupting source-rank contracts.
- Weakest assumption: Jaccard-medoid geometry and pair/triple utility may omit outcome-relevant structure.
- Required next test: compare the backends on identical sealed pools and eligible issues under one walk-forward protocol.

### Synthesis

The smallest shared conclusion is that all four preregistered selector mechanisms now exist behind one fail-closed research boundary, and the control backend has exact parity. Geometry can be changed while retaining most mean score on the current pool, but no backend has predictive authority until strict walk-forward evidence exists.

## Round decision

- Selector interface and four research backends: ready for review.
- Production TopK: unchanged and unreferenced by production callers.
- Preferred selector/config: none.
- Predictive lift: untested.
- Promotion: prohibited.
- Next round: implement sealed issue-level walk-forward evaluation, paired controls, deterministic moving-block bootstrap, and fail-closed upgrade criteria.
