# DEHPS Web

Minimal Angular dashboard for DEHPS experiment and pipeline review.

```bash
npm install
npm test
npm run build
npm run start
```

The dashboard expects the API at `/dashboard`. During local development, the Angular dev server proxies `/dashboard`, `/experiments`, `/pipeline-runs`, and `/sync-runs` to `http://localhost:3000`.
