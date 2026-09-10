# Supply the inspected content digest of the reviewed Node image. No tag default.
ARG NODE_IMAGE
FROM ${NODE_IMAGE} AS build
WORKDIR /build
COPY apps/api/package.json apps/api/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/api/tsconfig.json ./
COPY apps/api/src ./src
RUN npm run build && npm prune --omit=dev --no-audit --no-fund

FROM ${NODE_IMAGE}
WORKDIR /app
COPY --from=build /build/node_modules ./node_modules
COPY --from=build /build/dist/execution-status.js /build/dist/execution-status-main.js /build/dist/config.js ./
ENV NODE_ENV=production API_PORT=3000
USER 65532:65532
ENTRYPOINT ["node", "/app/execution-status-main.js"]
