# Candidate Portfolio Formal Snapshot Audit v1

- Date: 2026-07-22
- Role: Engineering Agent
- Evidence level: `RESEARCH_ONLY_DIAGNOSTIC`
- Audit implementation commit: `208f1e8ef8fc4e5a3a56832b7587696c9b985a26`
- Production TopK change: none

## Round contract

### Primary goal

Regenerate the preregistered portfolio geometry audit for all 12 retained forward-prediction snapshots from the clean merged audit implementation, then answer the portfolio-compression questions using reproducible evidence.

### Non-goals

- no selector implementation or execution;
- no production reducer, scoring, ranking, training, persistence, API, or dashboard change;
- no overlap threshold or post-hoc diversity rule;
- no claim that geometry alone improves red4+ outcomes;
- no promotion or production replacement decision.

## Reproducibility contract

Every snapshot used:

- selected budget: Top100;
- sealed comparison pool: Top10K from the same durable prediction run;
- master seed: `20260722`;
- `uniform_legal_same_budget`: 500 replicates;
- `random_from_candidate_pool`: 500 replicates;
- exact score comparator: same-pool `score_topk`;
- artifact protocol: `candidate_portfolio_audit.v1`;
- metric protocol: `candidate_portfolio_metrics.v1`;
- null protocol: `candidate_portfolio_nulls.v1`.

All 12 artifacts passed the independent artifact verifier. All record the merged audit commit above. The runtime JSON files remain under ignored `data/output/portfolio-audit/formal-208f1e8/`; this report is the retained source evidence.

Database counts after the audit were unchanged:

```text
forward_prediction_runs:          12
forward_prediction_candidates: 120000
training_next_candidates_current: 30000
```

## Snapshot results

`ESS3` and `ESS4` are variance-equivalent ticket counts for the named red3+ and red4+ events under the uniform legal draw null. They are not universal counts of independent predictions.

| Target | Line | Mean overlap | Max number | Pair coverage | Triple coverage | ESS3 | ESS4 | Dominant pair | Dominant triple |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 2026081 | static_100 | 2.226 | 23: 73% | 47.73% | 13.16% | 8.40 | 18.73 | 2-23: 71% | 2-23-25: 36% |
| 2026081 | dynamic_kdj | 2.336 | 23: 77% | 46.02% | 12.77% | 7.71 | 17.33 | 2-23: 75% | 2-23-25: 42% |
| 2026081 | dynamic_kdj_near | 2.587 | 13: 82% | 38.64% | 11.44% | 6.22 | 13.29 | 13-23: 64% | 13-23-33: 41% |
| 2026082 | static_100 | 2.554 | 9: 86% | 41.67% | 11.33% | 6.70 | 15.12 | 9-13: 57% | 7-9-13: 39% |
| 2026082 | dynamic_kdj | 2.676 | 9: 88% | 41.29% | 11.31% | 6.27 | 14.60 | 9-13: 61% | 7-9-13: 37% |
| 2026082 | dynamic_kdj_near | 2.786 | 9: 93% | 40.15% | 10.91% | 5.99 | 14.57 | 9-13: 72% | 9-13-22: 37% |
| 2026083 | static_100 | 2.845 | 13: 91% | 36.17% | 10.03% | 5.57 | 12.73 | 4-13 / 13-23: 63% | 4-13-23: 42% |
| 2026083 | dynamic_kdj | 2.352 | 13: 74% | 40.34% | 11.29% | 7.62 | 16.89 | 13-23: 46% | 2-13-23: 30% |
| 2026083 | dynamic_kdj_near | 2.066 | 17: 57% | 39.39% | 12.10% | 9.47 | 20.07 | 2-23: 39% | 2-7-23 / 2-17-23: 23% |
| 2026084 | static_100 | 2.580 | 16: 90% | 42.42% | 11.90% | 6.78 | 16.08 | 16-33: 67% | 9-16-33: 38% |
| 2026084 | dynamic_kdj | 2.534 | 16: 82% | 41.67% | 11.53% | 6.96 | 16.36 | 16-33: 60% | 9-16-33: 35% |
| 2026084 | dynamic_kdj_near | 2.551 | 16: 86% | 41.67% | 11.62% | 6.85 | 16.18 | 16-33: 68% | 16-26-33: 35% |

