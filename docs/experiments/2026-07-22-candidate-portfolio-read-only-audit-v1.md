# Candidate Portfolio Read-Only Audit v1

- Date: 2026-07-22
- Role: Engineering Agent
- Status: implementation acceptance candidate
- Evidence level: `RESEARCH_ONLY_DIAGNOSTIC`
- Production TopK change: none

## Round contract

### Primary goal

Implement the read-only portfolio audit boundary preregistered in `2026-07-22-candidate-portfolio-architecture-audit-v1.md`, with reproducible null comparisons and fail-closed provenance.

### Non-goals

- no `PortfolioSelector` execution;
- no production reducer, scoring, training, persistence, API, dashboard, mail, or notification change;
- no overlap threshold or automatic deduplication;
- no strategy promotion or research conclusion;
- no claim that diversity improves 4+ red outcomes.

## Delivered boundary

The new isolated package is `dehps.portfolio`. Nothing outside the new CLI and tests imports it.

```text
durable forward run or JSON candidate pool
  -> canonical ScoredCandidate validation
  -> sealed selected/pool digests
  -> portfolio geometry and event-specific ESS
  -> two seeded null comparisons
  -> canonical content/artifact digests
  -> RESEARCH_ONLY audit JSON
```

The CLI supports:

- `--prediction-run-key`: read one durable `forward_prediction_runs` snapshot and its candidate rows;
- `--input`: read an arbitrary JSON selected set/candidate pool;
- `--verify-artifact`: verify schema and all canonical digests;
- `--budget` and `--pool-limit`: keep the selected portfolio and comparison pool explicit;
- explicit seed and replicate counts;
- optional atomic JSON artifact output.

The database loader executes `SET TRANSACTION READ ONLY`. It performs no `INSERT`, `UPDATE`, `DELETE`, DDL, state transition, or promotion operation.

## Contract checks

The auditor rejects:

- illegal, noncanonical, duplicate, or incorrectly identified candidates;
- non-finite scores and implicit numeric strings;
- duplicate or disordered source ranks;
- a selected row absent from, or inconsistent with, its sealed candidate-pool row;
- a durable candidate pool with missing source ranks;
- `as_of_issue >= target_issue`;
- a declared `strict_v1` pool not ordered by score descending and `lex_id` ascending;
- candidate pool smaller than the budget;
- unknown artifact fields, changed metric/null protocols, digest tampering, or promotion permission.

PostgreSQL finite `NUMERIC` values are accepted explicitly as `Decimal`; strings are not coerced.

## Metrics

For any selected portfolio, the artifact records:

- all 33 number counts, per-ticket exposure, slot share, maximum exposure and ties;
- pairwise overlap histogram, mean, P50, P90, and maximum;
- unique pair/triple count, full legal-universe coverage, attainable-budget coverage, and maximum core concentration with ties;
- number HHI, normalized Shannon entropy, and effective exposed-number count;
- event-specific red3+ and red4+ ESS using exact pair-event correlations under the uniform `C(33,6)` draw null;
- score min/P05/P50/P95/max/mean;
- mean score difference and retention ratio versus exact same-pool `score_topk`.

ESS is never reported without the event and formula:

```text
ESS_k = B / (1 + (B - 1) * mean_pair_indicator_correlation_k)
```

It is a variance-equivalent diagnostic under the declared null, not a universal count of independent predictions.

## Null models and reproducibility

Every audit includes both:

1. `uniform_legal_same_budget`: distinct portfolios sampled uniformly from Candidate Contract `C(33,6)`;
2. `random_from_candidate_pool`: uniform samples without replacement from the exact sealed pool.

For every standardized metric the artifact reports mean, sample SD, P05/P50/P95, observed value, z deviation, and zero-variance status. Same-pool random audits additionally report the mean-score distribution.

Seeds are derived by domain-separated SHA-256 from:

- master seed;
- null key;
- budget;
- replicate count;
- candidate-pool digest for the same-pool null.

