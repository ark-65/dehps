# PR420 conflict resolution and merge acceptance

Engineering Request 811 / execution 652 continues under the user's 2026-09-09
instruction to resolve conflicts and merge without disrupting the main project.
The existing approved request and running execution were checked again against
AgentAuthorityPolicy (`engineering`, `modify_code`, `development`: authorized).

## Scope and pre-change report state

One goal: integrate current main into PR420, retain both lines' meaningful
validation, and merge the ready PR after checks. Non-goals: production checkout
updates, supervisor restarts, timer installation, SMTP, V11, new learning rules,
Formal P3 changes, and historical evidence/source-contract changes.

The existing observation Goal, Ready conditions, runner, upstream/downstream
artifacts, evidence rule and consumers remain as declared in
`2026-09-05-pr420-mainline-closeout.md`. Code merge does not complete production
observation integration or real-cycle learning acceptance.

Baseline main: `bd32579e7210dc67ed51f38e4072c02e1406b0e7`.
Baseline PR head: `955dbf254dbafaed3f65c58f9027b7718e1d876c`.
The original PR head's four GitHub worker shards and aggregate pytest check all
passed. New merged-source checks are still required.

Expected issue: 2026105, draw date 2026-09-10, Asia/Shanghai. The normal pre-draw
mail deadline is 17:00. Registered refit, predraw and predraw replay completed
on 2026-09-09; settlement is waiting for the audited draw. Delivery is
PENDING_DELIVERY. The 2026103 post report was sent at 2026-09-09 10:14:16 +08:00.
2026104 remains a missed pre-draw issue; there is no retrospective prediction
or fabricated return report.

Pre-existing runtime problems: the resident unified supervisor reports invalid
`structural_decision_utility`; the post-report poll had a database deadlock at
14:59 and subsequently completed a successful poll. These are not silently
cleared by this code merge.

Before evidence is retained outside Git in
`runtime/pr420-merge-20260909/before.json` in this independent worktree. It
captures exact report task states, registered artifact identities and raw
hashes, existing runtime source hashes, live-main commit, and timer states.

## Conflict and dependency audit

The only merge conflict is the test for source partition coverage in
`tests/test_m4_roadmap_v2_1_hardening.py`. Resolve by retaining current main's
explicit learning-module coverage and all original frozen-partition counts,
pairwise disjointness, dynamic total count and complete worker coverage.

PR420 adds standalone observation modules and an uninstalled observer timer.
The byte audit verified all 690 existing runtime source/unit/schema files are
unchanged relative to current main. No existing runtime entry imports the new
observation modules. Existing notification and P3 source-contract digests remain
`9831490a024664a5023c88d660d8d7c4be2e06be5db3456834ff65abf86d2b82` and
`139ddc97ce1d81ea4e6182359f8391532ed1911090db004bcdf9ebcdea5f9493`.
The resolved conflict file is byte-identical to current main. New observation
execution remains guarded by an exact-source approved Operator request.

## Validation and acceptance

Local validation uses the existing worker virtualenv with this independent
worktree on PYTHONPATH and single-thread BLAS settings. No dependencies were
installed into the live environment.

- Focused observation, leakage, failure isolation, notification, Formal P3,
  source-partition and schema checks: 127 passed.
- Current-main recovery and offline-learning regressions: 10 passed, 6 skipped.
  Skips are explicit opt-ins for isolated PostgreSQL/incident clone and learning
  integration; production database tests were not enabled for this merge.
- Exact-issue read-only preflight passed for the opened 2026103 report and the
  2026105 sealed prediction. A second reconstruction reproduced the full 2026103
  preview exactly, including all 100 tickets and complete 33-red/16-blue labels.
  2026105 restored all four frozen artifacts and replay exactly, using history
  through 2026104. No same-issue labels or post-draw prediction were introduced.
- All 33 registered artifacts in the before snapshot remained byte-identical.
  The main worktree remained clean at its original commit. The mail ledger was
  read without invoking its write/lock/delivery methods.

Current main's earlier CI run 34301992173 had 16 actual test failures, primarily
historical source fixtures. That is a failed baseline, not a passing result or
a quota exception. PR420 contains the corresponding archival fixture repairs;
the exact combined source must pass local and GitHub validation before merge.

Historical fixture suite and new GitHub CI/merge results are recorded in the PR
and `runtime/pr420-merge-20260909/` acceptance evidence. They are not inferred
from the original PR head's successful CI.

| Report acceptance item | Evidence and disposition |
| --- | --- |
| Impact | NO_RUNTIME_IMPACT for this code-merge-only round: all existing runtime files unchanged; no new runtime import path or installed observer unit |
| Expected / observed issue | 2026105 sealed and replayed before its 2026-09-10 draw; 2026103 opened report verified; 2026104 remains missed |
| Required sections / provenance | Exact reconstructed base report and full additive preview; registered frozen parent proof; 100 tickets, 33 red and 16 blue labels |
| Mainline / replay | Original registered identities preserved; new observation execution/replay tested in isolation; no production execution claimed |
| Consumer | Existing report consumer uses unchanged code and artifacts; observation activation and new learner ingestion remain pending |
| Delivery | Existing 2026103 post ledger status sent at 10:14:16 +08:00; 2026105 PENDING_DELIVERY |
| Scheduling | Existing timers retained; next pre-mail 2026-09-10 17:00 +08:00; no install, restart, reschedule or test mail |
| Preservation | 33 registered artifact hashes, 690 existing runtime files and pre-existing delivery records audited before/after |

Production observation integration: **NO — INTEGRATION_PENDING**.
No production deployment or real-cycle acceptance is claimed by this round.
