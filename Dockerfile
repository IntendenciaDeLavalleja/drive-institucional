FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=wsgi:app \
    FLASK_CONFIG=production \
    PORT=5000 \
    PROMETHEUS_MULTIPROC_DIR=/tmp/drive_prometheus

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libmariadb-dev pkg-config libmagic1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/entrypoint.sh \
    && useradd --system --uid 10001 --create-home drive \
    && chown -R drive:drive /app

USER drive
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=8s --start-period=30s --retries=3 \
  CMD curl --fail "http://127.0.0.1:${PORT:-5000}/health" || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
