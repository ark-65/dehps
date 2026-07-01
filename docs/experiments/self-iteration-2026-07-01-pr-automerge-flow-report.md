# Self-Iteration PR Auto-Merge Flow

## Goal

Make scheduled DEHPS self-iteration changes count as co-authored merged pull requests by replacing direct branch pushes with a branch, PR, and auto-merge publishing flow.

## Non-Goals

- Do not change the daily pipeline auto-git helper; it still handles data/report sync pushes.
- Do not change the self-iteration Git author, committer, or co-author identity.
- Do not add a GitHub Actions workflow.

## Change

`scripts/hourly_self_iterate.sh` now instructs each scheduled Codex run to choose a single target, return to a clean `main`, pull with `--ff-only`, and create a topic branch before editing tracked files. Branch names must use `<type>/self-iterate-YYYYMMDD-HHMM-<slug>`, where `type` is one of `fix`, `feat`, `chore`, `docs`, `test`, or `refactor`.

Self-iteration commits and PR titles now use the same Conventional Commit prefix instead of the old `self-iterate:` prefix. The prompt explicitly forbids direct pushes or merges to `main`.

`apps/worker-python/scripts/self_iteration_publish_pr.py` is the new publishing helper. It validates:

- current branch is not `main` or `master`;
- branch and PR title use the allowed type prefixes;
- worktree is clean;
- `gh auth status` succeeds;
- the latest commit message contains the required `Co-authored-by` trailer.

When validation passes, the helper pushes the branch, creates a ready PR, and runs `gh pr merge --auto --squash --delete-branch --match-head-commit <sha>`. The merge body includes the co-author trailer to reduce the risk that squash merge attribution loses the Pair Extraordinaire signal.

## Recovery

If publishing fails, the helper returns a structured failure status and does not fall back to direct push. The topic branch remains available for manual inspection, push retry, PR creation, or merge recovery.

## Validation

```bash
bash -n scripts/hourly_self_iterate.sh
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_self_iteration_publish_pr.py
apps/worker-python/.venv/bin/python -m pytest -q apps/worker-python/tests/test_git_commit_and_push.py apps/worker-python/tests/test_self_iteration_publish_pr.py
git diff --check
```

Result: shell syntax check passed, focused publishing tests passed with `7 passed`, combined git helper tests passed with `16 passed`, and `git diff --check` reported no whitespace errors.

## Evidence Context

Pair Extraordinaire depends on co-authored work entering the default branch through a merged pull request. The existing commit-msg hook already appends:

```text
Co-authored-by: give me a 98K <240642031+inhuman-0@users.noreply.github.com>
```
