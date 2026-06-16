# DEHPS Web

Minimal Angular dashboard for DEHPS experiment and pipeline review.

```bash
npm install
npm test
npm run build
npm run start
```

The dashboard expects the API at `/dashboard`, experiment detail records at `/experiments/:experimentKey`, and structural feature charts at `/feature-distributions`. During local development, the Angular dev server proxies `/dashboard`, `/experiments`, `/feature-distributions`, `/pipeline-runs`, and `/sync-runs` to `http://localhost:3000`.
