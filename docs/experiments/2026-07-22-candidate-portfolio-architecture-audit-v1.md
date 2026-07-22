# Candidate Portfolio Architecture Audit v1

- Date: 2026-07-22
- Repository commit audited: `7a5b9514dd6cb850736053bc4e259926f67cdbb2`
- Status: architecture audit and experiment preregistration draft complete
- Evidence level: `RESEARCH_ONLY`
- Production selector change: none

## Round contract

### Primary goal

Separate the existing scalar score/rank boundary from a future fixed-budget portfolio decision boundary, and define the smallest falsifiable experiment that can determine whether portfolio selection improves decision quality.

### Non-goals

- Do not change static, dynamic KDJ, near-dynamic KDJ, forward-promotion, API, dashboard, or notification output.
- Do not add an overlap threshold or any other production deduplication rule.
- Do not change Feature weights, scoring formulas, ranking contracts, candidate ABI, or the Promotion Gate.
- Do not claim that diversity improves hits, prize return, or future prediction quality before paired walk-forward evidence exists.
- Do not implement the selector or audit CLI in this architecture-only round.

## Executive finding

The current production boundary is a deterministic scalar-score TopK, not a 100-ticket portfolio decision.

All three published lines use the same ranking primitive:

```text
history/config
  -> score every candidate independently
  -> order by score descending, candidate id ascending
  -> retain Top N
  -> persist ranks
  -> UI/mail take the first 100
```

No component in that path evaluates the marginal value of adding a ticket to an already selected set. There is no portfolio utility, exposure budget, pair/triple coverage objective, cluster quota, or risk constraint. The dynamic lines change the scalar score configuration before ranking; they do not change the selection rule after scoring.

The retained evidence also shows material candidate compression. Across the 12 durable Top100 snapshots available for issues `2026081` through `2026084`, average ticket overlap ranges from `2.066` to `2.845` red balls. A same-budget uniform legal baseline has mean `1.090` and P95 `1.110`. Every retained snapshot is beyond that baseline P95. Pair coverage is only `36.2%` to `47.7%`, versus a baseline P05 of `92.8%`; triple coverage is `10.0%` to `13.2%`, versus a baseline P05 of `30.1%`.

This proves repeated compression in the short retained window. It does **not** prove a long-term condition, because only four target issues retain complete candidate rows. It also does not prove that a diversified selector would improve 4+ red outcomes: no such selector has yet been evaluated on matched candidate pools.

## Evidence boundary

### Code and data inspected

- Legal red-ball universe: `C(33,6) = 1,107,568`.
- Canonical history: 3,480 issues, `2003001` through `2026083`, latest draw date `2026-07-21`.
- Durable candidate evidence: 12 Top10K forward snapshots, three lines for each of `2026081` through `2026084`.
- Evaluated forward evidence: three completed issues, `2026081` through `2026083`; `2026084` is pending.
- Current published rows and historical durable rows are stored in `training_next_candidates_current`, `forward_prediction_runs`, and `forward_prediction_candidates`.

### Read-only audit calculation used for this report

The metrics below were computed without modifying repository files, database rows, or runtime state. The provisional uniform baseline used:

- budget: 100 distinct legal red-ball tickets;
- sampling: uniform without replacement inside each ticket and no duplicate ticket inside a portfolio;
- seed: `20260722`;
- replicates: 200;
- role: diagnostic baseline only, not promotion evidence.

The final audit tool must increase the replicate count, emit a durable artifact, include implementation/library versions, and verify its own digest. These provisional results are sufficient to identify a large architectural mismatch, not to accept a strategy.

## Complete current call chain

### Entry points

The scheduled and manual paths converge at the same functions:

- `scripts/daily_pipeline.py` requests `top_n=10000` and calls `refresh_training_prediction_lines_current`.
- `scripts/generate_training_next_candidates.py` dispatches to the static, dynamic, near-dynamic, or all-lines refresh function.

### Static line

```text
refresh_training_next_candidates_current
  -> build_training_next_candidate_snapshot
  -> load_best_training_summary
  -> load_current_history_for_training_scope
  -> build_ranked_universe
  -> top_candidates_for_next(top_n)
  -> persist snapshot
```

`build_training_next_candidate_snapshot` calls `top_candidates_for_next` once with the selected scalar `FrequencyRankerConfig`. The returned ordered list becomes the published candidate list without a set-level transformation.

