# Round 17 - DEHPS Project Consolidation And Local Acceptance

## Goal

Consolidate project-level documentation, local run instructions, agent rules, and deployment examples without adding new algorithms, models, or strategies.

## Changed Files

- `AGENTS.md`
- `README.md`
- `docs/local-runbook.md`
- `infra/systemd/dehps-daily-pipeline.service`
- `docs/experiments/round-17-project-consolidation-report.md`

## Commands Run

Initial inspection:

```bash
pwd
git status --short
git rev-parse --show-toplevel
```

Files reviewed:

```bash
sed -n '1,260p' README.md
sed -n '1,320p' docs/roadmap.md
sed -n '1,260p' apps/worker-python/README.md
sed -n '1,220p' docker-compose.yaml
sed -n '1,520p' infra/postgres/init/001_init.sql
sed -n '1,220p' apps/worker-python/pyproject.toml
sed -n '1,220p' apps/api/package.json
sed -n '1,220p' apps/web/package.json
sed -n '1,260p' scripts/hourly_self_iterate.sh
sed -n '1,220p' infra/systemd/*.service infra/systemd/*.timer
```

Validation:

```bash
python -m pytest -q
.venv/bin/python -m pytest -q
cd apps/api && npm test
cd apps/web && npm test
cd apps/web && npm run build
git status --short --ignored
```

## Test Results

- `python -m pytest -q` from `apps/worker-python`: failed because this shell has no `python` command.
- `.venv/bin/python -m pytest -q` from `apps/worker-python`: passed, `183 passed in 20.52s`.
- `npm test` from `apps/api`: passed, `25` tests.
- `npm test` from `apps/web`: passed, `17` tests.
- `npm run build` from `apps/web`: passed; generated ignored output at `apps/web/dist/dehps-web`.

## Unresolved Issues

- The active execution path in this environment is `/home/ark/workspace/dehps`, while the user mentioned `/Users/mac/Code/workspace/Mine/dehps`. The repository content was validated in the mounted workspace path available to Codex.
- `git status --short --ignored` reported permission warnings for Docker-owned `runtime/postgres/` and `runtime/redis/`. These runtime directories are ignored and were not staged.
- This environment does not provide a `python` executable name; use `python3` or `apps/worker-python/.venv/bin/python`.

## Next Round Suggestions

- Keep Round 18 focused on one concrete acceptance gap discovered by tests, if any.
- Do not add new strategy or model work until Round 17 acceptance blockers are resolved.

## Post-Round Positioning Note

After the Round 17 commit, the user clarified that DEHPS may provide betting-oriented recommendations and may present experimental results as predictive ability direction. The current maturity boundary is that the system has not reached its training target yet, so prediction and betting language should carry evidence level, uncertainty, training status, and failure cases.
