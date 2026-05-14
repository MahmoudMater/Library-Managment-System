#!/usr/bin/env sh
set -eu
cd /app
alembic upgrade head
exec gunicorn app.main:app \
  -w "${GUNICORN_WORKERS:-2}" \
  -k uvicorn.workers.UvicornWorker \
  -b 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