### Dynamic KDJ line

```text
refresh_dynamic_kdj_next_candidates_current
  -> build_dynamic_kdj_next_candidate_snapshot
  -> load base config and historical KDJ signals
  -> dynamic_kdj_config_for_next
  -> top_candidates_for_next(top_n, dynamic_config)
  -> persist snapshot
```

The dynamic line modifies weights before scoring. Its final reducer is identical to the static line.

### Near-dynamic KDJ line

```text
refresh_near_dynamic_kdj_next_candidates_current
  -> build_near_dynamic_kdj_next_candidate_snapshot
  -> build_dynamic_kdj_next_candidate_snapshot
       with rolling train mode and a nine-issue regression window
  -> top_candidates_for_next(top_n, dynamic_config)
  -> persist snapshot
```

The near-dynamic line changes the training scope and metadata. It does not introduce a portfolio selector.

### Shared scoring and TopK reducer

`dehps.optimization.walk_forward.top_candidates_for_next` calls `_kernel_score_rank(..., top_k=top_n)`. The NumPy scoring backend streams score tiles into `TopKReducer`. `ordered_topk` defines the complete selection rule:

1. larger scalar score first;
2. smaller candidate id first when scores tie.

The reducer sees candidate ids and scalar scores only. It has no access to a selected-set state or a portfolio objective. Candidate id is a deterministic tie-break, not a diversity term.

### Persistence and presentation

`replace_training_next_candidates_current` persists the full ranked list into both the durable forward tables and the current projection. The API queries by rank and the web client slices the first requested rows. There is no portfolio selection in storage, API, dashboard, copy, export, mail, or evaluation code.

### Existing diagnostics do not alter selection

`candidate_space_diagnostic` is observational only. It examines the first 100 candidates, but its average overlap uses only the first 50. It reports duplicates, unique red numbers, positional variety, mean overlap, and max overlap. Its current fixed flags are:

- collapsed at mean overlap `>= 4.25`;
- narrow at mean overlap `>= 3.75`.

Those thresholds are not normalized against a same-budget random baseline. Consequently the current `2026084` lines are labeled `diverse` even though their full Top100 mean overlap is `2.534` to `2.580`, more than twice the uniform mean, and their pair/triple coverage is far below the uniform P05. The diagnostic does not feed back into ranking or persistence.

### Existing training objective is candidate-rank oriented

The active `rank_objective_v1` rewards exact target ranks at Top100/1000/10000, red5 ranks, rank bands, and baseline-unique historical hit issues, then penalizes median/worst/tail ranks and hit-issue overlap with control configurations.

The field named `baseline_overlap_penalty` is **not** pairwise overlap among tickets. It penalizes target issues hit by both a candidate configuration and baseline configurations. The objective has no number exposure, ticket overlap, pair/triple coverage, effective-bet count, or portfolio prize term.

## Measured portfolio geometry

### Uniform same-budget reference

| Metric | Mean | P05 | P50 | P95 |
| --- | ---: | ---: | ---: | ---: |
| Average shared reds | 1.090 | 1.075 | 1.089 | 1.110 |
| Maximum number exposure | 26.7% | 24.0% | 26.0% | 30.0% |
| Number HHI | 0.03165 | 0.03122 | 0.03161 | 0.03219 |
| Normalized exposure entropy | 0.9936 | 0.9910 | 0.9938 | 0.9957 |
| Pair coverage | 94.4% | 92.8% | 94.5% | 95.8% |
| Maximum pair concentration | 9.1% | 8.0% | 9.0% | 11.0% |
| Triple coverage | 30.7% | 30.1% | 30.7% | 31.3% |
| Maximum triple concentration | 4.2% | 4.0% | 4.0% | 5.0% |

The analytic expectation for average shared reds between two independently sampled tickets is `6*6/33 = 1.0909`, consistent with the simulation.

### Durable Top100 snapshots

