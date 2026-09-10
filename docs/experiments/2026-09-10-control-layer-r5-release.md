# R5 controlled release preparation

Role: Engineering under the continuing R0–R5 owner consent. Status:
**PREPARATION_IN_PROGRESS**, not release-ready, reviewed or deployed.

Latest engineering continuation: PR #438 merged as
`3d0e5395414d64c2108360d156d2d5800cc0fc68` at 2026-09-10 16:04:14
Asia/Shanghai. All six checks of CI `34451541677` passed on exact source
`9c0e0b971e6c3832b3f67cff194a873575b8ab88` before merge. Twelve PRs
(#427–#438) are now merged; this does not complete R5 deployment.

The remaining status-consumer permission gap is addressed by a separate
credential-free entry for the existing API reader. Each reader uses its domain's
UID inside a read-only container and receives only that domain's status directory.
Canonical directory/file modes stay 0700/0600. The host caller's same-UID R4 HTTP
test was insufficient evidence for distinct deployed accounts; the new actual
image test uses consumer UID 65531 versus host UID 1000 and also checks another
UID cannot read. A real canonical failure replaces the previously visible success
without changing committed records. This adds no model, calculation or shared
supervisor behavior. Full deployment identities and service installation remain
pending, including separate immutable report consumption.

Local validation of this consumer change: the actual image/real PostgreSQL test
passed **3 tests in 3.66 seconds**, canonical run
`0d7e7102-9f73-4605-a3b4-82218788f058`. The container used UID 65531, returned
the canonical completion, denied writes with EROFS, denied a different UID with
EACCES, and then returned FAILED after the canonical authority-revocation test.
No committed record changed. Root and credential-bearing starts were rejected.
Node base was pinned to
`node@sha256:2c87ef9bd3c6a3bd4b472b4bec2ce9d16354b0c574f736c476489d09f560a203`.
The build's TypeScript compilation passed. API tests also passed in the local
network-enabled execution environment; the first sandboxed invocation exited in
the existing HTTP-test file and its failure log is retained. No application code
was changed to suppress that failure.

Report-impact verdict for this engineering change: **NO_RUNTIME_IMPACT** on
existing production. The diff adds a separate status entry/image, its integration
test, CI and deployment documentation; it does not modify the existing API entry,
status reader, frozen worker images, scientific code, source contracts, production
units, runtime files, credentials or delivery ledger. This verdict covers the
undeployed change only. Actual deployment and the affected current report cycle
still require their own before/after evidence; old delivery success and future
timers are not acceptance.

Primary goal: package the accepted independent observation/learning entries,
actual resource/identity isolation, retained legacy P3 execution and a reversible
single-writer transition. No new scientific experiment or model is introduced.

Goal: R5 controlled cutover. Ready: accepted R4 releases, complete input/resource
inventory, concrete rollout/rollback commands, independent authenticated review
and authorized Operator execution. Runner: the fixed release launcher and reviewed
service commands. Upstream: exact source/image identities, frozen input artifacts,
current unit/configuration and permission facts. Downstream: deployment records,
one writer per path, unchanged historical evidence and an executable rollback.
Status: preparation/review/deployment/business-cycle labels remain separate.
Evidence rule: actual permissions, source/environment identity, canonical execution,
replay, downstream consumption and before/after report-chain observations.
Decision consumer: independent Reviewer and authenticated Operator. Next consumer:
the deployed observation/learning entries and retained legacy P3 services.

R4 learning PR #436 merged as `505d86c84725a14b997355c9651829bf19ee5c24`
at 2026-09-10 13:59:05 Asia/Shanghai. Its exact head
`e2deaf7cf5a1b3355201cba3d94699abd2bb871e` passed all six checks in CI
`34442256105` before merge (aggregate completed 13:57:21). The prior failed CI
and its test-lease correction remain documented in the R4 report.

## Retained candidate release bytes

| Domain | Release | Archive SHA-256 |
| --- | --- | --- |
| Observation | `3ae2211b57e6af9ae471d8cc403cb905a62a1b5afde007adfd38af23d757478c` | `9de14e4677edcc28c9107e037a45886e14b5d74258d76344ed153b8e837977f8` |
| Learning | `d0ad80169b25143341feb2baaf5f78d4f212c1f69bec62dc50eceb381db347de` | `98e596a2992bdebc801922e77031e508cd99b1f492e2560afb0033d458756b1e` |

Both images were measured and exported by the fixed release archive entry, then
copied to durable task storage and rehashed. Observation archive: 257,184,256
bytes; learning archive: 257,139,200 bytes. These are candidate rollback bytes,
not deployment approval. The package is staged at
`/home/ark/.codex/visualizations/2026/09/09/01a0857a-6a96-7543-bc77-2579d2ad5079/r5-release-package/`.
Generated image/runtime data stays outside Git.

The staged host launcher contains the exact release/context modules and package
initializers from `5f8c1da7967461b784f0b5f150ab3ab691fb977f`, plus a small bootstrap
which selects only that staged package. Its manifest records all five file hashes.
`/usr/bin/python3.14 -I <staged>/launcher/launch.py --help` works outside either
checkout, without the production venv or installed Worker dependencies. The host
Python standard library and Docker CLI remain trusted launcher dependencies;
worker dependencies are bound to the fixed images. Installation must make the
launcher/configuration root-owned and unwritable by runtime identities.

## Live boundaries still to complete

No `dehps-learning`, `dehps-observer` or `dehps-operator` OS accounts existed at the
readonly check. The running legacy supervisor remains PID 7736 in the dedicated
`cd069c1` checkout, while its interpreter still belongs to the original workspace
venv. Forward/mail oneshot services also use that venv and the original checkout.
Base unit files and effective drop-ins must be recorded separately; the supervisor's
effective directory differs from its base unit. Current production source remains
clean at ac0ef78. No source, environment, unit, database or credential was changed.

The final package must include dedicated runtime owners, independently controlled
reviewer/operator logins, protected credential paths and a control database/network
that does not expose production PostgreSQL. A caller-supplied role label or the
test principals from R4 is not production authority. Provisioning mappings is a
trusted administrative step, with its own recorded review and execution.

Legacy P3 code, dependency files and source identity must be preserved as a fixed
compatibility release. A copied venv's editable package hook still points at the
development checkout and cannot be left as an unnoticed dependency. The running
legacy process must not be silently redirected: any required environment/service
transition, quiescence, restart and recovery must appear explicitly in the reviewed
Operator package. Activating an independent experiment does not authorize a P3
restart. P3 stays on its legacy executor; V11 stays masked and unschedulable.

Rollback must preserve all new commits, source archives and historical failures.
The old observation timer is currently disabled after the status collision; a
rollback cannot automatically re-enable that unsafe writer. Single-writer checks
must cover timers, supervisor dispatch, transient/manual processes and downstream
status consumers. A future report trigger is PENDING_DELIVERY, not acceptance.

Report-impact verdict for current preparation: **NO_RUNTIME_IMPACT**. All mutations
are staging/archive/documents, existing runtime commands were only inspected, and
no production launcher or service was invoked. The dated 2026104 gap remains; the
2026105 17:00 pre-draw trigger still needs actual sealing/delivery evidence. This
verdict must be replaced by the actual deployment/continuity evidence at cutover.

## Preparation verification at 2026-09-10 14:27 CST

Both saved image archives were loaded and their original release identities
verified through the staged launcher. Learning restore returned `d0ad80169b25143341feb2baaf5f78d4f212c1f69bec62dc50eceb381db347de`;
observation returned `3ae2211b57e6af9ae471d8cc403cb905a62a1b5afde007adfd38af23d757478c`.
No production service was started by these restore commands.

Frozen inputs are now retained beside the images and compared file by file with
the original exports: learning 2,625 files / 1,511,933,247 bytes; observation
2 files / 332,880 bytes. The copy manifests retain every SHA-256 and byte count.

A separate legacy ac0ef78 clone and dependency environment were staged. The
8,782 regular dependency files match the original environment; the three editable
project metadata entries were preserved outside the active copy. Running the
private interpreter with `-I -B` imported NumPy 2.4.6, Numba 0.66.0, pandas 3.0.3
and psycopg 3.3.4 from that copy, with no workspace directory in `sys.path`.
The verification is saved as `legacy/environment-import-verification.json`.
This proves staged dependency import isolation, not P3 lifecycle acceptance.
The resident cd069c1 source, legacy data paths and effective service configuration
still require an explicit compatible release mapping and reviewed transition.


## Legacy namespace verification at 2026-09-10 14:48 CST

The live inventory contains 25 DEHPS user unit definitions; 53 underlying unit
and override files were hashed. Effective configuration and source hashes are
retained in the staged package. The second source copy is exactly cd069c1, and
all tracked bytes were checked against their Git blob identities: 1,742 files
for ac0ef78 and 1,455 for cd069c1. The source manifest SHA-256 is
`20053876f28eb9c32805178788b9264154824534ab5b58ff3d879404a6ad0517`.

A fixed legacy namespace launcher now covers forward prediction, pre/post mail,
armed P4, the resident supervisor, draw sync and all three performance entries.
It keeps old absolute paths inside the namespace while selecting retained source
and dependency copies. Seven candidate service overrides include the forward
start/stop performance hooks. These overrides have not been installed.

The first shell smoke test exposed a missing empty venv mount target; it failed
before importing worker code. After staging that target, the forward help entry
passed. An actual systemd test then failed with `ProtectSystem=strict` plus bwrap.
Diagnostic isolation showed `NoNewPrivileges=yes` alone works; the outer systemd
user namespace enters AppArmor's `unprivileged_userns` profile, which rejects the
second namespace. No host policy was changed. Candidate configuration uses one
bwrap filesystem namespace, retains NoNewPrivileges and supplies the read-only
root plus private temporary directories itself. See the deployment README for
the indivisible launcher/property changes and the remaining review boundary.

Actual systemd unit `dehps-r5-legacy-acceptance-20260910.service`, invocation
`97053448d7624b22a1cf0a0dfcb86e11`, completed successfully in 35.411 seconds.
All nine offline entry checks passed. The child retained UID 1000 and
NoNewPrivileges; opening either source tree's config or the dependency copy's
NumPy module for writing failed with EROFS. Runtime and output mounts were
read-only during inspection. The verified launcher SHA-256 is
`fbd878fa8f8c4aca91b47c3cc4cb109d98eec57b6d34e5b05324b817b143fed2`.
Evidence: `legacy/systemd-namespace-verification.json` in the staged package.
This is import/permission evidence, not a new P3 canonical execution or deployment.

The owner has been asked only to identify the actual independent Reviewer/account
or approval entry point. Continuing engineering consent is already recorded;
no repeated engineering authorization is requested. The package is still being
completed, and no approval, identity mapping or Reviewer action is fabricated.


## Independent database and socket transport preparation

PR #437 merged as `a879a7b0cdd044811017c334e91503e84c291529` at
2026-09-10 15:20:45 CST. Its head `ba01a1546a57c49f59eedf3e49dea3eca6c8c305`
passed all six checks in CI `34447738058` before merge. Installation work continues
on `codex/control-refactor-r5-install`; that merge did not deploy any service.

The administrator installer now validates the exact PostgreSQL system identifier,
new database owner/ACL, absence of prior data/schema/roles, reviewed SQL hashes and
distinct Reviewer principal. It installs existing migrations and minimal entry
function grants in one transaction. All four roles start NOLOGIN with no password;
no approval or execution is inserted. Tests activate distinct fixture accounts
only in disposable databases. Runtime table access, schema creation, owner-role
assumption, self-approval and Reviewer execution are denied. An unrelated account
is rejected by PostgreSQL's CONNECT privilege; an existing unrelated schema and
its evidence are preserved rather than overwritten.

The host release launcher adds an optional private PostgreSQL socket mount, usable
only with IP networking disabled. It requires a PostgreSQL-owned socket directory,
the runtime primary group and private permissions, mounts it read-only at
`/run/dehps-postgres`, and rejects overlap with runtime/input/credential roots.
The accepted learning image and its frozen scientific code remain unchanged.

A real dedicated PostgreSQL 17 container was tested with no IP network, no
published ports, `listen_addresses=''` and SCRAM for all local connections. Its
fixed image was `sha256:2203e6282d9e7de7c24d7da234e2a744fb325df366a3fd8ed940e8abbee39527`.
Directory owner/group/mode were 999:1000 / 2750; socket mode was 0770. The official
entrypoint needs its internal default socket while initializing; an initial
attempt that replaced that path exited and is recorded as failed. The working
configuration keeps the internal socket and exports only the additional private
one. CI now creates and cleans its own separate socket server, waits for the final
PID-1 postmaster rather than the temporary initialization server, and never alters
the existing test database container.

Final local validation: **17 passed in 21.08 seconds**, including real installation,
transaction rollback, incorrect-cluster/SQL/identity rejection, all five learning
stages over the socket, kernel inspection of the actual running container, fresh
readonly replay and release-schema regressions. The worker had UID 1000, only
`lo`, and a read-only socket mount. Five commits and five artifact registrations
were retained; replay added no database records and changed no status bytes/mtime.
A runtime-owned fake socket and attempting to enable IP networking were rejected.

Accepted image release: `d0ad80169b25143341feb2baaf5f78d4f212c1f69bec62dc50eceb381db347de`.
Run: `9e4fbc4e-9688-438c-95ec-fdd029b3a6ce`.
Replay: `b5c6c505-a793-4216-b83a-65c8e2588924`.
Manifest: `a765e0f38ea4e334a547e7a549ffe14b4e8b7d481d0cab644f2278f50a9a3938`.
Log: `/tmp/dehps-r5-install-final-validation.log`.
These are bounded engineering fixture results, not a new scientific experiment
or production deployment. Earlier fixture failures (missing fixture import and a
connection-time exception lacking SQLSTATE) were fixed without relaxing the
actual PostgreSQL permission denial; their logs remain available.

Report impact remains **NO_RUNTIME_IMPACT for development/staging only**. No new
production account, control database, service, credential or authority mapping has
been installed. Reviewer identity remains requested, not fabricated. The final
Operator package still needs exact installed ownership, active entry/consumer
mapping, reviewed transition/rollback and real report continuity evidence.


The socket acceptance was strengthened to restart the actual test PostgreSQL
container after all five commits and before fresh-process replay. **17 checks
passed in 20.82 seconds**. The same database records survived socket recreation;
replay kept every artifact reference and left the status bytes/mtime unchanged.
Run `247278da-e1c4-42de-ad27-fd4edca1f2be`, replay
`773ff1b7-8284-445f-a0f6-713e3a1a4419`, manifest
`560b557ddd2634699405afb9443b5560bddc8537cbd24adddd803b33cb5fdf70`.
The kernel probe still found only `lo`, UID 1000 and a read-only socket mount.
Log: `/tmp/dehps-r5-socket-restart-validation.log`.

The administrator credential reader opens with O_NOFOLLOW and O_NONBLOCK before
checking the descriptor type/permissions. A wrong FIFO path cannot hang before
the regular-file check; public files and symlinks also remain rejected. This does
not generate, activate or consume any real Reviewer credential.
