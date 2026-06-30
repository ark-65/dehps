# Self-Iteration Report: Training Watch Gate Detail

- Date: 2026-07-01
- Primary goal: make the current training-watch alert show which suspicious eval-slice issues, candidate sources, and blocked candidate sources are driving the gate state.
- Non-goals: no model, advisor, candidate source, weight boundary, search strategy, promotion rule, supervisor restart, or betting recommendation change.
- Initial status: working tree was clean before edits.

## Training Status

- Latest watched run: `20260630-181946`
- Live watch result after the change: `severity=alert`, `action=prepare_restart_with_more_exploration`
- Completed rounds at validation: 87 total, with `--limit 5` used only for the recent display window.
- Heavy-job lock: active training supervisor process, PID `2336554`.
- Legal red-ball sample space: `C(33, 6) = 1,107,568`; latest supervisor ranked universe is 1,105,506 after 2,062 exclusions.
- Historical windows in the latest supervisor report: train window 900, eval window 100, frozen validation window 20 issues (`2026054` through `2026073`).
- Baseline/null context: latest supervisor report includes `null_baseline` and `default_baseline`; this round makes no predictive or betting claim.
- Leakage posture: monitor-only change; no parser, sync, candidate scoring, history window, threshold, model training, or promotion logic was changed.

## Gauss/Riemann Diagnostic

- Task Frame: the live run is active but shows high stagnation, eval-slice primary hits `[3, 3, 3]`, frozen-validation primary hits `[0, 0, 0]`, and rank-signature homogeneity. Progress means improving operational evidence visibility without treating eval-slice lift as a settled predictive signal.
- Historical Boundary: Gauss and Riemann are used as historically inspired verification and structure lenses, not literal minds, authority, or complete reconstructions.
- Gauss Pass: the measurable residual remains eval primary `[3, 3, 3]` versus frozen primary `[0, 0, 0]`, with promotion blocked by `frozen_validation_not_better`. The suspicious eval issues are repeated across `2026025`, `2026043`, and `2026048`; this supports caution, not promotion.
- Riemann Pass: the current state has a local eval-slice pattern that does not continue to the frozen-validation region. The watch report should therefore expose the local sources and the search-base obstruction together, rather than hiding them behind aggregate counts.
- Cross-Review: Gauss rejects any restart or performance claim based only on repeated eval-slice hits; Riemann rejects an alert that names the guardrail but hides the candidate-source geometry behind it.
- Synthesis: the smallest safe improvement is Markdown observability: keep the existing guardrails, but surface suspicious `source_counts`, suspicious `issue_counts`, and blocked candidate sources in the human-readable watch report.
- Next Verification: any later supervisor or search-navigation change must be validated against the same legal sample space, historical window, frozen validation, baseline/null model, leakage checks, uncertainty, and failure cases.

## Change

`apps/worker-python/scripts/watch_training_progress.py` now renders existing gate metadata in the watch Markdown and Judgement notes:

- eval-slice suspicious source counts
- eval-slice suspicious issue counts
- decision-round blocked candidate sources

This uses the already-collected `gate_summary` fields. It does not change scoring, candidate generation, advisor budgets, search navigation, or promotion.

## Validation

```bash
apps/worker-python/.venv/bin/python -m py_compile apps/worker-python/scripts/watch_training_progress.py
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_training_watch.py apps/worker-python/tests/test_training_supervisor.py
apps/worker-python/.venv/bin/python apps/worker-python/scripts/watch_training_progress.py --limit 5
```

Observed live watch output:

```json
{"run_id":"20260630-181946","round_count":87,"round_window_count":5,"severity":"alert","action":"prepare_restart_with_more_exploration"}
```

The generated Markdown now includes:

```text
Eval-slice overfit guardrail: active=True reason=eval_slice_overfit_no_frozen_primary_lift eval_primary=[3, 3, 3] frozen_primary=[0, 0, 0] suspicious=4 sources=unknown=3, stagnation_restart=1 issues=2026025=4, 2026043=4, 2026048=4
Decision round best: source=incumbent reason=incumbent_due_to_required_frozen_primary_lift selected_frozen_primary=[0, 0, 0] blocked_candidates=1 blocked_sources=[rank_homogeneity_restart]
```

## Result

The live alert remains real. The report now shows that the current alert is tied to repeated eval-slice issues and that the available rank-homogeneity restart candidate was blocked by the frozen-primary requirement. No fresh supervisor was required because this was a monitor/reporting change only.
