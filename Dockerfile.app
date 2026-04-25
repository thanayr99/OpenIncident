FROM node:20-bookworm-slim AS frontend-build

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci
COPY frontend ./
RUN npm run build


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /app

# Git is needed for repository pull/check workflows. Playwright uses Chromium for rendered browser checks.
RUN apt-get update \
  && apt-get install -y --no-install-recommends git curl ca-certificates \
  && rm -rf /var/lib/apt/lists/*

COPY . /app
COPY --from=frontend-build /frontend/dist /app/frontend/dist

RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -e . \
  && python -m playwright install --with-deps chromium

EXPOSE 8000

CMD ["sh", "-c", "uvicorn server.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
