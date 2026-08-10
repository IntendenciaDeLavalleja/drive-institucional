#!/bin/sh
set -eu

mkdir -p "${PROMETHEUS_MULTIPROC_DIR:-/tmp/drive_prometheus}"
rm -rf "${PROMETHEUS_MULTIPROC_DIR:-/tmp/drive_prometheus}"/*
echo "Aplicando migraciones..."
flask db upgrade
cleanup_interval="${FILE_CLEANUP_INTERVAL_SECONDS:-86400}"
case "$cleanup_interval" in *[!0-9]*|"") cleanup_interval=86400 ;; esac
if [ "$cleanup_interval" -lt 1 ]; then cleanup_interval=86400; fi
(
    while :; do
        echo "Eliminando archivos vencidos..."
        flask prune-expired-files || echo "ADVERTENCIA: falló la limpieza de archivos vencidos." >&2
        sleep "$cleanup_interval"
    done
) &
echo "Iniciando Drive Institucional..."
exec gunicorn --config /app/gunicorn.conf.py "wsgi:app"
