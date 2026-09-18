# Historical calendar overrun repair — Engineering839

Role: Engineering. Request839 / execution677. Parent Operator838 / execution676
failed with `CALENDAR_OVERRUN_REACTIVATION_STARVES_OBSERVER`; all successful
learning and failed-operation evidence remain intact. Owner consent covers
automatic repair/deployment; genuine independent Reviewer approval was recorded
before Engineering execution. Runtime release still needs its own authenticated
Operator request and execution.

## Problem and bounded change

On2026-09-18 the publisher ran14:37:50–15:00:39 Asia/Shanghai, longer than its
15minute calendar interval. It succeeded, then systemd immediately started it
again (15:00:39.185 completion;15:00:39.190 restart). Workers ordered after the
publisher could not take their turn. No model/data repair is needed.

Add `DeferReactivation=true` to only the publisher and worker timer templates.
On supported systemd257+, a completed long job waits for the next future
calendar tick. Preserve `OnCalendar=*:0/15`, boot recovery, persistent timers,
formal guards, two-worker/one-BLAS-thread limits, original plans/images, scoped
executions4, 30day expiry2026-10-15T00:55:24.344038Z and existing historical
budget deadline2026-09-19T05:50:58.708933Z. No new algorithm, strategy, model
admission, schema, source contract, mail action or research conclusion.

The fixed host entry verifies exact package bytes, genuine ark host identity,
completed Engineering839 and a separate live Operator. It allows only timer
installation/rollback and existing fixed-image read-only replay operations.
A code merge alone does not resume production timers or prove acceptance.

## Contract and integration matrix

| Contract element | Binding / engineering-time state |
|---|---|
| Goal | Complete existing historical-report-learning.v1 and automatic intake |
| Ready | Clean current main; actual839Reviewer approval and execution677 |
| Resolver / Ready Queue | Existing immutable learning and observer plans; unchanged |
| Runner / Supervisor | Existing canonical Coordinator and publisher; ff8ff3images |
| Upstream | Frozen3503labels,900warmup,2603history; exact837packet and commits |
| Downstream | Per-issue reports, independent summary, future incrementals |
| Status | Actual scoped executions4 and current run identities; no old-state substitution |
| Evidence | Real timer regression, exact registrations, fresh-process replay, formal comparison |
| Decision / next consumer | Independent observer then next authorized report; research-only |
| Runtime acceptance | Full final replay and deployed scheduling proof still pending |

**NO — INTEGRATION_PENDING** at this engineering checkpoint. This is a timer
repair completion report, not the later Operator's business-cycle acceptance.

## Validation and actual retained progress

-34focused host boundary tests passed, including revoked/completed/unstarted
  Operator rejection, unsupported systemd rejection, forbidden timer edits,
  genuine Reviewer terminal requirement and retained service-identity replay.
-Real isolated user-systemd259 regression,6second job on a4second calendar:
  defaultfalse reactivated after0.0355seconds and its dependent worker was
  starved; true waited2.0013seconds and the worker ran between publisher jobs.
  Only unique `dehps-historical-timer-839-*` test units were started/removed.
-`systemd-analyze verify` passed for both new timer templates on the actual host.
-Initial regression harness wrongly required the starved control worker to run;
  it timed out and journal evidence was retained. Corrected the expectation:
  the control must demonstrate immediate reactivation, the fix must demonstrate
  handoff. The final real regression passed. No production unit was changed.
-Read-only authenticated SQL inventory at15:32CST verified5214learning commits
  (2605learn,2605report,freeze,resumes,summary),10428mainline events and5214
  registrations. Observer has2608commits (2605observe,2resumes,summary),5216
  events and2608registrations. Both have zero registration violations.
-The frozen2603historical evaluations and2incremental issues2026107/2026108
  are complete. Independent summary was read as the actual observer service
  account. Full new-process replay remains an Operator gate.

The readable summary remains `HISTORICAL_RECONSTRUCTION · 证据不足`.
Descriptively, shrink900 mean log loss0.4741738055 and Brier0.1487707116 are
slightly worse than uniform0.4741393131 and0.1487603306, respectively; both
metrics are lower-is-better. Engineering success is not predictive improvement.
The2026104original prediction gap remains explicit.

## Report impact and preservation

Before implementation,44protected formal prediction, provenance, replay,
consumer, mail ledger and timer files matched the837baseline exactly. Formal
2026109 was sealed2026-09-17T22:06:58.717105+08 before the2026-09-20T21:15draw,
with readable published report and registered replay. Its future17:00Sep20mail
is `PENDING_DELIVERY`;2026108pre/post delivery records remain sent.

Direct impact is independent historical timer ordering. Indirect impact is
when already registered reports reach the observer. Formal P3 stays on its
frozen legacy release; V11 stays retired. No formal timer or mail path is
modified, and no acceptance email is sent. Report-impact verdict at this
checkpoint: isolated behavior validated and original evidence preserved;
production before/after scheduling and final replay acceptance are pending.
Runtime artifacts under runtime/ and /opt are intentionally not committed.
