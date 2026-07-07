# Self-Iteration Report: Rank Homogeneity Diagnostic

## Primary goal

Record a conservative operational diagnosis for the active training watch alert:
high stagnation, rank-homogeneity cycling, and a restart recommendation that is
blocked by a fresh continuous training-supervisor lock.

## Non-goals

- Do not change training, advisor, search, promotion, scoring, dynamic-weight,
  candidate-source, or supervisor logic.
- Do not stop, transfer, replace, or restart the live supervisor process.
- Do not promote any prediction, betting, or strategy-performance claim.
- Do not commit generated artifacts under `data/output` or runtime state.

## Initial status

The working tree was clean before exploration. The first required training watch
command completed successfully:

```bash
apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5
```

Observed watch state:

- run id: `20260707-100454`
- round count: `279` at watch generation, with supervisor progress later
  reporting round `280+`
- severity: `alert`
- action: `prepare_restart_with_more_exploration`
- promotion gate: `frozen_validation_not_better`
- rank homogeneity: `stale_rank_signature_cycle`,
  `unique_signature_count=1`
- restart champion: `rank_homogeneity_restart_changed_rank_vector`,
  `rank_vector_changed=True`, `changed_target_count=28`,
  `full_eval_rank=9`
- decision round best: incumbent retained because frozen-primary lift is
  required
- restart readiness: not ready, blocked by `active_training_supervisor_lock`
- active lock: owner `training-supervisor`, PID `2284647`, heartbeat fresh
- supervisor mode: `continuous`, progress fresh, target progress `28 / 28`

Latest supervisor artifacts inspected:

- `data/output/optimization/training-supervisor-20260707-100454.json`
- `data/output/optimization/training-supervisor-20260707-100454.md`
- `data/output/optimization/training-watch/training-watch-20260707-100454-20260707-080039.md`

## Evidence context

- Evidence level: `operational_training_diagnostic_no_predictive_claim`.
- Legal sample space: `ssq_red_ball_combinations`.
- Legal universe: `1107568`; ranked universe: `1105506`; excluded:
  `2062`.
- Historical window: `current_regime_default`, expanding train mode,
  train window `900`, eval window `28`, target issues `2026049` through
  `2026076`, top-N `10000`.
- Operational baseline: incumbent frozen-primary baseline with baseline score
  `[0, 0, 1]`.
- Random null model: `ranked_uniform_per_draw`, estimated over the ranked
  post-filter universe.
- Leakage and data checks reported by the watcher: parser/sync duplicate checks
  passed, history duplicate checks passed, universe duplicate/invalid checks
  passed, latest sync status `success`, and no recorded sync conflicts.
- Uncertainty: frozen validation can remain at baseline even when eval-slice
  metrics look strong.
- Failure modes reported: `promotion_gate:frozen_validation_not_better`,
  `rank_homogeneity:stale_rank_signature_cycle`, and a blocked
  `rank_homogeneity_restart` candidate.

## Gauss/Riemann diagnostic

Task Frame: the object is an operational training decision under an active watch
alert, not a prediction claim. Progress means a defensible next action for the
current run without weakening frozen validation, baseline/null-model, or leakage
controls.

Historical Boundary: Gauss and Riemann are used here as historically inspired
verification and structure lenses. They are not literal minds, authorities, or
complete reconstructions.

Gauss Pass: Verification:

- Strongest claim: the watcher correctly refuses promotion because the candidate
  has not beaten the incumbent on frozen-primary evidence.
- Weakest assumption: the live status artifacts are fresh enough to represent
  the current run. The inspected heartbeat/progress ages support that assumption
  for this diagnostic snapshot.
- Check for the other lens: explain whether a rank-vector change across all
  targets is structural exploration or only local movement that still fails the
  frozen gate.
- Boundary note: this is Gauss-inspired operational verification, not historical
  authority. Eval-slice lift, rank movement, or elegance is not proof.

Riemann Pass: Structure:

- Strongest claim: the search space is showing local motion without global
  acceptance. The restart champion changes ranks, but the accepted trajectory
  remains on the incumbent sheet because frozen-primary lift is absent.
- Weakest assumption: rank-signature homogeneity over a short recent window is
  enough to describe the relevant search-space obstruction. It is a diagnostic,
  not a proof that all useful neighborhoods are exhausted.
- Check for the other lens: verify with frozen validation and null/baseline
  controls before treating any changed-rank restart candidate as meaningful
  progress.
- Boundary note: this is Riemann-inspired structural framing; modern
  search-space language is a reconstruction for engineering clarity.

Cross-Review:

- Gauss challenges the restart champion: changed rank vectors and full-eval rank
  `9` are not promotion evidence while frozen-primary score remains at the
  incumbent baseline.
- Riemann challenges the operational action: an active continuous supervisor has
  no natural deadline, so restart preparation must remain an operator-reviewed
  transition, not a parallel fresh run.

Disagreement:

- `evidence`: whether the rank-homogeneity restart champion is a useful
  navigation clue remains unresolved until it improves frozen-primary evidence
  or another predeclared baseline.
- `scope`: the current diagnostic supports this run-state decision only. It does
  not generalize to a new search heuristic, weight bound, advisor budget, or
  betting signal.

Synthesis: the smallest shared conclusion is to keep the active supervisor under
operator review, preserve the incumbent/frozen-validation gate, avoid automatic
restart while the lock is fresh, and collect further rounds or a deliberate
human-approved restart rather than changing strategy logic from this alert
alone.

Next Verification:

- Re-run the watcher after additional completed rounds or after an operator
  deliberately stops/transfers the continuous supervisor.
- If rank homogeneity persists after a fresh approved restart, inspect whether
  restart candidates provide nonzero search distance, changed rank vectors, and
  frozen-primary lift under the same legal sample space, historical window,
  baseline/null model, leakage checks, uncertainty, and failure-case reporting.
- Do not promote a new weight, advisor, candidate source, or heuristic until
  code and live historical rounds verify it against those controls.

## Result

No code change was made because the inspected state is an operational training
alert with active safety controls, not a runtime failure or a proven strategy
defect. The current live run should not be replaced in parallel while the
training-supervisor lock is fresh. The next safe operational action is continued
monitoring or explicit human review before stopping the continuous supervisor
and starting a fresh run.

## Validation

Validation for this docs-only round:

```bash
apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5
git diff --check
```

Results:

- `watch_training_progress.py --limit 5`: passed. The run remained
  `20260707-100454`, round count advanced to `283`, severity stayed `alert`,
  action stayed `prepare_restart_with_more_exploration`, restart readiness
  stayed blocked by `active_training_supervisor_lock`, and supervisor progress
  remained fresh in continuous mode.
- `git diff --check`: passed.

The report makes no predictive claim and does not alter code paths, generated
runtime artifacts, or model behavior.
