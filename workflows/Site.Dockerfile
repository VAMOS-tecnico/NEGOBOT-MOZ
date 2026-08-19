FROM node:22-bookworm-slim AS frontend-build

WORKDIR /build
COPY platform-react/package.json platform-react/pnpm-lock.yaml ./platform-react/
RUN corepack enable && cd platform-react && pnpm install --frozen-lockfile
COPY platform-react/src ./platform-react/src
COPY platform-react/index.html platform-react/tsconfig.json platform-react/vite.config.ts ./platform-react/
RUN cd platform-react && pnpm build

FROM python:3.11-slim

WORKDIR /app
RUN pip install --no-cache-dir Flask gunicorn requests

COPY index.html platform.html assistant.html site_server.py tiktokoDTBw5Ntz98ZU3WlMhJdbTzyL0pFmdKH.txt ./
COPY --from=frontend-build /build/platform-react/dist ./platform-react/dist

RUN python -m py_compile site_server.py

EXPOSE 3000
CMD ["gunicorn", "--bind", "0.0.0.0:3000", "--workers", "2", "--timeout", "60", "site_server:app"]
