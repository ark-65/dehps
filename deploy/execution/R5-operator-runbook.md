# R5 installation and rollback packet

Status: **CANDIDATE — NOT INSTALLED OR APPROVED**. These are proposed production
actions for independent review, not evidence that they happened. The account
numbers, paths, resource owners and service commands below are fixed choices.
An administrator must verify real principals and record actual cluster/admission
identities before the corresponding execution step. Fixture identities cannot
fill these fields. Do not silently change this packet when a preflight fails.

## Resources and authority

| Domain | Worker / primary group | PostgreSQL UID / group | Database | Status port |
| --- | --- | --- | --- | --- |
| learning | dehps-learning / 61010 | dehps-learning-db / 61012:61010 | dehps_control_learning | 127.0.0.1:3311 |
| observer | dehps-observer / 61011 | dehps-observer-db / 61013:61011 | dehps_control_observer | 127.0.0.1:3312 |

The host's existing UID 999 is dnsmasq and GID 999 is systemd-journal. Do not
assign new data/socket ownership to 999 simply because that is the image's
postgres UID. The official pinned PostgreSQL image has been exercised under a
separate numeric UID, using its arbitrary-user initialization support, private
password file and pre-owned data/socket directories. New accounts have no login
shell, password or home. None has permanent Docker group membership.

The trusted fixed host worker launcher alone receives `SupplementaryGroups=docker`
through its system service. Docker access is administrative authority. Its root-
owned source/configuration and closed arguments are part of the trusted control
layer. The worker container receives its primary UID/GID only, no supplementary
Docker group, host home, Docker socket or production credentials. Host service
namespace restrictions do not constrain the Docker daemon: the launcher's actual
container mounts, user, network and image checks provide that separate boundary.

The database and status host services are trusted root Docker clients. Database
processes run as their dedicated UIDs, and status processes run as the respective
worker UID with only a read-only status-directory mount. Database/worker
containers have no IP networking. Status HTTP publishes only on loopback.

## Immutable bytes to install

Use the staged package recorded in the R5 experiment report. Validate every
manifest and archive hash before copying it to
`/opt/dehps/releases/control-refactor-r5`. Refuse an existing destination rather
than overwriting a prior release. Install only after the approved package digest
is recorded. Preserve executable bits while making all non-secret bundle files
root-owned and readable but unwritable by runtime accounts. Do not follow its
symlinks into external trees when changing ownership or permissions. Keep the
original workspace, venv, frozen archives and runtime data intact.

| Component | Bound identity |
| --- | --- |
| Learning release | d0ad80169b25143341feb2baaf5f78d4f212c1f69bec62dc50eceb381db347de |
| Observation release | 3ae2211b57e6af9ae471d8cc403cb905a62a1b5afde007adfd38af23d757478c |
| PostgreSQL image | sha256:2203e6282d9e7de7c24d7da234e2a744fb325df366a3fd8ed940e8abbee39527 |
| Status image | sha256:bb0a4afd351a78b090eb4fde4fd66db7d3263d942e7ee323a102a099c6063859 |
| Status source | e7503b26e034dfcc755902eeb68a43edfd9021d4 |
| Retained formal sources | ac0ef7832c6f13c7500b3f7d67731420b575c0f4 and cd069c15110b0af0f3a83ff619272c14e4748edc |

Restore the two worker archives using the existing launcher's `restore` command
and the archive hashes from the staged manifests. Load the status and PostgreSQL
archives and inspect their actual IDs. No pull or build is part of production
startup. `docker-client/` in the installed bundle is an empty root-owned directory
used as `DOCKER_CONFIG`, so developer Docker settings cannot select another daemon.
The system units set `DOCKER_HOST=unix:///var/run/docker.sock` and a fixed PATH.

## Preflight and installation order

1. Record the Reviewer account/approval event, administrator performing principal
   mapping, Operator identity and exact approved package digest. Confirm each
   review is independent of its implementer/executor. Verify no revocation. Owner
   continuing engineering consent and a green PR are not these approval events.
