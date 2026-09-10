# R3 fixed release and rollback boundary

Role: Engineering, continuing owner-authorized R0–R5 scope. Implementation and
acceptance in progress; no production deployment.

Goal: bind actual source, dependencies, entry and non-secret configuration to a
fixed release independent of the development checkout. Ready: committed source
and a content-pinned Python base image. Runner: bounded release builder and
launcher. Upstream: Git archive, base image and explicit configuration. Downstream:
release descriptor, retained image, installed dependency inventory and run facts.
Status: release verification outcome, separate from task or scientific completion.
Evidence rule: actual isolated image build/run, development mutation and rollback
exercise. Decision consumer: release verifier. Next consumer: R4 domain entry and
R5 reviewed deployment package.

The existing Docker daemon is used to freeze the Python userspace and dependency
closure while retaining systemd as the prospective service manager. This adds no
queue or orchestration platform. A local content-addressed image ID binds image
configuration and layers; tags are discovery aids only. See the primary
[Docker image identity documentation](https://docs.docker.com/reference/cli/docker/image/pull/).
The launcher must use the exact verified image ID, a read-only root filesystem,
an explicit non-root UID, no capabilities, and explicit data/credential mounts.
See [Docker runtime controls](https://docs.docker.com/engine/containers/run/).

Before implementation: original production checkout remains clean ac0ef78; no
production source, venv, unit, database, artifact, source contract or mail ledger
is targeted. Dated 2026104 report gap and 2026105 sealing/delivery acceptance remain
unclaimed. The R2 plan/commit/replay path is not yet a deployed release. Formal P3
continues on retained legacy execution; its original source identities are not
rewritten. Existing archived V11 files may be retained as history, never scheduled.

Scientific contract identity, implementation release identity and artifact schema
remain separate. The release descriptor is not an approval: R1 authenticates
actual principals and R5 must bind the concrete release to independent review.
Retaining an image permits rollback of code/configuration; rollback never deletes
or rewrites persistent execution facts. Missing historical image/environment is
an explicit inability to replay, never permission to substitute current code.

## Component validation

`tests/test_execution_release_schema.py` plus
`integration_tests/test_execution_release.py`: **10 passed in 29.85 s** against
actual Docker images with Python 3.14.4. The nine schema cases reject mutable or
incomplete identities and verify each recorded release component affects identity.
The integration case builds two committed package versions, installs them into
separate frozen userspaces and launches their recorded entrypoints. It modifies
the development source and switches its branch, verifies unchanged old-release
output, runs the new version, then rolls back to the old version. Readonly code,
config, inputs and credentials reject writes; replay also mounts runtime readonly.
The history remains `one, one, two, one` after replay. Actual container Image and
terminal ExitCode are inspected, not inferred from the Docker client exit code.

The same exercise saves the old image, removes it from Docker, confirms it is
unavailable, rejects a wrong archive digest, loads verified retained bytes and
replays with the original release. A forced timeout removes only the exact
container created by that call; no detached computation remains.

- First fixture release: `416ff8dac23fe8bbdacad6744adb42f8aa6b510c53d4843e719358fb8ded7689`.
- Second fixture release: `0a3b12c44377e1e74cd156331a055968bf2b5b6158a10d4ad3099378385ee086`.
- Archived image bytes: `4bb562feac62c0a6bdf0c0ba320084d25144134afbb5402d9af02e5e43edab32`.

These are engineering fixtures, not scientific/production replay acceptance.
Fixture images are removed by their test cleanup. The full worker build and
smoke verification also passed after the Numba cache correction below.

Full worker verification used committed source
`55906b05932cdd22a4f0432b3d09e94e967ba299`, release
`122a40f2a9c58d0e579e39ee7428593d5058dc81fa8072c2b7d5baec77c032ef`, image
`sha256:7a2586be833f1d2ed688a7fa45fc80268ee6624c620c35bc9dbb56564f96d746`.
Container `6e5fbf24725a7c5a9749b23967e2f9e3070ff72156151fee3beb0e399a66fd02`
exited 0. All **531** archived Python files matched the installed package byte
for byte, coordinator and learning_v1 imported successfully, source writes were
denied and no production credentials were present. Python is 3.14.4; the resolved
NumPy is 2.5.3, distinct from CI's 2.4.6 pin. This is packaging/environment proof,
not frozen-science parity. R4 must explicitly select and verify the scientific
environment. The complete inventory and descriptor remain outside Git in the
local engineering artifact directory `/tmp/dehps-r3-full-worker`.
The same fixed descriptor also passed the `release run --action replay` CLI with
runtime mounted readonly, container
`b1793a3cea5dece391ae3e5ba6ec4ff42c9a3d158df87dcb3196107323a355ab`, exit 0.
This smoke entry only verifies packaging and imports; it does not replace the R2
canonical task replay or the historical scientific verifier required in R4.

Failures retained in the local run log: pytest initially found duplicate test
module names (renamed the unit module); BuildKit interpreted bare image IDs in
FROM as repository tags (builder now resolves and checks the attached immutable
registry digest); the initial fixture script needed a raw string for its newline.
All three were repaired without relaxing the assertions.

The builder requires a clean checkout and an exact Git commit, and builds only
`git archive` bytes; untracked data, host dependencies and ambient `.env` are not
copied. Dependency version ranges resolve at build time, and actual versions are
recorded inside the resulting image. A later rebuild is a new release requiring
its own accepted identity; reinstalling version ranges is not historical replay.
The descriptor and retained archive are created without overwriting earlier files.
The deployment package must retain both descriptor identity and archive digest.

The first full worker smoke run exposed Numba's import-time cache initialization
against readonly installed code. This is a real runtime packaging defect, not a
test-only failure. The image now fixes NUMBA_CACHE_DIR to the isolated `/tmp`
tmpfs. No scientific kernel, historical source binding or verifier is changed.
The import trace also confirms that current learning_v1 still imports the legacy
supervisor through the notification prize helper; R4 must remove that coupling
while preserving the helper's exact numerical behavior.

The launcher accepts no replacement command, writable code mount or configuration
override. It has a dedicated runtime target and readonly inputs/credential target;
it rejects overlapping or noncanonical roots, root UID, public credential files
and ambient/host networking. R5 still must provision the dedicated filesystem
owner, restricted database principal, isolated Docker network and independently
reviewed deployment inputs. Docker administration stays outside worker authority.
Image labels are builder provenance, not authentication of a Reviewer.

Command surface: `python -m dehps.execution.release --help`. Build uses explicit
`--repository`, `--commit`, `--base-image-id`, `--entrypoint-json`, `--config-json`
and `--output`. Verify/archive/restore/run require both `--descriptor` and its
externally accepted `--release-sha256`; restore also requires the retained archive
digest. Run requires explicit domain, roots, credentials, network and action.

Remaining integration: R4 must supply the actual capability entry and bind this
verified release identity into R1 admission and R2 records, alongside the unchanged
scientific contract and artifact schema. R3 status/API consumption, historical
science parity and real legacy release preservation still need their own evidence.
No claim is made that a fixture build completes those paths. Overall remains
**NO — INTEGRATION_PENDING**.

Report impact: **NO_RUNTIME_IMPACT for this undeployed component**, based on the
isolated development/build/test resources and additive diff. No existing runner,
scientific implementation, production path, timer or delivery consumer changes.
No new production report completeness or delivery is claimed.
