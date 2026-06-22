# DEHPS Local Runbook

This runbook is for local acceptance and smoke testing. DEHPS is a hypothesis-verification project, not a lottery prediction or betting system.

## Start Infrastructure

```bash
docker compose up -d
```

PostgreSQL listens on `localhost:54329`; Redis listens on `localhost:63799`. Runtime database files are stored under `runtime/` and should not be committed.

## Python Worker

Create and install the worker environment:

```bash
cd apps/worker-python
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Run tests:

```bash
python -m pytest -q
```

Generate the legal 双色球 red-ball universe:

```bash
python scripts/generate_ssq_red_combinations.py --reset
```

Run a historical sync dry-run:

```bash
python scripts/sync_latest_ssq.py --source zhcw --history --dry-run
```

Run a daily pipeline smoke:

```bash
python scripts/daily_pipeline.py --strategy-key baseline_v1 --source zhcw --force --skip-weight-kdj-signals
```

This smoke writes local run records and Markdown output. Review the result, but do not commit generated `runtime/` or `data/output/` content unless the task explicitly asks for a specific evidence artifact.

## NestJS API

Install dependencies:

```bash
cd apps/api
npm install
```

Run tests:

```bash
npm test
```

Start the API:

```bash
npm run start:dev
```

## Angular Web

Install dependencies:

```bash
cd apps/web
npm install
```

Run tests:

```bash
npm test
```

Build or start the dashboard:

```bash
npm run build
npm start
```

The web app uses `proxy.conf.json` for local API proxying.

## Common Issues

### `psycopg` Missing

Run `pip install -e .` inside `apps/worker-python` with the virtual environment activated. The worker dependency is declared as `psycopg[binary]`.

### PostgreSQL Not Running

Start Docker services with `docker compose up -d`, then check the container:

```bash
docker compose ps
```

The expected database port is `54329`.

### Port Conflict

If PostgreSQL `54329`, Redis `63799`, API, or Web ports are already in use, stop the conflicting process or change the local port mapping before starting services.

### Runtime Or Data Output Appears In Git

Do not commit `runtime/`, `data/output/`, `node_modules/`, `.venv/`, `dist/`, `build/`, caches, or logs. These are local runtime or generated output directories unless a task explicitly asks for a small evidence artifact.
