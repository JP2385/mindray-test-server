#!/usr/bin/env bash
# reconfigure.sh — Actualizar identity.json y/o .env sin reinstalar nada
#
# Uso:
#   bash setup/reconfigure.sh
#
# Útil cuando cambia: monitor_id, api_key, INGEST_URL (sin necesidad de
# volver a ejecutar el setup completo).

set -euo pipefail

_green()  { printf '\033[0;32m%s\033[0m\n' "$1"; }
_yellow() { printf '\033[1;33m%s\033[0m\n' "$1"; }

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

_yellow "▶ Reconfigurar vitals-collector"
echo

# Leer valores actuales para mostrarlos como sugerencia
CURRENT_INGEST_URL=""
CURRENT_MONITOR_ID=""
if [[ -f .env ]]; then
    CURRENT_INGEST_URL="$(grep -m1 'INGEST_URL' .env | cut -d= -f2-)"
fi
if [[ -f identity.json ]]; then
    CURRENT_MONITOR_ID="$(python3 -c "import json,sys; d=json.load(open('identity.json')); print(d.get('monitor_id',''))" 2>/dev/null || true)"
fi

# ── INGEST_URL ─────────────────────────────────────────────────────────────
read -rp "  INGEST_URL [${CURRENT_INGEST_URL:-https://api-reda.fly.dev/api/vitals/ingest}]: " NEW_INGEST_URL
INGEST_URL="${NEW_INGEST_URL:-${CURRENT_INGEST_URL:-https://api-reda.fly.dev/api/vitals/ingest}}"

# ── Identity ───────────────────────────────────────────────────────────────
read -rp "  monitor_id [${CURRENT_MONITOR_ID:-}]: " NEW_MONITOR_ID
MONITOR_ID="${NEW_MONITOR_ID:-$CURRENT_MONITOR_ID}"

read -rsp "  api_key (dejar vacío para no cambiar): " NEW_API_KEY
echo

if [[ -z "$NEW_API_KEY" && -f identity.json ]]; then
    CURRENT_API_KEY="$(python3 -c "import json; d=json.load(open('identity.json')); print(d.get('api_key',''))" 2>/dev/null || true)"
    API_KEY="$CURRENT_API_KEY"
else
    API_KEY="$NEW_API_KEY"
fi

# ── Escribir archivos ──────────────────────────────────────────────────────
cat > .env <<EOF
INGEST_URL=${INGEST_URL}
EOF
_green "  .env actualizado."

cat > identity.json <<EOF
{
    "monitor_id": "${MONITOR_ID}",
    "api_key":    "${API_KEY}"
}
EOF
chmod 600 identity.json
_green "  identity.json actualizado (permisos 600)."

# ── Reiniciar servicio ─────────────────────────────────────────────────────
if systemctl is-active --quiet vitals-collector 2>/dev/null; then
    sudo systemctl restart vitals-collector
    sleep 2
    _green "  Servicio reiniciado."
fi

echo
_green "  Reconfiguración completa."
