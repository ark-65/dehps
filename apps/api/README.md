# DEHPS API

Minimal read-only NestJS API for the DEHPS research dashboard.

```bash
npm install
npm test
npm run build
npm run start:dev
```

Endpoints:

- `GET /health`
- `GET /dashboard`
- `GET /experiments`
- `GET /experiments/:experimentKey`
- `GET /feature-distributions`
- `GET /pipeline-runs`
- `GET /sync-runs`
- `GET /execution-status`
- `GET /execution-status/:controlPlane`

The API reads PostgreSQL connection settings from `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD`.

The execution-status routes are a separate readonly file consumer and do not use
database credentials. Set `DEHPS_EXECUTION_STATUS_SOURCES` to a JSON array of
explicit bindings. Each object must contain exactly:

| Field | Required value |
| --- | --- |
| `controlPlane` | Exact configured control domain, e.g. `learning` |
| `root` | Absolute canonical runtime root; API deployment mounts it readonly |
| `planDigest` | Initial canonical plan's 64-character SHA-256 |
| `releaseSha256` | Accepted implementation release's 64-character SHA-256 |
| `executionId` | Actual authenticated execution reference, a positive integer |
| `maxAgeSeconds` | Explicit freshness bound, 1–86400 seconds |

The only selected file is `<root>/<controlPlane>/status/execution.json`. Use the
actual admitted plan/execution and verified release references; configuration
does not grant authority or create those records. Choose a freshness bound longer
than the coordinator heartbeat interval (lease duration / 3; normally 100 seconds).
Invalid/duplicate bindings reject startup. An unset variable configures no
domains; unconfigured domain requests return 404, with no Formal P3 fallback.

The reader requires `execution-status.v2`, matching domain/plan/execution/release,
bounded timestamps and valid task states. Missing, unreadable, corrupt, stale,
future-dated or mismatched files return `UNKNOWN` with an explicit reason and no
cached success. Symlinks and oversized files are rejected. Every response is
labeled `OPERATIONAL_PROJECTION_ONLY` and `durableCompletionVerified: false`;
it is not a scientific result, live-process guarantee, canonical replay proof or
report-delivery acceptance. Failed projection writes can only be observed through
the launch result and the configured freshness bound; API reads do not repair them.
Existing legacy status routes remain separate and cannot certify new domains.
