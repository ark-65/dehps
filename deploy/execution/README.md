# Retained legacy P3 release preparation

These launchers prepare the R5 compatibility release. They do not approve or
deploy it. Formal P3 keeps its original executor and scientific contracts. The
independent learning and observation images use `dehps.execution.release`.

`legacy_p3_namespace.py` selects two retained source trees and one dependency
environment through a private mount namespace. The paths seen by old code remain
unchanged, so existing artifact references and source probes need no rewriting.
The original source and shared venv are not imported through the host checkout.

| Retained source | Actual entry |
| --- | --- |
| `ac0ef7832c6f13c7500b3f7d67731420b575c0f4` | P3 forward, pre/post mail, armed P4, draw sync, performance watch/enter/exit |
| `cd069c15110b0af0f3a83ff619272c14e4748edc` | Resident research evidence supervisor |

The launcher accepts only the named service commands. Inspection substitutes
`--help`, removes network access, and mounts production runtime/output read-only.
Execution requires the existing `ark` runtime UID and a root-owned bundle whose
parents, directories and files cannot be replaced by runtime users. The trusted
installer must first validate the retained source, dependency and symlink
manifests, then make the complete installed bundle immutable to runtime users.
Root ownership is an installation boundary, not independent review evidence.

Execution mounts source and dependencies read-only, and retains the original
runtime and output locations. Mail can write only runtime; the other legacy
entries can also write data/output. Private `/tmp` and `/var/tmp` are supplied by
bwrap. Numba's execution cache goes to `runtime/control-layer-legacy-numba`, outside
fixed code. No editable package hook is active in the copied environment.

The actual host denies a second user namespace under its AppArmor
`unprivileged_userns` profile. A test combining systemd `ProtectSystem=strict`
with bwrap failed. `NoNewPrivileges=yes` alone passed. Candidate overrides
therefore move the filesystem protection to bwrap: clear systemd `ReadWritePaths`
and `ReadOnlyPaths`, set `ProtectSystem=no` and `PrivateTmp=no`, and retain
`NoNewPrivileges=yes`. This is valid only with the reviewed launcher supplying
the read-only mounts and private temporary directories. Do not install those
property changes separately from the fixed launcher or add arbitrary shell
commands before it. Other namespace-related unit properties must be rechecked
against the captured effective configuration before deployment.

The actual offline verification can be repeated as a separate temporary user
service (choose an unused unit name and a new evidence filename):

```bash
systemd-run --user --unit=dehps-r5-legacy-verification --collect --wait --pipe \
  --property=Type=exec --property=NoNewPrivileges=yes \
  /usr/bin/python3.14 -I -B /path/to/verify_legacy_namespace.py \
  --bundle /path/to/staged-release-package --output /path/to/new-evidence.json
```

This checks all nine fixed commands, their actual imported source root and venv,
UID 1000, `NoNewPrivileges`, kernel `EROFS` denials for both source trees and the
dependency copy, and read-only inspection data mounts. It does not exercise a
production cycle, send mail, or count as canonical deployment acceptance.

The candidate production bundle path is
`/opt/dehps/releases/control-refactor-r5`. Candidate overrides preserve the
effective environment files, timers and CPU settings. The forward service's
`ExecStartPre` and `ExecStopPost` must also select the fixed performance launcher.
Adding only an `ExecStart` override leaves a dependency on the development venv.

Before Operator execution, the final package still needs the independent domain
accounts/database/network, protected credentials and authenticated identity
mapping, exact review/admission references, complete consumer/single-writer
mapping, and reviewed transition/rollback commands. A one-time legacy environment
transition must list any resident process restart explicitly. Starting an
independent experiment must never restart P3.

The old observer remains disabled after its historical status collision; rollback
must not automatically reactivate it. V11 remains masked. A rollback must retain
new immutable commits/artifacts, avoid re-running committed work and avoid an
SMTP retry when delivery outcome is unknown. Legacy source paths and original
unit files must not be overwritten to conceal a failed transition.

## Independent control database installation

`provision_control_database.py` installs the existing schemas as a trusted
administrator, without loading legacy settings. Its closed specification binds
the new database, PostgreSQL cluster identity, control domain, stable principals
and exact SQL bytes. It rejects a changed cluster or SQL file, an existing
deployment role, execution schema or unrelated user schema. The new database
must belong to the connected administrator and retain its initial ACL. All
role/schema/grant changes share one transaction and roll back on failure.

The specification has schema `dehps-control-database-install.v1` and these fields:

| Field | Reviewed value |
| --- | --- |
| `database` | New `dehps_control_learning` or `dehps_control_observer` database |
| `system_identifier` | Actual intended PostgreSQL cluster identifier, as a string |
| `domain` | `learning` or `observer` |
| `principals` | Administrator-verified `engineer`, `reviewer`, `operator` identities; Reviewer differs from both others |
| `sql_sha256` | Exact path-to-SHA mapping for the installer's four `SCHEMA_FILES` |

The schema owner and three role accounts initially have NOLOGIN. Installation
generates no passwords and creates no approvals or executions. Only the operator
gets execution-store entry functions; each role gets only its authority entry
functions. None gets table access, schema creation rights or owner membership.
The administrator must separately activate logins and deliver credentials to
their actual owners. The agent must not hold a Reviewer credential to manufacture
independent review. These identity mappings require real administrative evidence;
a supplied principal string is not proof of that person's approval.

The private administrator JSON contains only `dsn` and must be canonical, owned
by the caller and mode 0600. The DSN explicitly supplies host, port, dbname, user
and password. Remove ambient libpq settings. Never put the password in command
arguments or this repository. The retained environment contains psycopg:

```bash
/opt/dehps/releases/control-refactor-r5/legacy/environment/bin/python -I -B \
  /opt/dehps/releases/control-refactor-r5/provision_control_database.py \
  --admin-credentials /etc/dehps/control-admin.json \
  --spec /etc/dehps/reviewed-control-install.json \
  --source-root /opt/dehps/releases/control-refactor-r5/schema-source
```

## Database access with IP networking disabled

The independent launcher accepts `--database-socket` only with `--network none`.
It mounts the private socket directory read-only at `/run/dehps-postgres`; the
scoped credential DSN uses that host path and port 5432. The directory belongs to
PostgreSQL, not the worker UID; its group equals the worker's primary group, with
no group write or other-user access. The socket shares that owner/group and
denies other users. Typical modes are 2750 for the directory and 0770 for the
socket. The socket source cannot overlap runtime, inputs or credentials. Install
its host parent under a protected path so runtime users cannot replace it.

Each independent PostgreSQL container also uses `--network none`, publishes no
ports and sets `listen_addresses=''`. Local HBA rules require `scram-sha-256`.
Keep the official image's internal `/var/run/postgresql` socket during
initialization and export only the additional private socket directory.
Overriding the default directory alone breaks the initialization client. Pin the
PostgreSQL image and record volume/socket ownership in the final package.

The accepted learning image works unchanged over this socket. The integration
test installs the real schema/grants, performs all five learning stages, inspects
the running container (only `lo`, non-root UID, read-only socket mount), and
replays in a fresh process with no extra records or status writes. It also rejects
a runtime-owned socket and combining this transport with IP networking. Fixture
identities and their activation are not production review evidence.
