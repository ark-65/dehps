# Prediction learning v1 — first offline round

Goal: `dehps-prediction-learning-v1`. Engineering role, directly authorized by
the user's first-round objective. Formal P3 and V11 are outside execution scope.
Base: main `745a06e250b3048630ec98891d0887922e8ee480`.

## Question and falsifiable claim

Can shrinkage or a predefined temporal marginal estimator reduce chronological
out-of-sample red-number Bernoulli log-loss? The null is legal uniform marginal
6/33; all probability vectors must sum to six. A marginal composite ticket score
does not constitute a learned joint distribution. Historical data has already
been researched: all comparisons here are exploratory, including later years.

The primary new model is expanding marginal counts with 900 prior-equivalent
draws at the uniform marginal. Fixed alternatives: expanding alpha=100,
156-draw window alpha=100, exponential half-life=156 alpha=100. There are four
candidate configurations total; the old alpha=1 estimator and uniform are fixed
controls. No outer-result model selection, calibration, or tuning is permitted.
The final checkpoint uses the predefined alpha=900 model even if it loses.
No nonlinear model is introduced in this first simple-model round.

## Freeze and boundaries

Before evaluating, the runner saves an immutable JSON contract containing the
validated full red/blue data snapshot digest, existing Formal P3 preregistration
and source identities, code digests, exact issue lists, seed=20260905, four
configurations, probes, workers, metrics, random repetitions and stopping rules.
The database is read only for the snapshot. Dates, issue uniqueness, sequential
within-year numbering, legal balls and complete blue labels must validate.
The first 900 draws are warm-up and retain labels with explicit insufficient
history status; no invented old-model forecasts. Every subsequently opened draw
is evaluated chronologically with data strictly before its date and issue.
Historical availability is draw-date availability, not a claim of original
ingestion-time prediction or new confirmatory evidence.

## Comparisons

Reuse the exact old estimator, frozen preregistration, original model artifact
construction, SHA256 legal sampler and shared blue-by-rank algorithm. Baseline
candidate pool is 10,000, top size 100, and lexicographic score ties break by id.
For all red-selection arms use the same blue vector. Compare old/original;
new/original; old/full legal 1,107,568-space top-100; old/original with greedy
number-concentration penalty 0.01 bits per prior occurrence; then the combined
new/full-space and new/full-space with the same diversity selector. The combined
greedy selector uses a declared 10,000 highest-score shortlist, not a claimed
full-space optimization. Exact winning-combination score rank is separately
computed in the full space for old and primary new scores.

Each issue also has 32 equal-budget uniform random red ticket groups with shared
blue and 32 complete random red/blue ticket groups. Repetitions average within
issue; they are not independent historical observations. Seed domains separate
arms, issue and repetition. Costs are 100 x 2 CNY. Returns are simulated gross
pretax prize minus cost; floating first/second prizes require actual issue payout
evidence, never a guessed jackpot. Prize omissions must be explicit.

Primary metric: equal-weight issue average of the 33 per-number log-loss values,
in nats per number per issue, using the canonical metric kernel. Secondary:
fixed calibration bins, coverage, global/local ranks, first rejection stage,
all omitted/extra ball score swaps, overlap and concentration, 0..6 hit counts,
maximum hits, pretax net returns and ROI. Report all candidates and failures.
Paired circular moving-block bootstrap, block length 13, 4,000 resamples,
seed 20260905; 95% intervals and Bonferroni family intervals over eight
candidate-vs-old/uniform primary contrasts. No selection by these results.
Interpret primary improvement only when family interval favors the new model
against both controls; otherwise report no observed improvement or insufficient
evidence according to effect and uncertainty. Never infer ROI gain from loss.
The diagnostic examples are first, middle and last evaluable issue, fixed before
results. Per-issue files retain all probabilities, labels and ticket diagnostics.

## Execution and integration declaration

Use a separate experimental worktree, output root and PostgreSQL database.
No main checkout changes, mail, production dispatch or formal artifact writes.
Existing ResearchEvidenceSupervisor, resolver, Task model and immutable
publication provide the execution path; do not build a competing V12 framework.

| Task | Ready / upstream | Runner | Downstream / consumer |
| --- | --- | --- | --- |
| freeze | validated snapshot + label-blind probe + code identity | experiment capability through ResearchEvidenceSupervisor | frozen experiment contract -> train/evaluate |
| train-evaluate | freeze COMPLETE | same capability; bounded program workers | all immutable issue results, trained checkpoint, resource/attempt ledger -> analysis |
| analysis | train-evaluate COMPLETE | same capability, no refit | paired comparisons, diagnostics, report -> replay/engineering acceptance |
| replay | analysis COMPLETE | same supervisor + deterministic artifact verification | status and honest research decision; no Formal P3 promotion |

Status projection is experiment-local; Evidence remains exploratory with no
Formal P3 gate credit. Next consumer is report/replay and a later explicitly
authorized validation decision. Engineering status must distinguish code from
successful supervisor execution and replay at every stage.

Workers <=8, one BLAS thread each; choose workers from measured memory and
throughput, initially at most four to preserve production headroom. Wall-clock
budget is 24 hours across resumes, no automatic second round. A single run id
and append-only attempt ledger survive restart. Existing immutable issue files
are verified and reused. Program pauses dispatch for a live formal service;
bounded in-flight jobs complete. No repeated training without new work.

Preflight on 2026-09-05: production service last exited 0, timer active/waiting;
Formal 2026103 checkpoint and replay completed, settlement external_wait;
3,499 zhcw draws through 2026102, no missing blue labels. PR420 remains open with
five successful checks. Its diagnostics may inform this implementation without
deploying its unfinished operational path. No historical results were inspected
when defining this contract.
