# Round 6 Report

## Done

- Added a read-only experiment detail API endpoint: `GET /experiments/:experimentKey`.
- Extended experiment summaries with recorded hypothesis text.
- Joined experiment records with the latest stored Markdown report from `dehps_experiment_reports`.
- Fixed API build output so `npm run start` runs the compiled `dist/main.js`.
- Added dashboard detail selection for experiment records.
- Added an in-dashboard Markdown report viewer with hypothesis, config snapshot, metrics, and report timestamp.
- Kept the dashboard single-screen and read-only.
- Added focused API and Web tests for experiment detail/report availability.

## Tests

Worker:

```text
25 passed in 7.50s
```

API:

```text
3 passed
npm run build passed
```

Web:

```text
5 passed
npm run build passed
```

## Commands Run

```bash
/home/ark/workspace/dehps/apps/worker-python/.venv/bin/python -m pytest
cd apps/api && npm test
cd apps/api && rm -rf dist && npm run build
cd apps/api && npm run start
curl -s http://localhost:3000/health
curl -s 'http://localhost:3000/dashboard?limit=1'
curl -s http://localhost:3000/experiments/baseline_v1-daily-20260615-070922
cd apps/web && npm test
cd apps/web && npm run build
```

## API Verification

Health endpoint:

```json
{"status":"ok","service":"dehps-api","mode":"read-only"}
```

Experiment detail endpoint returned:

```text
experimentKey: baseline_v1-daily-20260615-070922
hasReport: true
reportLength: 445
hypothesis: baseline structural naturalness filter
```

## Acceptance Evidence

API detail contract:

```text
apps/api/src/research.types.ts
apps/api/src/research.repository.ts
apps/api/src/research.service.ts
apps/api/src/research.controller.ts
apps/api/test/research.service.test.ts
```

Dashboard detail and report viewer:

```text
apps/web/src/app/dashboard.model.ts
apps/web/src/app/dashboard.service.ts
apps/web/src/app/app.component.ts
apps/web/src/app/app.component.html
apps/web/src/app/app.component.css
apps/web/test/dashboard.model.test.ts
```

Build metadata:

```text
apps/api/tsconfig.json
```

## Problems

- The report viewer intentionally renders stored Markdown as readable preformatted text instead of converting it to HTML. This avoids a new Markdown dependency and keeps the first detail loop small.
- The dashboard still has no client-side route for deep-linking directly to an experiment key.
- Experiment details return the latest report by `created_at`; if multiple reports are later accepted for one experiment, report versioning should become explicit.

## Next Round

Round 7 should add richer comparison views:

- Feature and combination distribution charts.
- Side-by-side experiment comparison.
- Optional deep links for experiment detail state.
- Clear distinction between accepted experiment reports and verification-only generated outputs.

## Risk Note

DEHPS remains a discrete combination-space scoring and backtest platform. The detail viewer exposes historical experiment evidence and stored reports; it does not provide prediction or betting advice.
