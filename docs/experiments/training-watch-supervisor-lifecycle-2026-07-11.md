# Training Watch Supervisor Lifecycle — 2026-07-11

## Primary Goal

Separate supervisor status-artifact availability from actual PID existence, so an intentionally parked forward-evidence wait is not misreported as a running process or a crash.

## Non-Goals

- No training restart while issue `2026079` is pending.
- No model, advisor, source budget, objective, candidate, or promotion change.
- No automatic recovery action based on the new observation.
- No claim that PID existence verifies command identity.

## Triggering Observation

The current supervisor artifact reports `available=true`, `status=waiting_for_forward_issue`, and PID `3579268`. The park marker correctly records `forward_wait.process_active=false`, and the OS no longer has that PID. The watcher previously discarded the marker field and did not expose PID activity, making artifact availability easy to misread as a live supervisor.

## Change

The watcher now emits `supervisor_lifecycle` using protocol `dehps-supervisor-lifecycle-observation-v1`. It records:

- status-file availability and state;
- status-reported, expected, and OS-observed process activity;
- lifecycle consistency and attention requirement;
- an explicit `os_pid_exists_not_command_identity` scope;
- unchanged selection and disabled promotion.

The autonomous self-iteration contract now treats `parked_waiting_for_forward_issue` with a consistent inactive PID as expected, while `running_pid_inactive` requires log inspection and fail-closed handling.

## Pre-Change Runtime Audit

At `2026-07-11 16:30 CST`, the watchdog synchronized history issue `2026078`, found no changed draw, retained the complete three-line snapshot for `2026079`, and kept training parked. Advisors were current, holdout isolation passed, parser/sync/duplicate checks passed, the sequential null ledger remained an uninterpretable lower bound, and no training process was active.

## Validation Plan

- Focused watcher lifecycle and self-iteration prompt-contract tests.
- Full Python worker test suite.
- Live watcher replay against the current parked artifact and inactive PID.

## Validation Result

- Focused watcher and prompt-contract tests: `99 passed` before the final lifecycle edge cases.
- Final full Python worker suite: `572 passed`.
- Live watcher replay emitted:
  - `status=parked_waiting_for_forward_issue`
  - `status_file_available=true`
  - `status_file_state=waiting_for_forward_issue`
  - `pid=3579268`
  - reported/expected/observed process activity all `false`
  - `lifecycle_consistent=true`
  - `requires_attention=false`
  - `pid_activity_scope=os_pid_exists_not_command_identity`
  - `selection_changed=false`
  - `promotion_allowed=false`
- The replay retained `action=await_new_forward_issue`, history issue `2026078`, pending issue `2026079`, and no active training process.

## Evidence Boundary

This is operational observability only. It does not establish predictive lift or change the legal sample space, historical window, null baseline, frozen-validation quarantine, leakage boundary, forward-evidence threshold, selection, or promotion.