| Issue | Line | Avg overlap | Max exposure | Pair coverage | Triple coverage | ESS red3+ | ESS red4+ |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026081 | dynamic | 2.336 | 77% | 46.0% | 12.8% | 7.7 | 17.3 |
| 2026081 | near | 2.587 | 82% | 38.6% | 11.4% | 6.2 | 13.3 |
| 2026081 | static | 2.226 | 73% | 47.7% | 13.2% | 8.4 | 18.7 |
| 2026082 | dynamic | 2.676 | 88% | 41.3% | 11.3% | 6.3 | 14.6 |
| 2026082 | near | 2.786 | 93% | 40.2% | 10.9% | 6.0 | 14.6 |
| 2026082 | static | 2.554 | 86% | 41.7% | 11.3% | 6.7 | 15.1 |
| 2026083 | dynamic | 2.352 | 74% | 40.3% | 11.3% | 7.6 | 16.9 |
| 2026083 | near | 2.066 | 57% | 39.4% | 12.1% | 9.5 | 20.1 |
| 2026083 | static | 2.845 | 91% | 36.2% | 10.0% | 5.6 | 12.7 |
| 2026084 | dynamic | 2.534 | 82% | 41.7% | 11.5% | 7.0 | 16.4 |
| 2026084 | near | 2.551 | 86% | 41.7% | 11.6% | 6.9 | 16.2 |
| 2026084 | static | 2.580 | 90% | 42.4% | 11.9% | 6.8 | 16.1 |

For all 12 snapshots, overlap P90 is 4 and maximum pair overlap is 5. There are no duplicate tickets in these Top100 sets, so uniqueness alone would incorrectly report 100 independent decisions.

### Effective independent betting count

There is no event-independent scalar definition of “equivalent independent bets.” This report uses an explicit event definition under the uniform legal draw null.

For threshold `k`, let `I_i(k)` indicate that ticket `i` matches at least `k` red balls. For each ticket pair, exact correlation is calculated from its shared-red count by enumerating the four disjoint number regions. The diagnostic effective sample size is:

```text
ESS_k = B / (1 + (B - 1) * mean_pair_correlation(I_i(k), I_j(k)))
```

For the current `2026084` Top100 portfolios:

- red3+ ESS is approximately `6.8` to `7.0`;
- red4+ ESS is approximately `16.1` to `16.4`.

These are event-specific variance-equivalent counts under the null, not a claim that only that many rows exist or that winning probability equals an independent sample of that exact size. The audit artifact must always publish the threshold and formula next to ESS.

### Persistent dominant exposures in the retained window

Each line has four snapshots and 400 Top100 ticket rows. Uniform per-ticket exposure expectations are `18.18%` for one number, `2.84%` for one pair, and `0.367%` for one triple.

| Line | Leading numbers | Leading pair | Leading triple |
| --- | --- | --- | --- |
| static | 9: 46.5%, 23: 46.3%, 13: 45.8% | (2,23): 32.0% | (2,13,23): 18.5% |
| dynamic | 9: 46.8%, 23: 44.3%, 13: 42.3% | (2,23): 34.5% | (2,13,23): 18.0% |
| near | 9: 41.8%, 13: 41.0%, 33: 41.0% | (16,33): 21.8% | (16,26,33): 11.8% |

These are descriptive frequencies over a short, changing-model window. They identify which templates dominated retained portfolios; they do not establish that those numbers or templates have predictive meaning.

### Completed forward outcomes

| Issue | Line | Max reds | red3+ tickets | red4+ tickets |
| --- | --- | ---: | ---: | ---: |
| 2026081 | dynamic | 4 | 10 | 1 |
| 2026081 | near | 3 | 3 | 0 |
| 2026081 | static | 4 | 7 | 2 |
| 2026082 | all three | 2 | 0 | 0 |
| 2026083 | dynamic | 3 | 3 | 0 |
| 2026083 | near | 3 | 10 | 0 |
| 2026083 | static | 3 | 1 | 0 |

Three completed issues cannot distinguish signal, portfolio geometry, and chance. More importantly, all rows above are `score_topk`; no diversity-constrained counterfactual exists on the same candidate pools. Therefore the repository currently has no evidence that diversity constraints improve the probability of 4+ red outcomes.

## Proposed read-only audit contract

The next implementation round should add a side-effect-free module and CLI. It may read a sealed candidate artifact, a durable prediction run, or a JSON/CSV candidate list. It must not update a prediction, rank, selector status, hypothesis, or Promotion Gate.

### Proposed package boundary

```text
dehps/portfolio/
  models.py          immutable request/result types
  audit.py           portfolio metrics and null comparison
  selectors.py       PortfolioSelector protocol
  score_topk.py      exact current baseline
  random_pool.py     seeded random-from-pool baseline
  greedy.py          explicit utility research backend
  cluster_quota.py   deterministic clustered research backend
  artifact.py        canonical digests and JSON report

scripts/audit_candidate_portfolio.py
scripts/run_candidate_portfolio_walk_forward.py
```

