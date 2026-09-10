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
`integration_tests/test_execution_release.py`: **10 passed in 33.39 s** against
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

- First fixture release: `8126ce5fed6e031f9872301420c55a1cfeefa7ecb321b68c03800e4784d43bb2`.
- Second fixture release: `c86167ed5f432d7c09f6880657388905eef34e591f422baccd31f792bce2376d`.
- Archived image bytes: `94751cd5da751d5a8ea3bbdcafa15d078ee9127d612f6922c40662bf4c950e58`.

These are engineering fixtures, not scientific/production replay acceptance.
Fixture images are removed by their test cleanup. A full worker image build and
smoke verification remains the next check before PR acceptance.

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
