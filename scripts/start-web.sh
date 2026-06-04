#!/bin/sh
set -eu

mkdir -p /run/gunicorn

python manage.py migrate --noinput

RELOAD_FLAG=""
WORKERS="${WEB_CONCURRENCY:-1}"
WORKER_CLASS="${GUNICORN_WORKER_CLASS:-gthread}"
THREADS="${GUNICORN_THREADS:-4}"

if [ "${GUNICORN_RELOAD:-False}" = "True" ]; then
  RELOAD_FLAG="--reload"
fi

python manage.py collectstatic --noinput

exec gunicorn project.wsgi:application \
  --workers "${WORKERS}" \
  --worker-class "${WORKER_CLASS}" \
  --threads "${THREADS}" \
  --bind unix:/run/gunicorn/gunicorn.sock \
  --timeout 30 \
  ${RELOAD_FLAG}
