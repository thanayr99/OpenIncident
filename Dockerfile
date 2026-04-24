FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

COPY frontend/package.json frontend/package.json
COPY frontend/vite.config.js frontend/vite.config.js
COPY frontend/index.html frontend/index.html
COPY frontend/src frontend/src

RUN npm install
RUN npm run build


FROM python:3.11-slim

WORKDIR /app

COPY . /app
COPY --from=frontend-builder /frontend/dist /app/frontend/dist

RUN pip install --no-cache-dir fastapi uvicorn[standard] pydantic openai requests pyyaml playwright \
    && python -m playwright install --with-deps chromium

ENV PORT=7860

EXPOSE 7860

CMD ["python", "-m", "server.app"]