All 12 score-retention ratios versus the exact same-pool `score_topk` comparator are `1.0`. This confirms the audited sets are the current scalar TopK outputs, not a hidden portfolio selector.

## Is compression persistent?

Yes, descriptively and against both declared nulls.

Across all 12 Top100 snapshots:

- mean pair overlap ranges from 2.066 to 2.845, versus the analytic uniform-ticket expectation `36/33 = 1.091`;
- maximum single-number exposure ranges from 57% to 93%;
- legal pair coverage ranges from 36.17% to 47.73%;
- legal triple coverage ranges from 10.03% to 13.16%;
- red3+ ESS ranges from 5.57 to 9.47 out of 100;
- red4+ ESS ranges from 12.73 to 20.07 out of 100.

Monte Carlo standardized deviations are extreme in every snapshot:

| Comparison | Mean-overlap z range | Pair-coverage z range | Triple-coverage z range |
| --- | ---: | ---: | ---: |
| Uniform legal same budget | +79.09 to +142.25 | -54.76 to -43.90 | -58.92 to -50.02 |
| Random from same sealed Top10K | +21.01 to +36.94 | -20.81 to -17.16 | -26.44 to -21.67 |

These z values summarize finite Monte Carlo null distributions; they are not reported as calibrated p-values. Their useful conclusion is qualitative and robust: compression is not confined to one issue, one product line, or only to the scoring pool itself. The final scalar Top100 step intensifies compression relative to random coverage from the same Top10K pool.

## Current effective independent bets

For target 2026084, each nominal Top100 behaves under the declared event null like only:

- 6.78 to 6.96 variance-equivalent tickets for red3+;
- 16.08 to 16.36 variance-equivalent tickets for red4+.

The three product lines are also highly redundant with one another:

| Pair of Top100 lines | Exact shared combinations |
| --- | ---: |
| dynamic_kdj / dynamic_kdj_near | 79 |
| dynamic_kdj / static_100 | 83 |
| dynamic_kdj_near / static_100 | 71 |

There are 68 combinations shared by all three lists. The nominal 300 rows contain only 135 unique combinations. After exact deduplication, the 135-ticket union still has mean overlap 2.452, 84.44% exposure to number 16, and only 7.57 red3+ / 18.68 red4+ ESS. Its dominant pair is 16-33 in 61.48% of tickets and dominant triple is 16-26-33 in 32.59%.

Therefore “300 recommendations” must not be interpreted as 300 independent bets. Even “135 unique combinations” materially overstates the event-specific variance-equivalent coverage.

## Dominant cores and persistence

The dominant core changes with the issue, while all three product lines usually converge on the same issue-specific family:

- 2026081: numbers 23/13, especially pairs 2-23 or 13-23;
- 2026082: number 9 and pair 9-13 across all three lines;
- 2026083: a broader but still 13/23-centered family, with static_100 especially compressed;
- 2026084: number 16 and pair 16-33 across all three lines.

This is family collapse rather than one globally fixed “hot number.” A simple permanent ban or overlap threshold would therefore treat the symptom, could discard score information arbitrarily, and would not establish predictive benefit.

## Does diversity improve red4+ probability?

Unknown. This audit measures dependence and coverage under explicit nulls; it does not estimate predictive lift.

Only three retained target issues are evaluated, and there is no preregistered diversified selector comparator. Geometry can establish that the current nominal ticket count exaggerates independent coverage, but it cannot prove that a more diverse portfolio improves realized red4+ probability. Any such claim before strict walk-forward comparison would be post-hoc.

The required next evidence is a sealed-pool, issue-by-issue walk-forward comparison of `score_topk`, `random_from_top_pool`, `greedy_score_diversity`, and `cluster_quota`, with selector parameters fitted only on prior issues and red4+ portfolio-hit confidence intervals/bootstrap reported against the same baselines.

## Should controlled random coverage be used if no signal is provable?

