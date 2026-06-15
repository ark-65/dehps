# Round 4 Report

## Done

- Expanded Strategy, Backtest, and Critic Agent documents into concrete prompts and acceptance rules.
- Added `dehps.agents.strategy_suggestion.StrategySuggestion` as the local schema for advisory strategy proposals.
- Added strategy version management through `{base_strategy_key}_{proposed_version}`.
- Enforced `advisory_only = true` so agent suggestions cannot directly promote themselves into scheduled use.
- Added measurable failure-condition validation for strategy suggestions.
- Added `dehps.agents.report_reader.parse_experiment_report(...)` for machine-readable experiment summaries.
- Updated experiment report rendering to include `Missed Issues` and `Config Snapshot`.
- Added tests for strategy suggestion validation and experiment report parsing.

## Einstein Pass

Core question: can AI agents propose the next DEHPS strategy experiment without turning historical backtests into prediction claims?

Invariant: every legal 双色球 red-ball combination remains equally likely before a draw; agent output is only a structural hypothesis.

Hypothesis: a strategy suggestion is acceptable only if it includes a baseline, measurable keep-rate and coverage expectations, failure conditions, and a frozen config snapshot.

Measurement: the local schema validates the suggestion, the report reader extracts metrics and misses, and tests prove unsafe suggestions fail validation.

Failure mode: an agent could still write persuasive language around a weak or post-hoc idea, so the Critic Agent prompt now requires leakage, time, null, and language checks.

Next experiment: Round 5 can expose accepted experiment records and agent review packets through an API/dashboard without changing the research boundary.

## Tests

```text
25 passed in 7.31s
```

## Commands Run

```bash
/home/ark/workspace/dehps/apps/worker-python/.venv/bin/python -m pytest
```

## Acceptance Evidence

Strategy Agent prompt:

```text
docs/agents/strategy-agent.md
```

Backtest Agent prompt:

```text
docs/agents/backtest-agent.md
```

Critic Agent prompt:

```text
docs/agents/critic-agent.md
```

Strategy suggestion schema and versioning:

```text
apps/worker-python/dehps/agents/strategy_suggestion.py
apps/worker-python/tests/test_agent_strategy_suggestion.py
```

Experiment report reader:

```text
apps/worker-python/dehps/agents/report_reader.py
apps/worker-python/tests/test_agent_report_reader.py
```

Report fields required by the Backtest Agent:

```text
apps/worker-python/dehps/backtest/report.py
```

## Problems

- This round intentionally does not call a real AI model. It defines the local contract that model output must satisfy later.
- Strategy suggestions are not persisted as first-class database records yet.
- The report reader targets the project's generated Markdown report format; it is not a general Markdown parser.

## Next Round

Round 5 should build the smallest Dashboard/API surface:

- List experiment reports.
- Show strategy keys, metrics, missed issues, and config snapshots.
- Expose daily sync and pipeline status.
- Keep the product language research-focused and avoid prediction or betting language.

## Risk Note

DEHPS remains a discrete combination-space scoring and backtest platform. Agent suggestions are hypotheses for backtesting, not predictions or betting advice.
