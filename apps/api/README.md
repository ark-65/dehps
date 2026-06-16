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

The API reads PostgreSQL connection settings from `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD`.