2. Refresh production source hashes, effective units/timers, in-flight P3 execution,
   exact current issue/report deadlines, report/input digests and delivery ledger.
   Preserve the explicit 2026104 gap. Classify future reports as pending. This
   installation does not authorize a resend or change any scientific conclusion.
3. Reject collisions for all four names, UIDs 61010–61013, groups 61010–61011,
   ports 3311/3312, `/etc/dehps/control`, the target input/runtime paths, the six
   service instances and container names. Inspect existing objects; never adopt
   them merely because a name matches. Recheck that unit files match the reviewed
   bytes. The supplied sysusers file may not be used to modify an existing account.
4. Install the reviewed bundle; copy the supplied sysusers/tmpfiles definitions to
   `/etc/sysusers.d/dehps-control.conf` and `/etc/tmpfiles.d/dehps-control.conf`.
   After the collision audit, run `systemd-sysusers` on that exact file, then
   `systemd-tmpfiles --create` on that exact file. Record resulting passwd/group
   entries, directory owners/modes and absence of permanent Docker membership.
5. Create `/etc/dehps/control/{learning,observer}` owned root and the corresponding
   domain group, mode 0750. Administrator creates distinct random database admin
   passwords through the approved secret mechanism. Each `admin-password` file is
   owned by its PostgreSQL UID, mode 0600. Never put a password in a shell argument,
   repository, unit, report or returned log. No Reviewer credential is given to
   this engineering agent.
6. Write root-owned mode 0600 `postgres-uid.env` in each domain directory:
   learning `DEHPS_POSTGRES_USER=61012:61010`, observer
   `DEHPS_POSTGRES_USER=61013:61011`. Install the three reviewed service templates
   into `/etc/systemd/system`, then `systemctl daemon-reload`. They have no timer,
   automatic restart or installation target. Start only
   `dehps-control-postgres@learning.service` and
   `dehps-control-postgres@observer.service` for this installation.
7. Service process creation is not readiness. Inspect the exact CID from each
   root-owned `/run/dehps-<domain>-postgres-control/container.id`, its expected
   domain/role labels, image, user, mounts, no network and no published ports.
   Connect through that domain's host socket using its private admin credential.
   Require final postmaster PID 1 (not the temporary init server), empty
   `listen_addresses`, all local HBA rules SCRAM, fsync/synchronous_commit on, and
   the actual `pg_control_system().system_identifier`. Save non-secret results.
8. Administrator creates the exact empty domain database, records its new cluster
   identity and constructs the closed installer specification described in README.
   Bind the actual independently verified engineer/reviewer/operator principals
   and the four reviewed SQL hashes. Use the installer with an explicit private
   admin JSON whose DSN names this database. Reject ambient libpq variables.
   Installation must return `INSTALLED_LOGINS_DISABLED`, zero approvals and zero
   executions. Preserve its result and spec digest.
9. The administrator activates each login and delivers its credential exclusively
   to its real owner through the approved channel. Verify actual login OID/name,
   principal/domain mapping and minimal grants. Reviewer reviews the exact plan
   and release through that authenticated role; Operator admission is separate.
   Do not re-use the fixture passwords or write approval rows directly.
10. Copy the already verified input packets into new
    `/opt/dehps/inputs/control-r5-{learning,observer}` directories, owned root and
    their domain group, directories 0550/files 0440. Verify the entire original
    per-file manifest. Add the exact release descriptor and `execution.json`
    containing the real request ID and unchanged approved plan. Record new packet
    hashes; do not alter the frozen files to fit an admission. Runtime stays under
    `/var/lib/dehps/control-<domain>`, owned by that domain UID, mode 0700.