The first implementation PR should contain only `models.py`, `audit.py`, `artifact.py`, the audit CLI, and critical tests. Selector execution and walk-forward belong to later reviewable rounds.

### Required audit inputs

- legal universe manifest and candidate contract;
- ordered candidate rows with canonical `lex_id`, red numbers, scalar score, and source rank;
- budget and optional rank cutoff;
- history cutoff/as-of issue when the source is historical;
- candidate-pool digest and score/config digest;
- null model specification, replicate count, and seed manifest.

### Required outputs

- legal/unique/duplicate counts and rejected rows;
- number occurrence counts and per-ticket exposure rates;
- all-pairs overlap mean, P50, P90, and maximum;
- unique pair and triple counts, legal-universe coverage, and attainable-budget coverage;
- maximum pair and triple concentration with all tied cores;
- number HHI, normalized Shannon entropy, and effective exposed-number count;
- event-specific ESS for red3+ and red4+ with formula/version;
- standardized deviations and empirical intervals versus:
  - uniform legal same-budget portfolios;
  - random same-budget samples from the sealed candidate pool;
- source score mean/quantiles and score-retention ratio versus `score_topk`;
- full provenance and failure status.

### Fail-closed audit checks

The artifact must be invalid when any of these occur:

- illegal or noncanonical candidate;
- duplicate candidate id or combination;
- non-finite score;
- row count below budget;
- source rank or score order inconsistent with its declared contract;
- digest mismatch;
- missing seed for a stochastic null;
- history cutoff later than or equal to the evaluated target issue;
- parser/sync conflict in the target history.

## PortfolioSelector interface design

The selector consumes a sealed scored pool and returns a new ordered portfolio artifact. It does not score candidates and does not write production state.

```python
@dataclass(frozen=True)
class ScoredCandidate:
    lex_id: int
    red_numbers: tuple[int, ...]
    score: float
    source_rank: int

@dataclass(frozen=True)
class PortfolioRequest:
    candidates: tuple[ScoredCandidate, ...]
    budget: int
    selector_key: str
    selector_config: Mapping[str, JSONValue]
    candidate_pool_digest: str
    history_digest: str
    score_config_digest: str
    seed: int | None

@dataclass(frozen=True)
class PortfolioSelection:
    selected: tuple[ScoredCandidate, ...]
    selector_key: str
    selector_config_digest: str
    portfolio_digest: str
    audit: PortfolioAudit
    provenance: PortfolioProvenance

class PortfolioSelector(Protocol):
    def select(self, request: PortfolioRequest) -> PortfolioSelection: ...
```

### Interface invariants

- `budget >= 1` and `budget <= len(pool)`.
- Pool rows are unique, legal, canonical, finite-scored, and source-ranked.
- Output is a subset of the input pool with exactly `budget` unique rows.
- The selector cannot read outcomes, target draws, post-target history, or mutable global randomness.
- Equal request bytes, code commit, and dependency manifest produce the same output.
- Every stochastic backend requires a derived recorded seed.
- Selection order records marginal choice order; presentation may separately sort by source score.

## Four research backends

### 1. `score_topk`

Exact control backend. Return the first `budget` rows ordered by scalar score descending and `lex_id` ascending. Its output must match the current reducer byte-for-byte for the same sealed pool.

### 2. `random_from_top_pool`

Uniformly sample `budget` distinct rows from the same sealed Top10K pool. The seed is mandatory and derived from a master seed plus issue, line, pool digest, selector-config digest, budget, and replicate id. Store both master and derived seeds, RNG algorithm, and library version.

This baseline answers whether selection inside the scored pool adds value. A separate non-deployable `uniform_random_legal` null is still required to answer whether the scored pool itself adds value over the legal universe.

### 3. `greedy_score_diversity`

This backend must maximize an explicit set utility, not apply a fixed overlap threshold.

For final budget `B`, candidate-pool rank percentile `q(c) in [0,1]`, and selected set `S`:

```text
U(S) = alpha * Q(S)
     - lambda * R(S)
     - nu * E(S)
     + mu2 * C2(S)
     + mu3 * C3(S)

Q(S)  = sum(q(c) for c in S) / B
R(S)  = sum(choose(|a intersect b|, 2) / 15 for a<b in S) / choose(B, 2)
E(S)  = (sum((count_n(S)/(6B))^2 for n=1..33) - 1/33) / (1 - 1/33)
C2(S) = unique_pairs(S)   / min(15B, choose(33,2))
C3(S) = unique_triples(S) / min(20B, choose(33,3))
```

