#!/bin/sh
set -eu

WORKFLOWS_DIR="${WORKFLOWS_DIR:-/workflows}"
FLAG_FILE="${FLAG_FILE:-/home/node/.n8n/.workflows_imported}"

if [ -f "${FLAG_FILE}" ] && [ "${FORCE:-0}" != "1" ]; then
  echo "[n8n-bootstrap] ya importado (${FLAG_FILE}). FORCE=1 para reimportar."
  exit 0
fi

echo "[n8n-bootstrap] esperando que n8n libere sqlite..."
sleep 5

echo "[n8n-bootstrap] importando workflows desde ${WORKFLOWS_DIR}..."
for attempt in 1 2 3 4 5; do
  if n8n import:workflow --separate --input="${WORKFLOWS_DIR}"; then
    break
  fi
  echo "[n8n-bootstrap] intento ${attempt} fallo, reintento..."
  sleep 5
done

echo "[n8n-bootstrap] activando workflows..."
for attempt in 1 2 3 4 5; do
  if n8n update:workflow --all --active=true; then
    break
  fi
  echo "[n8n-bootstrap] activacion intento ${attempt} fallo, reintento..."
  sleep 5
done

mkdir -p "$(dirname "${FLAG_FILE}")"
touch "${FLAG_FILE}"
echo "[n8n-bootstrap] hecho."
