# Prediction v2 structural evaluation status projection fix — Round 70

Date: 2026-08-09

Role sequence: Operator failure -> Engineering Agent -> Reviewer -> Engineering Agent

## Primary goal

Project the already registered structural evaluation execution into canonical M4
status after merged execution and replay exposed a null-detail projection.

## Reproducer and root cause

Mainline execution
`3a0aacca17b31f2fc251e9c5dd8e6a121310af3f090235f5cce1f019066dafa7`
completed and replayed four immutable artifacts. The durable resolver correctly
marked the evaluation complete and made `prediction-v2-structural-route-decision`
Ready, but status reported null decision/arithmetic fields and zero island counts.

`ResearchEvidenceSupervisor._latest_completed_v2_summary` did not include the
structural execution or evaluation task keys. Its generic path also returned only
the completion event payload, while these status fields live in the registered
execution artifact.

## Fix

- prefer the completed structural evaluation, then structural execution, before
  older Measurement v2 summaries;
- load and verify the singular registered execution artifact for both tasks;
- add a regression test proving evaluation precedence and artifact-field loading.

The evaluator, source contract, manifests, task definitions, frozen arithmetic,
artifact identities, bounded interpretation, and route are unchanged. No
repeated/duplicate/uniqueness validation, workload rerun, historical read,
Evidence change, model, promotion, P3, or production action is introduced.

## Validation

- focused evaluator/status tests: `8 passed`;
- structural/planner/latest-summary regression group: `68 passed`;
- Ruff formatting/lint, Python compilation, and `git diff --check`: passed;
- live read-only projection against the durable 66-task control plane:
  - latest execution task: `prediction-v2-structural-portfolio-evaluation`;
  - execution artifact: `f17d1a9f...`;
  - decision: `SUPPORTED_AT_FROZEN_B176_AGAINST_UNIFORM_RANDOM_ONLY`;
  - exact ideals: 33,792 / 13,200 / 76,032;
  - selected gaps: +4 / +952 / -2;
  - null extrema: 34,104 / 15,144 / 2 / 75,876;
  - robustness: 16 of 22 islands;
  - next consumer resolver status: Ready.

Mainline acceptance remains pending until this fix is merged, the merged
Supervisor refreshes canonical status from durable state, and the registered
evaluation execution is replayed again with the merged selector.