The selector greedily adds the candidate with the largest exact marginal `Delta U`, breaking ties by higher `q(c)` and then lower `lex_id`.

Properties of this definition:

- score scale is normalized inside the sealed pool;
- redundancy is continuous and convex in shared pairs, with no skip threshold;
- number concentration is penalized separately from ticket overlap;
- pair and triple coverage receive explicit rewards;
- every coefficient (`alpha`, `lambda`, `nu`, `mu2`, `mu3`) is a required research parameter;
- there are no production defaults and no coefficient may be selected on an outer evaluation window.

The exact formula remains a research hypothesis. It is not endorsed until inner-window tuning and outer-window rejection tests are complete.

### 4. `cluster_quota`

Represent each candidate as a 33-dimensional binary vector and cluster the sealed pool using Jaccard distance. Cluster count, medoid initialization, quota mode, and within-cluster selection rule are explicit research parameters. The initial control should use deterministic k-medoids and either equal or preregistered size-proportional quotas; ties resolve by score and `lex_id`.

Clustering may use only candidate geometry and pre-target scores. It may not use the target draw or outer-window performance. Empty/undersized clusters redistribute quota by a declared deterministic rule and record the redistribution.

## Walk-forward experiment plan

### Core question

Given the same pre-target scored Top10K pool and the same ticket budget, does a portfolio selector improve issue-level 4+ red decision outcomes and risk-adjusted return relative to both scalar `score_topk` and random selection, without merely discarding model score for cosmetic dispersion?

### Invariants

- Every legal six-red combination is equiprobable under the mathematical draw null.
- All selectors for `(line, target issue)` receive identical sealed pool rows and scores.
- Target issue `t` is unavailable to model fitting, pool construction, selector tuning, and seed derivation.
- Budget, blue allocation, cost, and candidate pool are identical across compared selectors.
- Selector hyperparameters are chosen only in an inner historical window.

### Hypotheses

- `H0`: conditional on the same candidate pool and budget, the challenger does not improve the preregistered issue-level primary metric versus `score_topk` and `random_from_top_pool`.
- `H1`: a challenger improves the primary metric against both controls, preserves preregistered worst-window non-inferiority, and passes score-retention and leakage checks.

Historical lift is evidence for or against these hypotheses, not proof of a future edge.

### Evaluation units and windows

Use the issue as the statistical unit, never individual tickets. Tickets inside one portfolio are dependent.

Two evidence lanes are required:

1. **Retrospective nested walk-forward**: for each outer target issue, recreate the model/config using only earlier data and inner validation, seal one shared Top10K pool, then run every selector. Reusing today's best config across earlier targets is prohibited.
2. **Prospective shadow**: apply frozen selector configs to future sealed production pools before the draws, with no updates based on pending results.

Preregister `B=100` as the primary budget. Budgets `20`, `50`, and `200` are secondary sensitivity analyses and share the same pool for each issue. A short 60-issue run may validate runtime and artifacts but is not inferential. The primary retrospective window should contain at least 300 eligible outer issues after the required training burn-in. If historical model artifacts cannot be reconstructed without future information, mark those issues unavailable rather than approximating them.

### Controls

- `score_topk` from the shared Top10K pool;
- `random_from_top_pool`, with many seeded replicates per issue;
- `uniform_random_legal`, same budget, as the no-model null;
- the three challenger families/parameter sets selected by inner validation only.

All selectors and controls must use identical eligible issues. Missing one selector for an issue removes that issue from the paired primary comparison and is reported.

### Metrics

Primary metric at `B=100`:

- issue indicator that at least one selected ticket has 4+ red matches.

Required secondary outcome metrics:

- maximum red matches per issue;
- counts of tickets with exactly/at least 3, 4, 5, and 6 red matches;
- Top100 total prize and net return, only when the blue-allocation and payout contract below is valid;
- lift/difference versus both random controls;
- P05, P50, and P95 across issues;
- worst contiguous 30-issue window;
- mean score percentile and score-retention ratio versus `score_topk`.

Required portfolio diagnostics:

