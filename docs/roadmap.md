# DEHPS Long-Term Roadmap

DEHPS long-term development must advance by staged, reviewable rounds. Do not implement crawlers, agents, frontend, AI workflows, and schedulers in one broad pass.

Parent task: DEHPS long-term research and development.

Core positioning:

- DEHPS = Discrete Event Human Plausibility Score.
- Chinese name: 离散事件人类合理性评分.
- DEHPS is being trained toward a prediction-oriented decision-support system, with betting-oriented recommendations allowed as a future product direction and as clearly labeled experimental outputs.
- It is currently an AI-assisted platform for scoring, filtering, backtesting, training diagnostics, and reporting over large discrete combination spaces.
- The first demo domain is 双色球 red-ball combinations only.

Core principle:

```text
AI proposes hypotheses. Code verifies them. Historical data judges them.
```

## Working Rules

Each round must complete exactly one verifiable loop.

Before starting a round:

- Confirm the round goal and non-goals.
- Keep production data separate from verification data unless explicitly promoting results.
- Prefer small, reversible changes over broad refactors.

At the end of each round:

- Run the relevant test suite.
- Produce or update a human-readable report under `docs/experiments/`.
- Record commands, results, known problems, and next-round recommendations.
- Make a rollback-friendly git commit for the round's accepted changes.

## Round Status

| Round | Theme | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Basic computation and backtest loop | Done | `docs/experiments/round-1-report.md` |
| 2 | Daily data synchronization | Done | `docs/experiments/round-2-report.md` |
| 3 | Git automation and scheduled runs | Done | `docs/experiments/round-3-report.md` |
| 4 | AI Agent experiment system | Done | `docs/experiments/round-4-report.md` |
| 5 | Dashboard and API | Done | `docs/experiments/round-5-report.md` |
| 6 | Experiment detail and report viewer | Done | `docs/experiments/round-6-report.md` |
| 7 | Comparison and distribution review | Done | `docs/experiments/round-7-report.md` |
| 8 | Candidate generation audit foundation | Done | `docs/experiments/round-8-report.md` |
| 9 | Walk-forward algorithm ranking skeleton | Done | `docs/experiments/round-9-report.md` |
| 10 | Sorted history, constant universe, regime window, first weight search | Done | `docs/experiments/round-10-report.md` |
| 11 | Expanding walk-forward and previous-draw micro weights | Done | `docs/experiments/round-11-report.md` |
| 12 | Progress output and feature-matrix cache | Done | `docs/experiments/round-12-report.md` |
| 13 | Adaptive training supervisor and draw schedule | Done | `docs/experiments/round-13-report.md` |
| 14 | DB-first training intelligence | Done | `docs/experiments/round-14-report.md` |
| 15 | Neural readiness probe | Done | `docs/experiments/round-15-neural-readiness-report.md` |
| 16 | Explicit neural CPU MLP scorer v0 | Done | `docs/experiments/round-16-neural-scorer-v0-report.md` |
| 17 | Project consolidation and local acceptance | Done | `docs/experiments/round-17-project-consolidation-report.md` |
| 18 | Training runtime architecture refactor | Done | `docs/experiments/round-18-training-architecture-refactor.md` |
| 19 | Production runtime decomposition phase 1 | Done | `docs/experiments/round-19-production-runtime-decomposition-phase-1.md` |
| 20 | Structured Hypothesis Registry | Done | `docs/experiments/round-20-hypothesis-registry-foundation.md` |
| 21 | Research/Engineering Agent authority separation | Done | `docs/experiments/round-21-agent-authority-separation.md` |
| 22 | Autonomous Hypothesis Proposal Engine | Done | `docs/experiments/round-22-autonomous-hypothesis-proposal-engine.md` |
| 23 | Autonomous Experiment Planning and Preregistration | Done | `docs/experiments/round-23-autonomous-experiment-planning.md` |
| 24 | Ranking-disagreement isolated execution tool | Done | `docs/experiments/round-24-ranking-disagreement-execution.md` |

## Round 1: Basic Computation And Backtest Loop

Goal: complete a stable minimum loop.

Acceptance checklist:

- PostgreSQL tables initialize successfully.
- Python worker installs with `pip install -e .`.
- 双色球 red-ball combinations can be generated.
- Red-ball structural features can be calculated.
- Sample or verification history can be imported without polluting production data.
- `baseline_v1` strategy can filter combinations.
- Backtest metrics can be calculated.
- Markdown experiment report can be written.
- `pytest` passes.
- A round report and commit are produced.

Non-goals:

- Real crawler.
- Git auto-push.
- Frontend dashboard.
- Complex AI Agent calls.
- Model training.
- Betting advice.

Current state: completed as an acceptance round. See `docs/experiments/round-1-report.md`.

## Round 2: Daily Data Synchronization

Goal: formalize daily data sync as a verifiable loop.

Acceptance checklist:

- Implement `sync_latest_ssq.py`.
- Implement source abstraction.
- Validate draw data.
- Record conflicts.
- Implement `daily_pipeline.py`.
- Write daily reports.
- Support `--dry-run`.
- Support explicit CSV fallback.

Current state: completed as an acceptance round. See `docs/experiments/round-2-report.md`.

## Round 3: Git Automation And Scheduled Runs

Goal: make the daily pipeline operational and auditable without mixing verification and production outputs.

Acceptance checklist:

