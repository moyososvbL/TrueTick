# TrueTick: one container with the web app, the API and the sealed browser (Chromium) for website visits.
# Works on Hugging Face Spaces (Docker), Render, Railway or Fly.io. Set META_API_KEY as a secret there.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright \
    DATA_DIR=/tmp/truetick-data

WORKDIR /app
COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir -r requirements.txt \
 && python -m playwright install --with-deps chromium \
 && chmod -R a+rx /opt/playwright

COPY backend ./backend
COPY frontend ./frontend

# Runs as a normal user (required by Hugging Face Spaces, safer everywhere).
RUN useradd -m -u 1000 truetick
USER truetick

# Hosts tell us the port in $PORT; Hugging Face Spaces uses 7860.
EXPOSE 7860
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-7860} --proxy-headers --forwarded-allow-ips='*'"]
