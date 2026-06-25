# Self-Iteration Report: Hourly Wrapper Status Messages

Date: 2026-06-25

## Primary Goal

Make the two-hour self-iteration wrapper leave an accurate last-message artifact when it skips because of a dirty worktree or when the Codex process exits unsuccessfully.

## Non-Goals

- No training, scoring, backtest, candidate-generation, or advisor logic changes.
- No generated `data/output` or `runtime` artifacts are promoted.
- No change to DEHPS evidence level, prediction claims, or betting language.

## Change

`scripts/hourly_self_iterate.sh` now writes `runtime/logs/hourly_self_iterate.last.md` for scheduler-level failures before Codex starts, including missing Codex or Node binaries.

The wrapper also accepts `DEHPS_REPO_ROOT`, `DEHPS_NODE_BIN_DIR`, `DEHPS_CODEX_BIN`, and `DEHPS_LOG_DIR` overrides. The production defaults are unchanged, while the override path makes the scheduler guardrails testable without touching the live lock or runtime logs.

The dirty-worktree guard now captures `git status --short` once, prints it to stdout, and writes the same status into the last-message artifact before exiting. This keeps operational review from mistaking an older successful Codex final message for the latest scheduled run.

If Codex exits with a non-zero status, the wrapper writes a short failure artifact with start time, failure time, and exit code before propagating the same exit code.

## Validation

Focused validation:

```bash
bash -n scripts/hourly_self_iterate.sh
DEHPS_REPO_ROOT="$tmp_repo" \
DEHPS_LOG_DIR="$tmp_repo/logs" \
DEHPS_CODEX_BIN=/bin/true \
DEHPS_NODE_BIN_DIR="$node_bin" \
  scripts/hourly_self_iterate.sh
```

The live wrapper invocation observed an existing lock and exited without changing active-run state. The dirty-worktree branch was then validated with a temporary git repository and temporary log directory through the new environment overrides, so it did not launch Codex or training.

## Guardrail

This is an operational observability fix only. It does not alter historical ranking behavior, structural scoring, candidate generation, strategy selection, or any claim about predictive ability.
