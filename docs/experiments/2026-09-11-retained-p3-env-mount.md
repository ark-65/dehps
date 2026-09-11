# Retained P3 environment mount correction

The first fixed-release transition failed before either resident entered Python
business code: bubblewrap could not create `.env` inside the already readonly
source bind. The earlier offline verifier omitted that execution-only file bind,
so its successful import and frozen-contract checks missed the packaging defect.

The launcher now requires an empty, regular `legacy/ac0ef78/.env` mount target.
Offline inspection performs the same readonly file mount using this empty input;
execution continues binding the original host environment file. Credentials never
enter the release. The verifier requires an empty readonly file at the original
path. Missing, nonempty and symlink targets are rejected before launching.

The corrected package must manifest the empty target as well as the changed
launcher/verifier. Preserve the failed package and its review receipt. Do not
reuse its digest or approval for changed bytes. This is one packaging correction;
frozen Python sources, dependencies, scientific contracts and results are retained.
No new model, task recovery, resend, V11 operation or independent-domain change.

## Actual transition and rollback

Human Operator Request 816, decision 3481, was verified against the root-owned
receipt and actual formal database. Canonical execution 657 started. At
2026-09-11 10:47:59 Asia/Shanghai, four timers were paused after recording their
original activation. All five oneshots were terminal, the two residents had no
children and the formal database had no other active transaction/session. Both
idle residents were stopped and the seven exact reviewed overrides installed.

Both resident starts failed with `bwrap: Can't create file at
/home/ark/workspace/dehps/.env: Read-only file system`. The reviewed rollback
removed and archived exactly those seven overrides. All eleven original effective
unit configurations matched their recorded bytes. Both original residents and all
four timers were restored by 10:48:08. Execution 657 and Request 816 are FAILED
with this rollback recorded through the canonical AgentRequestService.

## Report impact

This was a brief, reviewed production scheduler/resident interruption. It is not
`NO_RUNTIME_IMPACT`. Before/after snapshots at 10:45:35 and 10:49:32 show identical
formal manifest, running-task immutable events and complete mail ledger. No task
state was reset and no delivery was added. The pre-existing unsupported objective
class, 2026105 settlement deadlock/post-report gap and 2026104 missed deadline
remain explicit. 2026105 pre delivery is historical evidence; the next pre timer
at September 13 17:00 is pending and cannot prove current report acceptance.

The new correction is engineering preparation. Fixed-release deployment and
current-cycle report/replay/consumer acceptance remain pending. Independent
learning/observer deployment and replay stay accepted; the learning conclusion
remains 证据不足.

## Validation

- Six focused tests passed: three unsafe environment targets and three real Git
  history/tamper cases.
- Full actual readonly namespace acceptance covers nine frozen entry points,
  exact source/interpreter identities, Git ancestry, original runtime/source
  contract functions, and the environment file mount: all passed. The original
  defective package is now rejected for the missing target before launch.
- Evidence directory: `r5-env-mount-20260911`; failed operation and rollback:
  `r5-formal-transition-20260911`, under the task's durable evidence directory.
