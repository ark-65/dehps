# Self-Iteration Report: Training Watch Gate Snapshot

- Date: 2026-06-30
- Primary goal: make the training watch alert explain the active frozen-primary and search-base gates behind the current stagnation.
- Non-goals: no model, advisor, candidate source, weight boundary, search strategy, supervisor restart, or promotion rule change.
- Initial status: working tree was clean before edits.

## Training Status

- Latest watched run: `20260630-181946`
- Latest watch result after the change: `severity=alert`, `action=prepare_restart_with_more_exploration`
- Completed rounds: 57 total, with the `--limit 5` recent window used only for latest metrics and advisor snapshot.
- Heavy-job lock: active training supervisor process.
- Legal red-ball sample space: `C(33, 6) = 1,107,568`; latest supervisor ranked universe is 1,105,506 after 2,062 exclusions.
- Historical windows in the latest supervisor report: train window 900, eval window 100, frozen validation window 20 issues (`2026054` through `2026073`).
- Baseline/null context: latest supervisor report includes `null_baseline` and `default_baseline`; this round makes no predictive or betting claim.
- Leakage posture: monitor-only change; no parser, sync, candidate scoring, history window, threshold, or model training logic was changed.

## Gauss/Riemann Diagnostic

- Task Frame: the live run shows 50+ stagnation rounds while the current best keeps Top100/1000/10000 = 3/3/3 on the 100-draw eval slice but frozen validation Top100/1000/10000 = 0/0/0. Progress means making the operational blocker explicit without promoting the eval-slice result.
- Historical Boundary: Gauss and Riemann are used as historically inspired verification and structure lenses, not literal minds or authority.
- Gauss Pass: the measurable residual is eval primary `[3, 3, 3]` versus frozen primary `[0, 0, 0]`, with promotion blocked by `frozen_validation_not_better`. The null/baseline and repeated-search cautions remain required, so the eval lift is not evidence of a settled future edge.
- Riemann Pass: the search state is split between local eval-slice behavior and global frozen-validation/navigation state. The useful representation is a gate snapshot that exposes promotion, eval-slice overfit, search-base, rank-homogeneity, and decision-round-best state together.
- Cross-Review: Gauss rejects restarting or promoting based only on repeated eval-slice hits; Riemann rejects a watch alert that hides the structural reason the run stays on the incumbent search base.
- Synthesis: the smallest safe improvement is observability: expose the existing gate state in the watch JSON and Markdown so future restart decisions can be tied to frozen-primary evidence.
- Next Verification: any later supervisor or search-navigation change must be validated against the same legal sample space, historical window, frozen validation, baseline/null model, leakage checks, uncertainty, and failure cases.

## Change

`apps/worker-python/scripts/watch_training_progress.py` now extracts a `gate_summary` from the latest round `prefilter` and renders a Markdown `Gate Snapshot`.

The snapshot includes:

- promotion gate pass/reason and candidate/incumbent frozen-primary scores
- eval-slice overfit guardrail status, eval-primary score, frozen-primary score, and suspicious candidate count
- stale search-base gate status and frozen-primary challenger requirement
- rank-homogeneity guardrail status and unique signature count
- decision-round-best source, reason, selected frozen-primary score, and blocked candidate count

## Validation

```bash
apps/worker-python/.venv/bin/python -m py_compile apps/worker-python/scripts/watch_training_progress.py
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_training_watch.py
apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5
git diff --check
```

Observed live watch output after the change:

```json
{"run_id":"20260630-181946","round_count":57,"round_window_count":5,"severity":"alert","action":"prepare_restart_with_more_exploration"}
```

The generated Markdown now reports:

```text
Promotion gate: passed=False reason=frozen_validation_not_better candidate_primary=[0, 0, 0] incumbent_primary=[0, 0, 0]
Eval-slice overfit guardrail: active=True reason=eval_slice_overfit_no_frozen_primary_lift eval_primary=[3, 3, 3] frozen_primary=[0, 0, 0] suspicious=4
Search-base gate: active=True reason=eval_slice_overfit_no_frozen_primary_lift require_frozen_primary_challenger=True
Rank homogeneity: active=True reason=stale_rank_signature_cycle unique_signatures=1
Decision round best: source=incumbent reason=incumbent_due_to_required_frozen_primary_lift selected_frozen_primary=[0, 0, 0] blocked_candidates=1
```

## Result

The live alert remains real. The watch report now explains that the run is active but blocked by frozen-primary validation, eval-slice overfit guardrails, search-base constraints, and rank-signature homogeneity. No training process restart was required for this monitor-only change.
