# Retained P3 release: authentic Git metadata

Status: **OFFLINE_VERIFIED — NOT DEPLOYED**. Engineering under the owner's
continuing R0–R5 authorization. The primary goal is to make the fixed legacy
release satisfy its existing Git identity and history checks. No model,
scientific contract, historical digest, production task or delivery is changed.

The original root-owned R5 package contains source archives but no `.git`.
An actual read-only, network-isolated namespace probe returned exit 128 for both
`git rev-parse HEAD` and `git status --short` in both retained source directories.
The resident supervisor uses these commands; the performance runtime also reads
historical source objects and checks commit ancestry. Passing import/`--help`
checks did not cover those runtime requirements. The original failure is retained
in the activation evidence, and no formal override has been installed.

## Change

`deploy/execution/package_legacy_git.py` exports authentic Git objects and full
reachable history into a new metadata directory. Before export it checks every
tracked file against the original tree object, including bytes, symlink contents
and executable mode. It creates a fresh index, retains the exact detached commit,
requires a clean worktree and runs full `git fsck`. The export has no remote,
hooks, external object alternates, shallow boundary or replacement refs. It never
changes frozen source bytes or copies a mutable developer Git directory.

The fixed launcher now rejects missing metadata or the wrong detached commit
before starting an entry. It clears inherited `GIT_*` selectors and disables
external Git configuration/replacement objects. The offline verifier additionally
checks the exact commits, clean worktrees, full object integrity, parent ancestry,
historical source access and readonly metadata inside the actual namespace.
The original frozen implementations continue executing real Git commands.

## Validation

| Retained tree | Commit | Tracked files verified | Reachable commits |
| --- | --- | --- | --- |
| Original formal scripts | ac0ef7832c6f13c7500b3f7d67731420b575c0f4 | 1,742 | 625 |
| Resident supervisor | cd069c15110b0af0f3a83ff619272c14e4748edc | 1,455 | 494 |

Three real-Git regression tests passed in 0.15 seconds:

- After removing access to the fixture's original repository, the exported copy
  resolves its exact HEAD, reads the original parent source, checks ancestry,
  passes full object integrity verification and detects later dirty content.
- A same-size content edit with the original timestamp restored is rejected
  before metadata creation.
- Executable-mode changes and unexpected untracked source files are rejected;
  an existing output is preserved rather than overwritten.

Command: `apps/worker-python/.venv/bin/python -m pytest -q
apps/worker-python/tests/test_legacy_git_package.py` (using the existing project
interpreter from the unchanged production checkout, with the new test path in
the isolated development worktree). No dependency was installed or modified.

The complete actual namespace check passed all nine import/help commands and the
extended Git/permission probe in 36.897 seconds. Its systemd invocation was
`92f20a122e9b4fa586d6d68bf8fb30e4`. Both source trees and the dependency copy
returned EROFS for write-open; Git metadata and inspection runtime/output mounts
were readonly. The launcher SHA-256 was
`805dbe2617a43240b63c83ac983a9f5944d34911d4e39daf2568c5f3584d7331`.
The metadata-free original bundle was also rejected before process launch.

A separate network-isolated, read-only probe imported the unchanged original
performance-runtime script and called its existing
`verify_runtime_compatibility_closure` and `load_source_contract` functions.
It passed in 4.520 seconds, invocation `859b7a5d345b40399b770e1d3b2d3445`, with
intentionally invalid inherited `GIT_DIR` and `GIT_INDEX_FILE` values:

- Original Operator commit: `6968ed917e4f8bc7e7b9bf415531c93d4012aa9d`.
- Runtime closure: `a37a36d0ad9d35d85b50d56dca4941698db63dbccb75c98a381c4e0c861ef4f7`.
- Source contract: `139ddc97ce1d81ea4e6182359f8391532ed1911090db004bcdf9ebcdea5f9493`.
- Source set: `a3b34318d784d9477fe82f7e66c3c04e5640eaed87e2b4c49cd8b397fc27cd9c`.

These checks used original code and original current configuration as read-only
inputs, without database access, task dispatch, mail delivery or runtime writes.
They do not prove a current P3 execution or report was successful.

## Report impact and remaining release work

Report-impact verdict for this engineering round: **NO_RUNTIME_IMPACT**. The diff
is confined to offline packaging, the undeployed legacy launcher/verifier, tests
and documentation. The original ac0ef78 checkout, retained cd069c1 source, installed
bundle, unit overrides, timers, database, report objects and delivery ledger were
not modified. Both actual namespace probes removed networking and made runtime
and output mounts readonly. Frozen source/compatibility checks above passed.

The already deployed independent learning and observation domains retain their
[R5 execution and replay acceptance](2026-09-11-control-layer-r5-activation.md).
Their scientific conclusion remains “证据不足”. Formal P3's existing forward
failure, manifest incompatibility and current report gaps remain explicitly
pending; this packaging fix does not claim to repair them.

The original reviewed package index and receipt remain immutable. Package the
new metadata, launcher and verifier as a separately manifested legacy release,
then complete the reviewed installation/quiescence/rollback preflight before any
formal transition. Do not silently attach new bytes to the old reviewed package,
substitute an identity string for Git, or disable the frozen verifiers. Full R5
and overall-goal completion remain unproven.
