# R5 independent-domain deployment and retained-P3 gap

Status: **INDEPENDENT_DOMAINS_DEPLOYED_AND_REPLAY_VERIFIED**.
The retained P3 environment transition and its current report-chain acceptance
remain pending. This is not a claim that every R5 entry or the overall goal is complete.

The owner authorized deployment, then personally used the local authenticated
review command on 2026-09-11 at 08:54 CST. Both PostgreSQL Reviewer approvals
were read back and matched to the protected receipt before Operator execution.
Approval expires on 2026-09-12 at 08:54 CST. The agent did not execute the human
approval path. Reviewer logins returned to NOLOGIN with no stored password.

The reviewed package index is
`171a39b2b29eea1e0de74347637c43210471cbe8519147a00b8fd0e91ca61e8d`;
the actual review receipt SHA-256 is
`81fd1c9dd564fa360d3675387d58631efdedcf23c4f5b7e618ea6c6c23f4c9e2`.
PRs #427–#440 were already merged before these operations. Their tests and merges
were engineering evidence, not the deployment approval.

## Actual installations and authority

The root-owned release at `/opt/dehps/releases/control-refactor-r5` was copied
from verified component manifests and reverified after installation: 14,665
regular files, five symlinks and 2,855,910,941 bytes including manifests and CI
evidence. Runtime users cannot modify the installed source or dependencies.

| Domain | Worker UID:GID | PostgreSQL UID:GID | Database | Cluster ID |
| --- | --- | --- | --- | --- |
| learning | 61010:61010 | 61012:61010 | dehps_control_learning | 7683837206678351900 |
| observer | 61011:61011 | 61013:61011 | dehps_control_observer | 7683837211742154779 |

The four accounts have no login shell, home, password or permanent Docker group
membership. The trusted fixed launcher receives administrative Docker access
only through its host unit. Each actual worker container receives its own UID,
readonly input/credential mounts and private database socket, with no IP network
or production credentials. PostgreSQL has no published ports, requires SCRAM on
local connections and has fsync/synchronous_commit enabled. Domain socket owners
and modes were inspected. Schema installation used the accepted transactional
installer and exact four SQL file hashes.

Each separate database has request ID 1 and execution ID 1. Engineer and Operator
map to the same implementing Codex task principal; the real human Reviewer maps
to the administrator-verified local `ark` identity. Login OIDs, permissions,
request contents, release identity, approval expiry and absence of revocation
were checked against the actual database. Before human review, Engineer and
Operator approval calls and unapproved execution were denied, with all approval,
execution and commit counts remaining zero. Identity labels were not used to
grant permission.

## Canonical execution, replay and repeat invocation

| Evidence | Learning | Observer |
| --- | --- | --- |
| Release | d0ad80169b25143341feb2baaf5f78d4f212c1f69bec62dc50eceb381db347de | 3ae2211b57e6af9ae471d8cc403cb905a62a1b5afde007adfd38af23d757478c |
| Initial run | 397ddd48-ea7a-4071-baab-13664bf4d1e7 | 16703890-bbea-4a00-941c-d9b6fe27bf8e |
| Replay run | 7c074e50-adbc-4d8c-b0cb-cabcd7efd2e3 | fb751cde-ecd6-44ca-94fa-e11e90d1d271 |
| Repeated canonical run | 8ea8d014-d88d-4275-86ea-329ad16724c9 | 2fbda29a-e6f0-4b1f-8c58-89984c81b7d4 |
| Final manifest | f4087b61afa900eb8957b28fa08c6468041bd439c68d0bb9b5657c81c16fc2ae | 4cf8b6771e95f4ffcb62cd2ba5f7c6f05189b7f2fdbe2f00f057f8c1f91eecb2 |
| Tasks / attempts / commits / registered artifacts | 5 / 5 / 5 / 5 | 2 / 2 / 2 / 2 |
| Persisted canonical execution events | 10 | 4 |

Both first executions used the installed systemd worker instances and their
approved fixed images. The five learning phases were fit, chronological
evaluation, analysis, archived Top-100 verification and report. The two observer
phases were the frozen 2026103 decision and complete diagnostic report.

Replay used a fresh systemd process under the same domain identity and fixed
launcher, changing only the action to replay and mounting runtime readonly.
All rows in all 23 authority/store/mainline tables were hashed before and after;
every table was unchanged. All runtime file contents and modification times were
unchanged as well: six learning files and three observer files. Replay returned
the same manifest and artifact identities with a new run ID.

Starting each completed canonical worker again also succeeded. All 23 tables,
attempt counts, registered artifacts and artifact bytes/mtimes remained
unchanged. Only the domain's status projection changed to describe the fresh
run. There was no second business result or new scientific experiment. These
deployed checks supplement the R2/R4 real-PostgreSQL crash, lost-acknowledgment,
restart and no-refit tests; they do not claim a production crash was injected.

## Consumers and scientific result

