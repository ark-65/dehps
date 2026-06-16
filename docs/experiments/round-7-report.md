# Round 7 Report

## Done

- Added read-only structural feature distribution data to the API.
- Added `GET /feature-distributions`.
- Included feature distributions in the dashboard payload.
- Added dashboard feature charts for:
  - sum value
  - span value
  - odd count
  - consecutive pair count
- Added a side-by-side experiment comparison panel for keep rate, coverage rate, lift, and history coverage.
- Added URL hash state for experiment detail and comparison selection.
- Fixed hash-loaded experiment detail so deep links automatically load the selected report.
- Updated API and Web READMEs for the new endpoint and proxy.
- Kept the round read-only and avoided strategy or algorithm changes.

## Tests

Worker:

```text
25 passed in 7.53s
```

API:

```text
4 passed
npm run build passed
```

Web:

```text
6 passed
npm run build passed
```

## Commands Run

```bash
/home/ark/workspace/dehps/apps/worker-python/.venv/bin/python -m pytest
cd apps/api && npm test
cd apps/api && npm run build
cd apps/api && npm run start
curl -s http://localhost:3000/feature-distributions
curl -s 'http://localhost:3000/dashboard?limit=2'
cd apps/web && npm test
cd apps/web && npm run build
cd apps/web && npm run start
curl -s http://localhost:4200/feature-distributions
google-chrome --headless --no-sandbox --disable-gpu --window-size=1440,1800 --virtual-time-budget=5000 --screenshot=/tmp/dehps-round7-dashboard-desktop-fixed.png 'http://localhost:4200/#experiment=baseline_v1-daily-20260615-070922'
google-chrome --headless --no-sandbox --disable-gpu --window-size=390,2000 --virtual-time-budget=5000 --screenshot=/tmp/dehps-round7-dashboard-mobile-fixed.png 'http://localhost:4200/#experiment=baseline_v1-daily-20260615-070922'
```

## API Verification

Feature distribution endpoint returned:

```text
features: 4
keys: sum_value, span_value, odd_count, consecutive_pair_count
totalCounts: 10000, 10000, 10000, 10000
```

Dashboard endpoint returned:

```text
experiments: 1
featureDistributions: 4
```

## UI Verification

- Desktop screenshot confirmed experiment detail, comparison, combination distribution, feature distributions, pipeline runs, and sync runs render together.
- Mobile screenshot confirmed the experiment table scrolls horizontally and detail/report sections stack vertically.
- DOM verification confirmed `Report available`, `Markdown Report`, `Experiment Comparison`, and `Feature Distributions` render through a hash deep link.

## Acceptance Evidence

API feature distribution read model:

```text
apps/api/src/research.types.ts
apps/api/src/research.repository.ts
apps/api/src/research.service.ts
apps/api/src/research.controller.ts
apps/api/test/research.service.test.ts
```

Dashboard comparison and charts:

```text
apps/web/src/app/dashboard.model.ts
apps/web/src/app/dashboard.service.ts
apps/web/src/app/app.component.ts
apps/web/src/app/app.component.html
apps/web/src/app/app.component.css
apps/web/test/dashboard.model.test.ts
apps/web/proxy.conf.json
```

## Problems

- The current main database contains 10,000 generated red-ball combinations in `ssq_red_combinations`; feature charts therefore describe the current generated table, not necessarily the full `C(33,6)` space.
- The experiment comparison panel is ready for multiple experiments, but the current main database has only one experiment record, so deltas display as `N/A` until more accepted experiments exist.
- Feature distribution buckets are fixed read-only bins. Choosing better bins belongs in a later analysis or algorithm-optimization round.

## Roadmap Completion Note

The engineering roadmap is now complete through the currently defined product/review scope:

- computation and backtest loop
- real history sync
- scheduled pipeline and recovery records
- agent experiment contracts
- read-only API and dashboard
- experiment report viewer
- comparison and distribution review surface

The next phase should be explicitly opened as deep optimization and algorithm optimization.

## Risk Note

DEHPS remains a discrete combination-space scoring and backtest platform. These views summarize historical records and generated combination features; they do not provide prediction or betting advice.
