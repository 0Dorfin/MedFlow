#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if [ $# -lt 1 ]; then
  echo "uso: $0 <ruta_backup_dir>" >&2
  echo "ej:  $0 ./backups/20260519_142030" >&2
  exit 1
fi

SRC="$(cd "$1" && pwd)"
PROJECT_PREFIX="proyecto_triage_6"
VOLUMES=(postgres_data minio_data n8n_data)

if [ ! -d "$SRC" ]; then
  echo "ERROR: $SRC no existe" >&2
  exit 1
fi

echo "==> restore desde: $SRC"

if [ -f "$SRC/.env" ]; then
  if [ -f .env ]; then
    BAK=".env.bak.$(date +%s)"
    echo "==> .env existente -> $BAK"
    mv .env "$BAK"
  fi
  cp "$SRC/.env" .env
  echo "==> .env restaurado"
else
  echo "WARN: $SRC/.env no encontrado, mantén el .env actual" >&2
fi

if [ -f "$SRC/airflow_secrets.tar.gz" ]; then
  echo "==> airflow/secrets"
  tar xzf "$SRC/airflow_secrets.tar.gz"
fi

echo "==> parando containers"
docker compose down >/dev/null

echo "==> recreando volumes vacios"
for vol in "${VOLUMES[@]}"; do
  full="${PROJECT_PREFIX}_${vol}"
  docker volume rm "$full" >/dev/null 2>&1 || true
  docker volume create "$full" >/dev/null
done

echo "==> restaurando volumes"
for vol in "${VOLUMES[@]}"; do
  arch="$SRC/${vol}.tar.gz"
  full="${PROJECT_PREFIX}_${vol}"
  if [ ! -f "$arch" ]; then
    echo "  - $arch no existe, skip"
    continue
  fi
  echo "  - ${vol}.tar.gz -> $full"
  docker run --rm \
    -v "${full}:/dest" \
    -v "${SRC}:/src:ro" \
    alpine sh -c "cd /dest && tar xzf /src/${vol}.tar.gz"
done

echo "==> levantando stack"
docker compose up -d >/dev/null

echo
echo "==> done. ps:"
docker compose ps --format "table {{.Name}}\t{{.Status}}" | head -25
