# Round 5 Report

## Done

- Replaced API placeholder with a minimal read-only NestJS service.
- Added API endpoints for health, dashboard payload, experiment records, pipeline runs, and sync runs.
- Added PostgreSQL-backed repository mapping DEHPS tables into dashboard DTOs.
- Replaced Web placeholder with a minimal Angular dashboard application.
- Dashboard first screen shows experiment metrics, retained/rejected combination distribution, pipeline status, and sync status.
- Added frontend helpers for percentage formatting and latest pipeline state.
- Added API and Web package manifests, lockfiles, build configs, and READMEs.
- Added `.gitignore` entries for generated Node/Angular build output.
- Verified the API against the existing local PostgreSQL database.

## Tests

Worker:

```text
25 passed in 7.67s
```

API:

```text
2 passed
npm run build passed
```

Web:

```text
4 passed
npm run build passed
```

## Commands Run

```bash
npm view @angular/core version
npm view @nestjs/core version
npm install
/home/ark/workspace/dehps/apps/worker-python/.venv/bin/python -m pytest
cd apps/api && npm test
cd apps/api && npm run build
cd apps/api && npm run start:dev
curl -s http://localhost:3000/health
curl -s 'http://localhost:3000/dashboard?limit=3'
cd apps/web && npm test
cd apps/web && npm run build
cd apps/web && npm audit --omit=dev
cd apps/api && npm audit --omit=dev
```

## API Verification

Health endpoint:

```json
{"status":"ok","service":"dehps-api","mode":"read-only"}
```

Dashboard endpoint returned:

```text
experiments: 1
pipelineRuns: 1
syncRuns: 2
latest experiment: baseline_v1-daily-20260615-070922
latest pipeline status: success
latest sync source: zhcw
```

## Acceptance Evidence

NestJS API:

```text
apps/api/src/main.ts
apps/api/src/app.module.ts
apps/api/src/research.controller.ts
apps/api/src/research.service.ts
apps/api/src/research.repository.ts
apps/api/test/research.service.test.ts
```

Angular dashboard:

```text
apps/web/src/app/app.component.ts
apps/web/src/app/app.component.html
apps/web/src/app/app.component.css
apps/web/src/app/dashboard.service.ts
apps/web/src/app/dashboard.model.ts
apps/web/test/dashboard.model.test.ts
```

Package and build metadata:

```text
apps/api/package.json
apps/api/package-lock.json
apps/web/package.json
apps/web/package-lock.json
apps/web/angular.json
```

## Problems

- The dashboard currently renders a retained/rejected combination distribution for the latest experiment, not deeper feature histograms.
- `npm audit --omit=dev` reports 0 production vulnerabilities for both API and Web.
- Full Web audit reports 3 high-severity dev-chain findings through Angular build's `esbuild` and `vite` dependencies. npm reports no available fix at this time.
- The API is read-only and intentionally does not expose mutation endpoints.

## Next Round

The original five-round plan is complete. Future work should be added as new, separately accepted rounds, for example:

- Round 6: experiment detail pages and Markdown report viewer.
- Round 7: combination distribution charts.
- Round 8: persisted agent suggestion review packets.

## Risk Note

DEHPS remains a discrete combination-space scoring and backtest platform. The dashboard displays historical research records and operational status; it does not provide prediction or betting advice.
