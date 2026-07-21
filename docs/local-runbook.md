# DEHPS Local Runbook

This runbook is for local acceptance and smoke testing. DEHPS is being trained toward prediction-oriented decision support, while local acceptance focuses on whether the hypothesis, training, backtest, API, and dashboard surfaces run correctly.

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

## QQ Mail Smoke

QQ Mail must have SMTP enabled and must use its generated authorization code, not the QQ login password. Put the following values in the repository-root `.env`, which is ignored by Git:

```dotenv
DEHPS_QQ_MAIL_ADDRESS=your-account@qq.com
DEHPS_QQ_MAIL_AUTHORIZATION_CODE=your-qq-smtp-authorization-code
```

The recipient defaults to the same QQ address. To send elsewhere, add an optional `DEHPS_QQ_MAIL_RECIPIENT` value or pass `--to` for one command.

Send one manual smoke message:

```bash
cd apps/worker-python
.venv/bin/dehps mail send \
  --subject "DEHPS mail smoke" \
  --text "QQ SMTP delivery is working."
```

The service uses implicit TLS at `smtp.qq.com:465`. Credentials are not accepted as CLI arguments and successful output contains only the sender, recipient, and message ID. Do not commit `.env`, paste the authorization code into an Agent Request, or put it in a shell command.

### Scheduled Mainline Top-100 Mail

Scheduled delivery requires an explicit recipient in the same ignored `.env`:

```dotenv
DEHPS_QQ_MAIL_RECIPIENT=recipient@example.com
```

Validate the current durable `static_100` prediction without sending:

```bash
cd apps/worker-python
.venv/bin/dehps mail mainline-prediction --preview
```

The checked-in timer runs at 17:00 Asia/Shanghai on Tuesday, Thursday, and Sunday, four hours and fifteen minutes before the official 21:15 SSQ draw. Install it only under an approved Operator Request:

```bash
sudo install -m 0644 infra/systemd/dehps-mainline-prediction-mail.service /etc/systemd/system/
sudo install -m 0644 infra/systemd/dehps-mainline-prediction-mail.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dehps-mainline-prediction-mail.timer
systemctl list-timers dehps-mainline-prediction-mail.timer
```

The delivery ledger is stored at `runtime/notifications/mainline_prediction_mail.json`. A completed delivery is idempotently skipped. An interrupted or ambiguous SMTP attempt becomes `uncertain` and blocks automatic retries until an operator reviews it; this avoids silently sending duplicates.

### Post-draw Three-line Evaluation Mail

After a draw update, `daily_pipeline.py` first synchronizes the official result and completes accepted forward Evaluation for the three frozen lines. It then sends one detailed report for:

- `static_100`;
- `dynamic_kdj`;
- `dynamic_kdj_near`.

The report distinguishes the actual red combination's full-universe model rank from its rank in the frozen TopN export. It separately reports exact-six and red-five Top100/1000/10000 outcomes, cutoff overlap counts, ranking-path audit, prediction/evaluation identity, leakage status, and Runtime/Evaluation Artifact digests. The blue ball is recorded but never scored.

Preview one completed issue without writing artifacts or opening SMTP:

```bash
cd apps/worker-python
.venv/bin/dehps mail post-draw-evaluation --issue 2026082 --preview
```

External delivery requires an approved Operator Request:

```bash
.venv/bin/dehps mail post-draw-evaluation --issue 2026082 --send
```

Compilation fails closed unless exactly one accepted pre-draw evaluation exists for every required line, all three rows bind to the same draw, leakage checks pass, candidate counts equal the frozen TopN, and Ranking Audit supplies a legal full-universe rank. Digest-addressed JSON/text reports are written under `data/output/post-draw-evaluation-reports/`. Delivery state is stored at `runtime/notifications/post_draw_evaluation_report_mail.json`; `uncertain` SMTP state requires manual review and is never retried automatically.

Mail failure is recorded in the pipeline summary but does not block generation of the next pre-draw prediction snapshot. This preserves the separation between notification operations and prediction production.

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