- overlap mean/P50/P90/max;
- maximum number exposure;
- number entropy and HHI;
- pair/triple coverage and maximum core concentration;
- red3+ and red4+ ESS.

### Prize and blue-ball blocker

Current candidate rows contain red numbers only, and current evaluation explicitly records `blue_scored=false`. Therefore “Top100 total prize” is not presently reproducible.

Before prize becomes an acceptance metric, freeze a `BlueAllocationContract` containing:

- the pre-draw blue number(s) assigned to every red ticket;
- whether a blue number is shared or budgeted across tickets;
- ticket cost and total budget;
- per-issue official prize schedule and source digest;
- rounding and missing-payout policy.

Every selector must receive the same blue allocation and cost. Until this contract exists, report red-match metrics and mark monetary return `unavailable`; never substitute a post-draw blue number or a made-up fixed payout.

### Hyperparameter isolation

- Tune selector coefficients, cluster count, quotas, and score-retention tradeoffs only in the inner walk-forward window.
- Freeze the chosen config before evaluating the outer issue.
- Count every tried selector config in the multiple-testing ledger.
- Do not select coefficients after inspecting outer 4+ hits, worst windows, or prize returns.
- Use the same pool digest across all configs compared on an outer issue.

### Uncertainty and bootstrap

- Report paired selector-minus-control differences at issue level.
- Use a deterministic moving-block bootstrap over issues to preserve local temporal dependence; preregister the primary block length and run 5/10/20-issue sensitivity checks.
- Use at least 10,000 bootstrap replicates for the final report, with a stored seed manifest.
- Report 95% intervals for the primary difference, mean 3+/4+ counts, prize return when available, score retention, and worst-window difference.
- For rare binary 4+ outcomes, also report exact counts and an interval for each strategy's issue rate; do not rely on asymptotic normality.
- Adjust secondary strategy/budget comparisons with a declared familywise procedure. The single `B=100` primary comparison must be declared before execution.
- Publish all misses and all eligible issues, not only windows where a challenger wins.

### Reproducibility ledger

Every issue/selector artifact must record:

- target issue and as-of issue;
- legal-universe and history digests;
- candidate ABI/package and ordered candidate-pool digests;
- scoring contract, ranking contract, score-config digest, and source run id;
- selector key, canonical selector config, and config digest;
- master seed, derived seed, RNG algorithm/version, and replicate id;
- portfolio digest;
- Git commit, dependency lock digests, and generated timestamp;
- parser, sync, duplicate, leakage, and history-cutoff checks;
- metric protocol version and audit artifact digest.

### Fail-closed state transitions

```text
RESEARCH_ONLY
  -> retrospective evidence accepted
  -> SHADOW_CANDIDATE
  -> at least 30 sealed unseen issues accepted
  -> production-upgrade request
  -> existing Promotion Gate decision
```

Conditions to leave `RESEARCH_ONLY`:

- all contract, digest, parser/sync, duplicate, and leakage checks pass;
- the `B=100` primary paired 95% interval is strictly above zero versus both `score_topk` and `random_from_top_pool`;
- a preregistered worst-window non-inferiority margin is met versus both controls;
- the score-retention floor is met, showing the result is not obtained solely by discarding model score;
- results are not driven by one issue, one window, or one parameter seed;
- monetary claims remain blocked until the blue/payout contract is valid.

The non-inferiority margin and score-retention floor have no default in this document. They must be justified and frozen before the primary run. Absence of either value is a promotion blocker, not permission to choose it post hoc.

Conditions to request production after shadow:

- at least 30 fully sealed, previously unseen eligible issues;
- the same frozen selector config and seed policy throughout the window;
- primary improvement versus both controls with uncertainty;
- no material degradation in preregistered worst-window, cost, latency, or score-retention gates;
- explicit Reviewer and Operator authorization through existing DEHPS governance.

No selector can self-promote, and no historical result may bypass shadow.

## Scientific cross-review

### Task Frame

The object of study is a set of 100 dependent ticket decisions drawn from one scored candidate pool. Progress means proving the current boundary is scalar TopK, quantifying dependence without outcome leakage, and defining a paired experiment that can reject an ineffective portfolio selector.

### Historical Boundary

“Gauss” and “Riemann” below are historically inspired verification and structural lenses, not literal minds or complete reconstructions. Their authority is not evidence.

### Gauss Pass: Verification

