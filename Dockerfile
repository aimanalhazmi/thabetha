# syntax=docker/dockerfile:1

FROM node:22-alpine AS frontend
WORKDIR /frontend
ARG VITE_SUPABASE_URL=http://127.0.0.1:55321
ARG VITE_SUPABASE_PUBLISHABLE=
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN VITE_SUPABASE_URL="${VITE_SUPABASE_URL}" VITE_SUPABASE_ANON_KEY="${VITE_SUPABASE_PUBLISHABLE}" npm run build

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS runtime
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH" \
    APP_ENV=production \
    FRONTEND_DIST=/app/static
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-dev
COPY backend/app ./app
COPY supabase/migrations /supabase/migrations
COPY --from=frontend /frontend/dist ./static
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
