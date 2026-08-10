#!/bin/sh
set -eu

mkdir -p "${PROMETHEUS_MULTIPROC_DIR:-/tmp/drive_prometheus}"
rm -rf "${PROMETHEUS_MULTIPROC_DIR:-/tmp/drive_prometheus}"/*
echo "Aplicando migraciones..."
flask db upgrade
echo "Iniciando Drive Institucional..."
exec gunicorn --config /app/gunicorn.conf.py "wsgi:app"
