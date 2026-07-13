# Near-term orthogonal residual score — rejected experiment

## Task frame

- Primary goal: test whether the near-term line should rank with `z(static) + 0.25 * z(dynamic - static residual)` instead of directly reusing the dynamic KDJ score.
- Non-goals: no new feature, candidate filter, KDJ signal, history scope, production snapshot, or supervisor change.
- Claim under test: a trained near-term layer can sustain a short-window hit rate near 30%.
- Metrics are separated into Top100 issue hit rates for red4+, red5+, and exact red6. The phrase “30% hit rate” is not accepted without naming one of these outcomes.

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

Residual red4+ counts by block were `2, 0, 0`; static counts were `3, 0, 4`; shuffled-control counts were `3, 1, 5`. The residual arm lost direction in two blocks and never beat either control overall.

The orthogonalization itself worked: mean pre-projection static/delta correlation was `-0.2321`, while the maximum absolute post-projection static/residual correlation was approximately `2.49e-16`. The failure is predictive, not numerical.

## Same-budget null model

For 100 distinct uniform red-ball combinations from the legal `C(33,6)` sample space, the exact without-replacement probability that at least one ticket overlaps the target by:

- at least four reds is `38.82%`;
- at least five reds is `1.461%`;
- all six reds is `0.00903%`.

Therefore, a claimed 30% Top100 issue hit rate is below the random same-budget baseline if “hit” means red4+. A 30% red5+ or exact rate would be extraordinary, but 27 historical targets are far too few to establish it.

## Gauss pass

- Legal sample space is explicit and the null uses the same 100-ticket budget without replacement.
- No target issue enters its own rolling history or signal set.
- Candidate scores are finite, deterministic, and share the same tie-breaking rule.
- Projection removed the measurable linear duplicate of static score.
- The predeclared strength and acceptance rule were not retuned after seeing results.
- Acceptance failed: residual red4+ did not beat static or shuffled control and lost to static within blocks.

## Riemann pass

The dynamic-minus-static vector is not a stable temporal coordinate merely because it is orthogonal to the static score. Across the candidate space, removing the static tangent exposed a residual whose neighborhood ordering was less coherent than both the original geometry and a shuffled control. The latest 9-issue block was especially destructive: static had four red4+ Top100 issues while the residual arm had none. The near-term representation is therefore framed too weakly: it needs target-conditioned state or feature-group residuals, not a single global score residual.

## Cross-review and disagreement

- Gauss view: reject immediately because the same-budget null and blockwise direction tests fail.
- Riemann view: the negative result is informative about representation; global orthogonalization collapses useful local structure.
- Disagreement: Riemann leaves open whether groupwise or state-conditioned residuals could work; Gauss requires a new predeclared experiment before granting that possibility any predictive status.
- Smallest shared conclusion: do not promote this residual formula and do not tune its strength on these 27 outcomes.

## Decision and next verification

Status: **rejected**. Production near-term scoring remains unchanged.

The reusable scorer and isolated backtest are retained because they enforce leakage checks, exact same-budget baselines, block reporting, and a shuffled-residual control. The next admissible hypothesis should operate on predeclared feature groups or explicit market/temporal states and must be evaluated on untouched forward issues or a new blocked historical interval. It must report red4+, red5+, and exact metrics separately and beat the same-budget null rather than a vague 30% threshold.