11. Put the Operator's scoped `{dsn,database,role}` JSON at each domain's
    `operator.json`, owned by its worker UID, mode 0600. DSN host is
    `/run/dehps-postgres` inside the worker; port 5432; all fields are explicit.
    That role has no production login or cluster-owner privilege. Write the
    root-owned domain `release.env` described below. Recheck installed sources,
    credentials ownership, readonly inputs and actual socket ownership before run.

`release.env` for learning:

```text
DEHPS_RELEASE_DESCRIPTOR=/opt/dehps/releases/control-refactor-r5/learning-release.json
DEHPS_RELEASE_SHA256=d0ad80169b25143341feb2baaf5f78d4f212c1f69bec62dc50eceb381db347de
```

For observer, use the installed `observation-release.json` descriptor and
`3ae2211b57e6af9ae471d8cc403cb905a62a1b5afde007adfd38af23d757478c`.
Keep this host-launcher environment file root-owned, mode 0640, domain group.

## Canonical run, replay and consumers

After single-writer checks below, start one explicit admitted instance with
`systemctl start dehps-control-worker@learning.service` (or `@observer`). Do not
start a P3 service as a dependency. The fixed launch command is in the reviewed
unit; it uses the accepted image, `/inputs`, `/runtime`, scoped credentials and
private PostgreSQL socket. Record fresh systemd invocation ID, container ID,
canonical execution/run ID, plan/release identity, all immutable task artifacts,
registered downstream records and the actual status projection. A skipped
Condition, successful `systemctl` command or service exit alone is not acceptance.

For deterministic replay, run the **same fixed launch command** under the same
trusted host service identity, changing only `--action run` to `--action replay`.
Do not start a competing legacy runner. Capture database counts and artifact/status
bytes before/after. Replay must return the same manifest and artifact identities,
a fresh replay run ID, no new commits/registrations and no rewritten status.

The replay result identifies every immutable artifact by schema, SHA, size and
relative object path. The authorized Operator reads those exact registered report
objects through a one-time read-only mount under the domain UID, checks SHA/size
against the successful canonical replay result, and records the readable report
and provenance in deployment evidence. This is inspection of committed output,
not another completion path or new training. Do not substitute a status endpoint
for this report check or create an extra report-serving framework. Preserve the
original learning report's conclusion, “证据不足”.

After obtaining the real admitted execution ID, write root-owned `reader.env`
containing only `DEHPS_EXECUTION_STATUS_SOURCES=` followed by the single-domain
JSON binding from README. Use the actual plan/release/execution identities, root
`/status` and maxAgeSeconds 60. Never use a fixture ID or refresh a stale timestamp.
`reader-uid.env` contains `DEHPS_READER_USER=61010:61010` and
`DEHPS_READER_PORT=3311` for learning, or `61011:61011` and `3312` for observer.
Start `dehps-control-status@<domain>.service`, inspect its exact CID/mounts and
verify the localhost `/execution-status/<domain>` response. Its evidence remains
`OPERATIONAL_PROJECTION_ONLY`; an old completed run becoming STALE is expected,
not permission to retrain or rewrite success. Stopping this reader cannot restart
its worker or P3.

## Single writers and retained formal services

| Entry | Reviewed transition | Preserved boundary |
| --- | --- | --- |
| Old prediction-error observation service/timer | Remain stopped; mask exact old service and timer after inspecting their effective names; revoke the old observer Operator authorization through its legitimate decision entry | Preserve old tasks, failures, records and replay artifacts; never automatically unmask on rollback |
| Old learning 20260905 transient run | Confirm original process is terminal; no new prepare/run scheduling; record legacy writer retirement | Preserve original release, isolated DB, checkpoints and semantic replay; the old replay CLI can itself write files, so inspect copies/read-only outputs rather than invoke it as a new completion path |
| Common resident research supervisor | Retained fixed cd069c1 implementation; its script constructs ResearchEvidenceSupervisor only, no new learning/observer registration | Do not alter formal Goal/DAG or dispatch new domain tasks into it |
| New domain workers | One admitted canonical worker per domain, persisted lease/fence plus systemd instance | Repeated committed work uses actual verification/recovery and cannot create a second business result |
| New status readers | One readonly process per domain | No computation, database credential, mail or write authority |
| Formal forward/pre-mail/post-mail/P4/watchdog/draw-sync | Apply only the separately reviewed seven fixed-release drop-ins and nine named retained launcher commands | Preserve original source paths/digests, contracts, environment files, hooks and schedules |
| V11 | Preserve masked, retired state; no Request or activation | No rollback branch may reactivate it |

