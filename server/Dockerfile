FROM python:3.11-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir fastapi uvicorn[standard] pydantic openai requests pyyaml playwright \
    && python -m playwright install --with-deps chromium

ENV PORT=7860

EXPOSE 7860

CMD ["python", "-m", "server.app"]
