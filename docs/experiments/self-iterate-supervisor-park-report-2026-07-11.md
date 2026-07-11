# Supervisor Park Report Lifecycle Sync

## Round Goal

Keep the persisted supervisor Markdown report consistent with the authoritative JSON status when the forward-wait guard parks a completed run.

## Non-Goals

- No training, scoring, objective, advisor, candidate-source, budget, search-base, or promotion changes.
- No reinterpretation of historical lift as predictive evidence.
- No supervisor restart while the same-history forward-wait guard is active.

## Reproduction

Run `20260711-132111` reached database-backed round 8 with `supervisor_round_boundary.status=target_complete_round_recorded`. The watcher and supervisor JSON reported `waiting_for_forward_issue`, but the corresponding Markdown header still reported `Status: running`. The separate parking command updated JSON and heavy-job metadata without updating the report.

## Change

`mark_training_supervisor_waiting.py` now atomically updates the existing report's `Updated at` and `Status` header fields after persisting the waiting JSON. Missing report header fields fail explicitly instead of silently leaving a contradictory report. Tests cover the report helper and the full JSON, heavy-job metadata, and Markdown parking path.

## Gauss/Riemann Cross-Review

- Task frame: remove one observable lifecycle residual without changing model behavior.
- Historical boundary: Gauss and Riemann are used only as historically inspired verification lenses, not as authority or reconstructed minds.
- Gauss pass: JSON, database round boundary, and watcher agreed; the exact residual was Markdown `running` versus JSON `waiting_for_forward_issue`. The proof obligation is exact lifecycle-field equality plus regression tests.
- Riemann pass: the lifecycle state crossed from the supervisor process into a separate parking script, while the Markdown surface remained attached only to the original process writer. The repair joins those two state surfaces at the transition boundary.
- Disagreement: none on the local defect. Neither lens supports changing search behavior or interpreting historical metrics.
- Smallest shared conclusion: synchronize only the two report lifecycle fields and keep JSON authoritative.
- Next verification: on the next valid forward-wait park, confirm JSON, Markdown, watcher, and heavy-job metadata all report the same waiting state.

## Evidence Guardrails

- Legal red-ball universe: 1,107,568; ranked universe: 1,105,506; excluded: 2,062.
- Historical window: expanding train window 900; evaluation 100 split into non-overlapping search 80 and frozen 20.
- Holdout isolation: search does not use frozen validation; frozen role is promotion-only; prefilter isolation passed with zero frozen or outside-split overlap.
- Historical holdout remains quarantined. Forward evidence is 0/20 paired issues and is not promotion-eligible.
- Sequential null audit remains `incomplete_observed_lower_bound`: 294 legacy rounds are uncounted, adaptive generation and sequential multiplicity are incomplete, and automatic promotion is disabled.
- Candidate space is currently diverse (10 unique Top rank signatures); stale round-best behavior is an objective-surface diagnostic, not candidate collapse.
- Prediction input boundary passed with only `issue`, `draw_date`, and `red_numbers` admitted.
- GPU training remains disabled; the latest OpenCL probe was rejected for non-exact rounded scores and insufficient end-to-end speedup.

## Validation

```text
17 focused tests passed in 1.38s
558 worker tests passed in 19.82s
```

Evidence level: operational observability fix. This round provides no new prediction signal, performance lift, promotion evidence, or betting recommendation.