For the old observer, refresh the exact Request key
`operator-pr420-observation-release-20260909` and its current decisions. The
observer script requires its approved/executing/completed status; a valid
revocation must make that exact check fail. Do not forge a different actor label
to revoke it. An administrator with general production access remains trusted;
the single-writer claim concerns approved/scheduled entrances, not an assertion
that a machine administrator cannot deliberately run arbitrary old Python code.

Read-only inspection on 2026-09-10 found Request ID 815 still `executing`, while
`dehps-prediction-error-observation.service` was inactive (MainPID 0) and its
timer disabled/inactive. The old learning transient service had MainPID 0 and
exit status 1 from 2026-09-05. Retire the exact observer request using the existing
`AgentRequestService.cancel` transition with the legitimately authenticated
authorized actor and production scope; executing -> cancelled also stops its
active execution record. Preserve decisions 3474–3477. Their historical actor
strings are audit data, not proof of a currently independent Reviewer identity.
No cancellation or service change was performed by this engineering inspection.

The one-time retained-P3 environment transition is separate from activating an
independent experiment. Capture all effective drop-ins first. Quiesce only at a
verified safe boundary with no in-flight formal commit/delivery; list any resident
supervisor/watchdog stop/restart explicitly in the approved operation. Install the
fixed root-owned bundle and candidate overrides together. The bwrap launcher
supplies readonly source/dependencies and private temp space; its accompanying
systemd namespace-property changes cannot be installed alone. Record new source,
interpreter, process invocation, canonical execution/replay and exact current
report evidence after transition. If the safe boundary is unavailable, leave the
old services untouched and keep this transition pending. Independent research
must not restart P3 as a routine operation.

## Stop and rollback

Stop only the named new worker/status/database instances involved in the accepted
operation. Preserve their journals, invocation IDs and root-owned CID files. A
Docker client killed or a systemd failure is not proof its container stopped:
inspect the exact recorded CID and labels before removing it. Do not stop an
unrelated container merely because it occupies an expected name. RuntimeDirectory
preservation deliberately leaves a stale CID file after exit; archive it only
after proving that exact container is terminal, before a new explicit start.

Do not drop a new database, delete data directories/objects, revert immutable
commits or delete failed events. First installation has no earlier independent
writer to restore: mark it unavailable while preserving committed work. If a
previous accepted release exists, restore its pinned archive and verified binding
only after checking committed-artifact compatibility; replay before new work.
An unknown SMTP outcome requires reconciliation, never a blind retry.

For a failed formal compatibility transition, archive/remove only the newly
installed seven overrides and restore the captured effective configuration after
verifying original source/venv bytes still match the baseline. Resume only the
approved retained executor at a safe boundary; do not re-enable old observation,
learning schedules or V11. If restoring development-dependent launch paths is
temporarily necessary, label this as rollback to the old arrangement, not proof
of fixed-release acceptance. Record the report chain, delivery ledger and next
timer triggers again; future delivery stays pending and missed deadlines remain
explicit gaps.

## Remaining admission facts

This packet cannot claim production readiness until the independent Reviewer,
administrator/Operator route, package review and real mappings are known. Initial
cluster IDs and request/execution IDs necessarily arise during their ordered
installation/admission steps; record them before dependent execution, never
invent them in advance. The supplied units, static validation, isolated UID tests
and offline image restores do not prove a deployed service or actual report cycle.
