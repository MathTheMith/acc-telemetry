FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

ENV DATABASE_PATH=/data/telemetry.db
VOLUME ["/data"]

EXPOSE 5000

# Single worker: SQLite handles one writer at a time, and this app is single-user
# low-traffic telemetry, not a multi-tenant web app -- threads give concurrency
# for reads without multi-process SQLite lock contention on writes.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "app:app"]