- Verify `git_commit_and_push.py` behavior and allowed paths.
- Confirm crontab documentation.
- Confirm systemd timer documentation.
- Verify `pipeline_runs` records success and failure states.
- Confirm log directory behavior.
- Define and test a failure recovery path.
- Run `daily_pipeline.py --source zhcw --force` on a verification database.
- Confirm `pipeline_runs`, `ssq_sync_runs`, generated daily report, and generated experiment report are coherent.
- Add failure-path tests for sync and pipeline status recording.
- Produce `docs/experiments/round-3-report.md`.
- Commit the accepted round changes.

Non-goals:

- Frontend dashboard.
- AI strategy generation.
- Auto-promotion of generated reports to production.
- Unlabeled or unsupported betting and predictive claims.

Current state: completed as an acceptance round. See `docs/experiments/round-3-report.md`.

## Round 4: AI Agent Experiment System

Goal: let agents propose and criticize strategy hypotheses while keeping code and historical data as the verification layer.

Acceptance checklist:

- Strategy Agent prompt.
- Critic Agent prompt.
- Backtest Agent prompt.
- Experiment report reader.
- Next-round strategy suggestion format.
- Strategy version management.
- Clear separation between AI suggestions and verified metrics.
- Produce a round report and commit.

Non-goals:

- Unlabeled claims that treat immature training output as settled predictive ability.
- Autonomous production strategy changes without review.

Current state: completed as an acceptance round. See `docs/experiments/round-4-report.md`.

## Round 5: Dashboard And API

Goal: expose experiment history and operational status through a small product surface.

Acceptance checklist:

- NestJS API.
- Angular dashboard.
- Experiment list.
- Strategy comparison.
- Combination distribution views.
- Daily sync records.
- Produce a round report and commit.

Current state: completed as an acceptance round. See `docs/experiments/round-5-report.md`.

Non-goals:

- Marketing landing page.
- Betting workflow.
- User-facing recommendation language that hides the current evidence level.

## Round 6: Experiment Detail And Report Viewer

Goal: make the dashboard useful for evidence review, not only operational summary.

Acceptance checklist:

- Add a read-only API endpoint for a single experiment detail.
- Include stored Markdown experiment report content.
- Show hypothesis, config snapshot, metrics, report timestamp, and report body in the dashboard.
- Keep the dashboard read-only.
- Produce `docs/experiments/round-6-report.md`.
- Commit the accepted round changes.

Current state: completed as an acceptance round. See `docs/experiments/round-6-report.md`.

Non-goals:

- Full Markdown-to-HTML rendering.
- Editable experiment records.
- Client-side deep links.
- Unlabeled prediction or betting language.

## Round 7: Comparison And Distribution Review

Goal: complete the current research-review surface before deep optimization starts.

Acceptance checklist:

- Add read-only structural feature distribution data to the API.
- Show feature distribution charts in the dashboard.
- Add a side-by-side experiment comparison panel.
- Preserve selected experiment state in a shareable URL hash.
- Keep the round read-only and avoid algorithm changes.
- Produce `docs/experiments/round-7-report.md`.
- Commit the accepted round changes.

Current state: completed as an acceptance round. See `docs/experiments/round-7-report.md`.

Non-goals:

- Strategy tuning.
- Model training.
- New scoring formulas.
- Unlabeled prediction or betting language.
- Treating current generated-combination sample charts as full-space statistics.

## Round 8: Candidate Generation Audit Foundation

Goal: produce next-issue red-ball candidates as a frozen, auditable experiment.

Acceptance checklist:

- Add deterministic candidate generation for legal 双色球 red-ball combinations.
- Add a random null-model baseline with the same candidate count.
- Add leakage checks before publishing a candidate artifact.
- Write CSV and Markdown candidate artifacts.
- Keep language explicit that candidates are prediction hypotheses, not guaranteed outcomes.
- Produce `docs/experiments/round-8-report.md`.
- Commit the accepted round changes.

Current state: completed as an acceptance round. See `docs/experiments/round-8-report.md`.

Non-goals:

- Guaranteed hit prediction.
- Betting advice without evidence-level and risk labeling.
- Post-draw retuning.
- Blue-ball prediction.
- New model training.

## Round 9: Walk-Forward Algorithm Ranking Skeleton

Goal: start deep algorithm optimization by ranking every legal red-ball combination under a no-leakage walk-forward protocol.

Acceptance checklist:

- Add a transparent trainable ranker.
- Add exact target rank calculation.
- Track Top 100, Top 1000, and Top 10000 hit counts.
- Generate Markdown and JSON optimization artifacts.
- Make full-combination rankings reproducible with `as_of_issue`, `history_fingerprint`, and `config_hash`.
- Document the algorithm optimization plan.
- Keep failure results visible instead of tuning around them.
- Commit the accepted round changes.

Current state: completed as an acceptance round. See `docs/experiments/round-9-report.md`.

Non-goals:

- Promoting `frequency_v1` as a successful model.
- ECharts dashboard visualization.
- Large grid search over hundreds of configs.
- Claiming settled future predictive ability before the training target is reached.

## Update Policy

This file is the durable plan. At the end of each accepted round:

- Mark the round status.
- Link the new round report.
- Move unfinished acceptance items into the next round only when still relevant.
- Add new rounds only when they represent a distinct verifiable loop.
- Keep the roadmap short enough to guide work rather than replace experiment reports.
