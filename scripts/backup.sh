#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

TS="$(date +%Y%m%d_%H%M%S)"
DEST="${1:-$PROJECT_DIR/backups/$TS}"
PROJECT_PREFIX="proyecto_triage_6"
VOLUMES=(postgres_data minio_data n8n_data)

mkdir -p "$DEST"

echo "==> backup destino: $DEST"

if [ ! -f .env ]; then
  echo "ERROR: .env no encontrado en $PROJECT_DIR" >&2
  exit 1
fi

echo "==> parando containers"
docker compose stop >/dev/null

echo "==> backup volumes"
for vol in "${VOLUMES[@]}"; do
  full="${PROJECT_PREFIX}_${vol}"
  if ! docker volume inspect "$full" >/dev/null 2>&1; then
    echo "  - $full no existe, skip"
    continue
  fi
  echo "  - $full -> ${vol}.tar.gz"
  docker run --rm \
    -v "${full}:/src:ro" \
    -v "${DEST}:/dest" \
    alpine sh -c "cd /src && tar czf /dest/${vol}.tar.gz ."
done

echo "==> copiando .env"
cp .env "$DEST/.env"

echo "==> backup airflow/secrets"
if [ -d airflow/secrets ]; then
  tar czf "$DEST/airflow_secrets.tar.gz" airflow/secrets
fi

echo "==> levantando containers de nuevo"
docker compose up -d >/dev/null

cat > "$DEST/MANIFEST.txt" <<EOF
TriageIA backup
timestamp: $TS
host: $(hostname)
project_prefix: $PROJECT_PREFIX
volumes: ${VOLUMES[*]}
EOF

echo
echo "==> done. archivos en $DEST:"
ls -lh "$DEST"
