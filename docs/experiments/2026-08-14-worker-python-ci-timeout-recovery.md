# Worker Python CI Timeout Recovery

## Round boundary

This Engineering round has one goal: recover the Worker publication gate by
changing the existing `pytest` job timeout from 20 to 30 minutes. It does not
change tests, test selection, commands, actions, dependencies, runners,
triggers, concurrency, application code, runtime state, or production state.

Request 587 (`engineering-m4-v2-global-recovery-v2-terminalization-timestamp-normalization-v3`)
and Execution 479 failed under Decision 2460 with the exact reason
`merged_main_worker_ci_cancelled_timeout_20m_without_test_failure`. They must
not be retried or reused.

PR 351 was squash-merged as
`38daa88791b838c446a4a09866452ddb590131b4`. Its PR-head Worker run
31801185591 succeeded in 18m49s. Its merged-main Worker run 31802563591 was
cancelled after 20m16s by the workflow ceiling, with `test_failure=false` and
`rerun=false`. Neither old run may be manually rerun.

## Exact workflow change

Baseline workflow identity:

- Path: `.github/workflows/worker-python-tests.yml`
- SHA256: `c895363beb64f1ff9daacb38042afa56f400c9485178e6f63ecbbb5291180c1f`
- Length: 2930 bytes
- Unique timeout: `timeout-minutes: 20` at line 23

Final workflow identity:

- SHA256: `5fa0a579dbfde3d8ade2534302df6edae247caa6e1f262105271d49411edd592`
- Length: 2930 bytes
- Unique timeout: `timeout-minutes: 30` at line 23

Replacing the final line-23 scalar 30 with 20 in memory reproduces the exact
baseline bytes. Therefore every other raw workflow byte, including all
triggers, concurrency settings, permissions, jobs, steps, actions,
dependencies, working directories, and the Worker test command, is unchanged.
The final YAML parses successfully and contains exactly one timeout field.

## Validation and publication gates

- Exact write scope: the workflow above plus this report; no extra path.
- YAML parse and unique-timeout checks: PASS.
- Non-timeout raw-byte equivalence: PASS.
- `git diff --check`: PASS.
- Old-run rerun: forbidden and not performed.
- Production import, Supervisor, workload, replay, P3 fold, P4 action, and
  Promotion: none.

The report intentionally does not contain its own final SHA256, the exact2
material digest, or the inclusive diff digest. Independent final review owns
those non-recursive identities outside this report.

## Mainline integration matrix

| Stage | Evidence | Status |
| --- | --- | --- |
| Goal | Increase only the Worker job ceiling from 20 to 30 minutes | CODE_COMPLETE |
| Resolver / Ready Queue / Supervisor | Not a training capability or production operation | Not invoked |
| PR-head Worker | A new run is required after publication | Pending |
| Merged-main Worker | A distinct new run must succeed within 30 minutes | Pending |
| Local main | Must synchronize cleanly to `origin/main` after merged-main success | Pending |

Integration answer: **NO — INTEGRATION_PENDING** until a fresh PR-head Worker
run and a distinct fresh merged-main Worker run both conclude SUCCESS under the
30-minute ceiling, local `main` is synchronized cleanly to `origin/main`, and
the fresh Engineering request is typed-completed.


## PR353 Worker CI 30-minute timeout recovery

1. Engineering Request 599, Execution 490, and Decision 2518 failed at the PR-head Worker CI publication gate and are immutable, no-retry, and no-reuse.
2. PR 353 remains OPEN and ready for review at head 6258f1e06b8ab40bd88298acca707dd33c384158 with auto-merge disabled. The cancelled PR-head run is 31847793774 and job 94917641067.
3. The job ran for 30m17s. Its test step ran for 29m18s and reached 97% progress. The only terminal error was `The operation was canceled.` and the annotation was `The job has exceeded the maximum execution time of 30m0s`. There was no failed assertion, ERROR, traceback, or pytest failure summary, so this is a timeout boundary and not a scientific or test conclusion.
4. The same exact tree completed the local full Worker suite in 1039.24s (17m19.24s). The observed CI test lower bound is 1758s, or 1.6916208 times the local duration.
5. Raising only the unique Worker timeout from 30 to 45 minutes gives a 2700s ceiling. Preserving the observed 55s pre-test overhead leaves 887s (14m47s) after the observed 97% point.
6. Recovery changes only the unique `timeout-minutes: 30` scalar to `timeout-minutes: 45`. Workflow triggers, concurrency, permissions, job shape, runner, install steps, exact pytest command, and deselections remain byte-equivalent.
7. The old cancelled run is never rerun. A fresh synchronize commit on PR 353 must produce a new PR-head Worker SUCCESS before squash auto-merge is enabled, followed by a distinct merged-main Worker SUCCESS and a clean synchronized main.
8. Integration answer: NO - INTEGRATION_PENDING until both fresh CI gates succeed and the fresh Engineering request completes. No production, Supervisor, workload, replay, P3, P4, or Promotion action occurs in this recovery.