- Strongest claim: the reducer is exactly scalar-score ordering with a deterministic candidate-id tie-break; current Top100 dependence is far outside the same-budget uniform reference in every retained snapshot.
- Weakest assumption: event-specific ESS summarizes a complex joint portfolio using mean pair correlation; it is a diagnostic, not a complete probability model.
- Test requested from the structural lens: determine whether overlap is merely a coordinate symptom of a smaller candidate-family geometry.
- Boundary note: exact combinatorial null calculations and audit invariants are modern executable checks expressed through a Gauss-inspired verification stance.

### Riemann Pass: Structure

- Strongest claim: the missing object is the portfolio as a point/set in candidate-family space; optimizing isolated scalar points cannot represent coverage, concentration, or marginal value.
- Weakest assumption: Jaccard/binary-vector geometry may not align with the score model's latent family structure.
- Test requested from the verification lens: compare multiple geometry definitions on frozen pools and reject any that only improve visual dispersion.
- Boundary note: candidate manifolds, clustering algorithms, and submodular language are later mathematical developments, not claims about historical Riemann's complete methods.

### Cross-Review

Gauss rejects “more diverse is better” unless it names a fixed budget, null, outcome, paired window, uncertainty, and failure rule. Riemann rejects a single overlap threshold because it treats one local coordinate as the whole geometry and ignores exposure and family coverage.

### Disagreement

- `definition`: no unique event-independent ESS exists; every report must name the event threshold.
- `method`: the proposed utility geometry is plausible but unverified; other distances or set functions may represent candidate families better.
- `evidence`: four retained portfolio issues establish repetition, not long-term persistence.
- `risk`: coefficient and cluster selection can overfit outer outcomes unless nested and multiplicity-counted.

### Synthesis

The smallest shared conclusion is: add a read-only portfolio audit boundary first, then compare explicit selectors on identical sealed pools in paired nested walk-forward and prospective shadow. Do not patch production TopK and do not treat lower overlap as success by itself.

### Next Verification

1. Implement the read-only audit artifact and validate it against hand-computable portfolios and exact uniform expectations.
2. Reproduce all 12 retained snapshot metrics from durable run ids.
3. Implement `score_topk` parity and seeded `random_from_top_pool` before any challenger.
4. Add the two challengers behind `RESEARCH_ONLY` and verify determinism/digests.
5. Execute the nested walk-forward contract and publish paired uncertainty, misses, and failure cases.

## Answers to the audit questions

### What is the current Top100 effective independent betting count?

It depends on the event. For current issue `2026084`, the variance-equivalent ESS is approximately `6.8-7.0` for red3+ and `16.1-16.4` for red4+ under the uniform legal draw null. Reporting “100 independent predictions” is not defensible; reporting one universal ESS without its event definition is also not defensible.

### Is candidate collapse occasional or long-running?

It recurs in all 12 durable snapshots across four retained issues and three lines. That is evidence of a repeated architectural effect, not an isolated issue. The repository does not retain enough complete older pools to call it long-running; a reconstructed or prospective longer audit is required.

### Which numbers, pairs, and triples dominate?

Over the retained four-issue window, static and dynamic lines are led by numbers `9`, `23`, and `13`, pair `(2,23)`, and triple `(2,13,23)`. The near line is led by `9`, `13`, and `33`, pair `(16,33)`, and triple `(16,26,33)`. These are exposure facts, not predictive endorsements.

### Has diversity improved the probability of 4+ reds?

Unknown. No diversified selector has been run on matched historical pools. The three completed forward issues contain too little evidence and compare only score-TopK variants. Any affirmative claim now would be post-hoc.

### If no predictive signal can be proven, should production fall back to controlled random coverage?

As a fail-closed decision policy, yes: a seeded, auditable, budget-matched controlled-random selector is more honest than presenting highly correlated scalar-score neighbors as 100 independent predictions when neither the scored pool nor portfolio selector beats its null. This is a conditional policy conclusion, not authorization to change production today. The experiment must separately test `random_from_top_pool` and `uniform_random_legal`, then the existing Promotion Gate must decide any production request.

## Round decision

- Architecture audit: accepted as a working diagnosis.
- Portfolio selector design: ready for implementation review, still `RESEARCH_ONLY`.
- Production TopK: unchanged.
- Feature-weight work: should remain lower priority until the read-only audit and matched selector controls exist.
- Next round: implement only the read-only audit artifact/CLI and critical contract tests.