The authorized consumer used a separate readonly container with the respective
domain UID to read the exact report object returned by canonical replay. It
verified SHA-256 and size before parsing the report. Learning report object
`2dec9060c0fc37431ad0145ccbcef84f67aae0c3f7d0d180ceea4e97985c42b8`
is 4,367 bytes and matches the accepted historical result. Its conclusion is
**证据不足**, and `new_scientific_experiment` is false. Observation report object
`d506d64f2f920fb545dffc73be65e9b14a07e37747debc65d221ca73e599705b`
is 7,688,722 bytes, has all 100 ticket diagnoses and retains OFFLINE_VERIFIED
historical/post-hoc semantics. It is not a newly issued prediction.

The two actual status containers run as the domain UID, have a readonly root and
only one readonly status-directory mount, and publish on 127.0.0.1:3311/3312.
Actual write probes returned EROFS. The learning HTTP endpoint displayed the
current RUNNING identity during execution. The finished observer projection
later returned UNKNOWN/STALE at its configured 60-second age limit; timestamps
were not refreshed to manufacture a current success. These endpoints say
OPERATIONAL_PROJECTION_ONLY and durableCompletionVerified=false. Durable
completion is established by the registered objects and replay above.

| Integration step | Deployed proof |
| --- | --- |
| Goal and task definitions | One canonical Goal and 5/2 persisted task definitions in the separate domains |
| Resolver and Ready Queue | Accepted Coordinator resolves the approved plan through existing canonical implementations |
| Supervisor/capability execution | Installed fixed entry, domain Operator login and recorded fresh run IDs |
| Immutable artifacts and status | 5/2 commits and registered artifacts; domain-specific status projection |
| Next consumer | Each successor phase consumes its committed predecessor; final reports read by the authorized readonly consumer |
| Deterministic replay | Fresh process, same manifest/artifacts, unchanged persisted tables and runtime bytes |

**YES — validated by unified mainline execution and replay** applies to these
two independent control domains. It does not assert migration into the formal
P3 executor or completion of the pending legacy transition.

## Single writers, P3 and report impact

The old observer Request 815 was cancelled through the existing
`AgentRequestService.cancel` transition under the authorized Operator identity,
with the real review receipt attached as provenance. Its old decisions and
execution records were preserved. The old observer service and timer were
already inactive; their original files were moved intact to
`~/.config/systemd/user/retired-r5-20260911/` and replaced by persistent masks.
The old learning transient process remained terminal and was not restarted.
V11 remains retired and masked. Neither rollback nor the new dispatcher can
reactivate those old writers implicitly.

Formal P3 still uses the original ac0ef78 checkout and the cd069c1 resident
checkout. No P3 service was restarted and none of the seven candidate fixed-
environment overrides has been installed. Independent execution, repeat runs,
replay and consumers therefore did not require a P3 restart or production mail.
The one-time legacy environment transition remains explicitly pending.

The formal baseline is not healthy: the 08:54 forward attempt failed with
DeadlockDetected before the new domains started. The old resident process
remains alive, but its current heartbeat reports `dispatch_performed=false` and
failure to parse the existing `structural_decision_utility` objective class.
The public manifest still marks a routing-compatibility task and the 2026105
settlement task as running. Those records alone are not proof of live execution
or safe recovery. No historical state was reset to conceal these failures.

2026105/pre has its original sent ledger entry from 2026-09-10 17:00:49 CST;
the post-draw delivery has no sent entry in the observed ledger. The 2026104
historical gap remains explicit. The next scheduled pre-draw delivery is a
future event, not acceptance. This deployment sent no mail or historical resend.

Report-impact verdict: the new domains have complete registered reports and
verified replay. Their installation did not change formal source, scientific
contracts or mail records. **Formal P3 continuity/current-cycle acceptance and
its fixed-environment transition are not complete.** The existing failure does
not erase independent-domain engineering acceptance, and the independent
acceptance does not establish that the formal report chain is healthy.

## Installed-ownership verification correction

The original offline probe expected EROFS for a write-open. Actual root-owned
installed files can be rejected by discretionary permissions first, yielding
EACCES. The corrected probe requires ST_RDONLY on every tested source/dependency
path, then accepts either EROFS or EACCES. Thus an ordinary permission denial
cannot conceal a writable mount.

The actual installed bundle passed all nine fixed-entry import/help checks,
source/interpreter path checks, NoNewPrivileges, readonly data mounts and the
three source/dependency write denials in 35.640 seconds. The launcher bytes
remained `fbd878fa8f8c4aca91b47c3cc4cb109d98eec57b6d34e5b05324b817b143fed2`.
A separate negative probe on the real writable host filesystem failed at the
ST_RDONLY assertion before attempting a write-open. The initial failed probe
and the initial negative-harness traceback expectation were retained.

These are offline checks. They do not claim that the retained release has run
a real formal cycle, nor do they authorize clearing the pending P3 gap.

Host-local logs, protected review receipt, row/file snapshots, readable reports,
namespace probes and operation scripts are retained in the task's
`r5-activation-20260911` evidence directory. Credentials and generated runtime
objects are not committed to this repository.
