# Near-term orthogonal residual score — rejected experiment

## Task frame

- Primary goal: test whether the near-term line should rank with `z(static) + 0.25 * z(dynamic - static residual)` instead of directly reusing the dynamic KDJ score.
- Non-goals: no new feature, candidate filter, KDJ signal, history scope, production snapshot, or supervisor change.
- Claim under test: a trained near-term layer can move exact red6 combinations into Top100 often enough to approach a 30% issue hit rate.
- The sole training and acceptance objective is exact red6 rank `<= 100`. Red4+, red5+, and median rank are diagnostics only and cannot select or accept a model.

## Historical boundary and protocol

- As-of issue: `2026079`.
- Evaluation issues: `2026053`–`2026079`, 27 targets in three non-overlapping blocks of 9.
- Each target uses only its preceding rolling 900-draw history.
- The KDJ signal source is the canonical expanding-mode supervisor stream; every eligible signal satisfies `signal issue < target issue`.
- Candidate universe and base configuration are shared by static, original dynamic, residual, and shuffled-residual arms.
- The residual is the centered dynamic-minus-static score after linear projection on standardized static score is removed. The resulting residual is standardized and added with fixed strength `0.25`.
- Negative control: deterministically shuffle the same residual values across candidate combinations before adding them to the static score.
- This was an isolated historical run. No live prediction snapshot was changed.

## Results

| Arm | Red4+ Top100 | Red5+ Top100 | Exact Top100 | Median exact rank | Mean best overlap |
|---|---:|---:|---:|---:|---:|
| Static | 7/27 (25.9%) | 0/27 | 0/27 | 425,858 | 2.889 |
| Original dynamic | 7/27 (25.9%) | 0/27 | 0/27 | 431,753 | 2.852 |
| Orthogonal residual | 2/27 (7.4%) | 0/27 | 0/27 | 473,960 | 2.704 |
| Shuffled residual | 9/27 (33.3%) | 0/27 | 0/27 | 452,959 | 3.148 |

All four arms produced `0/27` exact-red6 Top100 hits, so the residual formula did not improve the primary objective and cannot pass acceptance. Red4+ counts by block are retained only as diagnostics: residual `2, 0, 0`; static `3, 0, 4`; shuffled control `3, 1, 5`.

The orthogonalization itself worked: mean pre-projection static/delta correlation was `-0.2321`, while the maximum absolute post-projection static/residual correlation was approximately `2.49e-16`. The failure is predictive, not numerical.

## Same-budget null model

For 100 distinct uniform red-ball combinations from the legal `C(33,6)` sample space, the exact without-replacement probability that at least one ticket overlaps the target by:

- at least four reds is `38.82%`;
- at least five reds is `1.461%`;
- all six reds is `0.00903%`.

The 30% goal in this project means exact red6 Top100, whose same-budget random probability is about `0.00903%` per issue. It is therefore an extremely strong hypothesis requiring substantial untouched forward evidence. The red4+ baseline explains why red4 diagnostics must never be substituted for the primary target.

## Gauss pass

- Legal sample space is explicit and the null uses the same 100-ticket budget without replacement.
- No target issue enters its own rolling history or signal set.
- Candidate scores are finite, deterministic, and share the same tie-breaking rule.
- Projection removed the measurable linear duplicate of static score.
- The predeclared strength and acceptance rule were not retuned after seeing results.
- Acceptance failed: residual, static, dynamic, and shuffled control all had zero exact-red6 Top100 hits.

## Riemann pass

The dynamic-minus-static vector is not a useful exact-target coordinate merely because it is orthogonal to the static score. All arms remained outside exact Top100 throughout the three blocks. Red4 neighborhood behavior changed, but that local overlap geometry cannot stand in for the exact six-number event. The near-term representation is therefore too weak for its declared target and needs target-conditioned state or feature-group residuals, not a single global score residual.

## Cross-review and disagreement

- Gauss view: reject immediately because there is no exact Top100 improvement over either baseline or control.
- Riemann view: the negative result is informative about representation; global orthogonalization collapses useful local structure.
- Disagreement: Riemann leaves open whether groupwise or state-conditioned residuals could work; Gauss requires a new predeclared experiment before granting that possibility any predictive status.
- Smallest shared conclusion: do not promote this residual formula and do not tune its strength on these 27 outcomes.

## Decision and next verification

Status: **rejected**. Production near-term scoring remains unchanged.

The reusable scorer and isolated backtest are retained because they enforce leakage checks, exact same-budget baselines, block reporting, and a shuffled-residual control. The next admissible hypothesis should operate on predeclared feature groups or explicit market/temporal states and must be evaluated on untouched forward issues or a new blocked historical interval. Exact red6 Top100 remains the sole acceptance target; red4 and red5 remain diagnostics.