As a research fail-closed comparator: yes. If strict walk-forward cannot show a reproducible score or selector advantage over null coverage, controlled seeded sampling from a sealed eligible pool is the scientifically defensible coverage baseline. It makes the absence of proved ranking signal explicit and avoids pretending that scalar rank differences justify severe concentration.

As a production replacement today: no authorization. The historical outcome window is too small, the selector experiment has not run, and the Promotion Gate remains authoritative. The controlled-random policy must preserve eligibility constraints, use a committed seed and pool digest, report score-retention cost, and remain `RESEARCH_ONLY` until outcome evidence and operational review pass.

## Provenance and fail-closed status

- Nine snapshots are fully `audited` under the v1 provenance contract.
- The three 2026081 snapshots are `audited_with_provenance_gaps` because their legacy metadata lacks `scoring_contract` and `source_code_commit`.
- Their descriptive geometry remains reproducible from sealed candidate rows, but they are ineligible for automatic promotion evidence.

## Content digests

| Target | Line | Content digest |
| --- | --- | --- |
| 2026081 | static_100 | `83c58f69727a9dd1dcb1ff0da648fc84f8ff30777bfeed8dbfb6d31d19bf79be` |
| 2026081 | dynamic_kdj | `38840f864c45a8548b52202e3da8c10d1452a1a43ae4f4c05b8551708d1d697c` |
| 2026081 | dynamic_kdj_near | `877cb1b25e62c41ac843d54764850979ea6d4b0ceac973aad68619d51a6bf1bf` |
| 2026082 | static_100 | `617a48aba6af89da39e7c521273eab8db0eac15505bf7b55b6d99b646a8c3a7f` |
| 2026082 | dynamic_kdj | `c63a6eca8fee8c8794fe7ab21d5a8d3f30cc8fd9b6abc32cd3e4d52d0336c484` |
| 2026082 | dynamic_kdj_near | `701300a00fa4998f5db654065e8534eacc5169208792bf60a297f0662dd95193` |
| 2026083 | static_100 | `2c99802fc87b555940dccb7296bfa251de5882bb8cd91691f45291cb88987c9b` |
| 2026083 | dynamic_kdj | `098337f640cdb8f21764d47e654c171aa3a2c0e40a15739f945d7035c0ee120b` |
| 2026083 | dynamic_kdj_near | `9294267f4516b3f5627457186de8aa48f1fb7f51576095ca74041e570ceb3614` |
| 2026084 | static_100 | `1774cfc3dbd5e7db0dec31b70601fcd9d354fed06a917b2f6c5b737af84627a4` |
| 2026084 | dynamic_kdj | `60fb81dfe325dfc5978f3495fadeebfedc9ae1d6d2596086f05c23b7f6c1b0b7` |
| 2026084 | dynamic_kdj_near | `3ce0765691aad608dac16717375831daf0ed855ac6a71f6256539ddfc7d97793` |

## Scientific cross-review

### Gauss pass: verification

- Strongest claim: all 12 sets are exact score TopK and all 12 are compressed relative to both declared nulls.
- Weakest assumption: ESS is event- and null-specific; it must not be marketed as literal independent ticket count.
- Structural test requested: determine whether alternative selectors improve realized red4+ portfolio hits rather than only geometry.

### Riemann pass: structure

- Strongest claim: collapse follows moving candidate families, and cross-line lists largely occupy the same local region of candidate space.
- Weakest assumption: pair/triple coordinates may not capture every predictive neighborhood relevant to outcomes.
- Verification test requested: compare multiple selector geometries under one sealed walk-forward protocol and identical candidate pools.

### Synthesis

The smallest shared conclusion is that current Top100 lists are persistently and materially redundant, including across product lines. This proves a portfolio architecture problem under a coverage objective, but not a predictive advantage for any replacement selector. The next round may implement the four preregistered selectors behind an isolated `RESEARCH_ONLY` interface; it may not change production TopK.

## Round decision

- Compression persistence: established descriptively across all 12 retained snapshots.
- Current effective coverage: materially below nominal Top100/Top300 counts.
- Predictive diversity lift: unproven.
- Controlled random coverage: approved only as a research null/fail-closed comparator.
- Production promotion: prohibited.
