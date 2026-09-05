# PR420 integration closeout

Engineering Request 811 / execution 652 records the current explicit user authorization.
One goal: finish CI correctness, preserve abandoned changes, and connect prediction
observations to actual mainline execution. No Formal P3 prediction changes, old
report recovery, V11 restart, historical resealing, or automatic model promotion.

## Declared integration contract

| Item | Contract before implementation |
| --- | --- |
| Goal | dehps-mainline-prediction-error-learning |
| Supported node | Existing Formal P3 refit/predraw/replay and opened per-issue post-report/replay |
| Ready | Exact registered parents verified; report additionally requires opened outcome and stored decision |
| Runner | Observation capability dispatched by ResearchEvidenceSupervisor in its own observation control plane |
| Upstream | Frozen dataset/model, candidate/baseline/checkpoint/report/replay; opened settlement/payout/report/replay |
| Downstream | Registered immutable decision, report and complete red/blue sample; deterministic replay |
| Projection | Observation supervisor status, execution ids, ready queue and real-cycle acceptance state |
| Evidence | Engineering facts only; no cumulative sealed result read and no scientific decision credit |
| Consumer | Report/sample replay; later separately evaluated learner |
| Decision consumer | Existing Formal gate unchanged; deployment acceptance only |
| Next consumer | Next exact issue record, opened report, sample; no automatic strategy replacement |

Observation scheduling may fail without invoking or blocking the existing P3
prediction, settlement or delivery runner. Integrity failures stop the affected
observation/sample. A real draw cycle must be distinguished from retrospective
mainline verification. Existing frozen modules and original mainline records
remain unchanged.

## CI root cause

The retired bounded lineage check incorrectly applied its frozen source hashes
to current repository bytes. The original release is
`f330f36e42c9e506860ac3634f86d28cced137d6`; all twelve source entries match their
original hashes there. The test now materializes those actual Git blobs, verifies
the original unchanged contract with the existing verifier, and checks that a
one-byte corruption fails. No historical fingerprint or production verifier was
modified. The pre-repair failure log remains in the phase-one runtime directory.
Focused prediction/notification/P3 validation: 53 passed after this repair.

## Abandoned V11 changes

The three changes belong to Request 808 / execution 649 and the abandoned
20260828 recovery. They are not part of PR420. They were restored in
`/home/ark/workspace/dehps-v11-abandoned-preserved-20260905` at the original
`ece499208227de1ac4dff28ddfc6d45ada243620` base, and compared byte-for-byte to
both original files and the retirement backup. The binary patch SHA256 is
`97f4830b63b3dc1c787f7cdaa17a5e65801f995d5aefa57d47e16eb5c90ce200`.
This is preservation, not acceptance or continuation of V11 recovery.

## Delivery state

Merge, deployment, and real-cycle acceptance are separate and remain pending.
This report will be updated with actual validation and deployment evidence.

## Additional CI repairs and validation environment

Historical diagnostic-P4 and forward-feasibility source tests now verify original
release bytes (`b3b905aa...` and `422a7aca...`) with unchanged validators and
contracts. Migration tests load their exact digest-checked historical inputs
from small deterministic gzip fixtures, rather than demanding that today's
production head still equal a past migration boundary. The optional database
cross-check likewise queries the historical completion by digest. Dynamic audit
source coverage retains disjointness, fixed scientific partitions and complete
worker coverage; its obsolete fixed audit-file count is replaced by the actual
partition cardinality.

An initial diagnostic full-suite run was launched through Python stdin, which
is incompatible with tests that spawn new interpreters. Its partial log is
retained, not claimed as validation. The corrected invocation uses Python `-c`
as CI does, exports this worktree's PYTHONPATH for child interpreters, and keeps
all six pre-existing CI deselections unchanged. No new checks are deselected.

Observation tests exercise the real supervisor dispatcher, immutable file
publication, registered decision/report, downstream readiness and replay using
memory-backed storage. Real frozen parent/read-only checks passed for 2026102
and 2026103; 2026102's audited label availability is
`2026-09-03T22:00:42.330236+08:00`. The next actual draw is 2026103 on
`2026-09-06T21:15:00+08:00`. Acceptance requires both a decision registered before
that draw and a later registered, replayed report with complete labels.