The artifact records master/derived seeds, derivation digests, RNG algorithm, Python version, replicate counts, null-config digest, selected portfolio digest, candidate-pool digest, source history/config provenance, audit code commit, deterministic content digest, and timestamp-bound artifact digest.

Missing or invalid historical provenance does not prevent descriptive geometry calculation. It changes status to `audited_with_provenance_gaps`, lists each gap, and remains ineligible for automatic promotion. Every artifact sets `automatic_promotion_allowed=false`.

## Live read-only smoke validation

Source:

```text
static_100:2026084:training-next-2026083-3a021a36e6bb
```

Parameters:

- selected budget: 100;
- candidate pool: Top10K;
- master seed: `20260722`;
- smoke replicates: 20 per null;
- role: runtime validation only, not final statistical evidence.

Observed result:

| Metric | Value |
| --- | ---: |
| Average overlap | 2.5795959596 |
| Maximum number exposure | 90% |
| Pair coverage | 42.4242% |
| Triple coverage | 11.8952% |
| ESS red3+ | 6.7773 |
| ESS red4+ | 16.0787 |
| Uniform-null overlap z | +117.29 |
| Uniform-null pair-coverage z | -56.09 |
| Uniform-null triple-coverage z | -63.29 |

The new result reproduces the earlier ad-hoc audit values for this snapshot. The artifact verifier returned `valid=true`.

Database row counts were captured before and after the CLI run:

```text
forward_prediction_runs:          12 -> 12
forward_prediction_candidates: 120000 -> 120000
training_next_candidates_current: 30000 -> 30000
```

The smoke artifact is generated under `data/output/` and is not committed. Because it was produced before the implementation commit existed, it is runtime evidence only; formal retained-window artifacts must be regenerated from the clean merged implementation.

## Validation

```text
apps/worker-python/.venv/bin/python -m compileall -q \
  apps/worker-python/dehps/portfolio \
  apps/worker-python/scripts/audit_candidate_portfolio.py

apps/worker-python/.venv/bin/python -m pytest -q \
  apps/worker-python/tests/test_candidate_portfolio_audit.py \
  apps/worker-python/tests/test_candidate_abi_contract.py \
  apps/worker-python/tests/test_evaluation_contract.py \
  apps/worker-python/tests/test_postgres_store.py
```

Final result after schema hardening: `87 passed`.

The reference search confirms there is no production import of `dehps.portfolio`; references are limited to the isolated package, audit CLI, and tests.

## Scientific review

### Task Frame

The implemented object is an audit of a fixed set and sealed pool. It does not decide which candidates should be selected.

### Historical Boundary

Gauss and Riemann are historically inspired verification and structural lenses, not literal minds or sources of empirical authority.

### Gauss Pass: Verification

- Strongest claim: legal identity, duplicate boundaries, exact null probabilities, digest integrity, and read-only database behavior are executable and tested.
- Weakest assumption: Monte Carlo z values depend on finite replicate counts; smoke z values are not final inference.
- Test for the structural lens: verify that pair/triple coverage and entropy add information beyond average overlap.
- Boundary note: the executable probability and artifact machinery is modern.

### Riemann Pass: Structure

- Strongest claim: the artifact preserves several coordinates of portfolio geometry instead of collapsing diversity to one threshold.
- Weakest assumption: these coordinates may still miss the candidate families relevant to future selectors.
- Test for the verification lens: require future selectors to improve preregistered outcomes, not merely these geometry coordinates.
- Boundary note: clustering, entropy, and candidate-space geometry are later mathematical tools.

### Cross-review and synthesis

The smallest shared conclusion is that the audit boundary is sufficient to expose compression and compare set geometry reproducibly. It is not sufficient to recommend a selector. The next accepted step is to regenerate all 12 retained snapshot artifacts from the clean merged commit, then implement the four selectors behind `RESEARCH_ONLY` with exact `score_topk` parity.

## Round decision

- Read-only audit implementation: ready for review.
- Production TopK: unchanged.
- Selector evidence: not started.
- Promotion: prohibited.
- Next round: formal 12-snapshot audit, followed by isolated selector backends.
