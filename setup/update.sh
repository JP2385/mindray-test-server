#!/usr/bin/env bash
# update.sh — Actualizar vitals-collector a la versión más reciente del repositorio
#
# Uso:
#   bash setup/update.sh
#
# Hace: git pull, reinstala dependencias si requirements.txt cambió,
# y reinicia el servicio.

set -euo pipefail

_green()  { printf '\033[0;32m%s\033[0m\n' "$1"; }
_yellow() { printf '\033[1;33m%s\033[0m\n' "$1"; }
_red()    { printf '\033[0;31m%s\033[0m\n' "$1"; }

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

_yellow "▶ Actualizando vitals-collector..."

# Guardar hash de requirements.txt antes del pull
REQ_HASH_BEFORE="$(sha256sum requirements.txt | awk '{print $1}')"

git pull --ff-only

REQ_HASH_AFTER="$(sha256sum requirements.txt | awk '{print $1}')"

if [[ "$REQ_HASH_BEFORE" != "$REQ_HASH_AFTER" ]]; then
    _yellow "  requirements.txt cambió — reinstalando dependencias..."
    venv/bin/pip install -r requirements.txt --quiet
    _green "  Dependencias actualizadas."
fi

# Actualizar el archivo .service si cambió
SERVICE_SRC="$REPO_DIR/setup/vitals-collector.service"
SERVICE_DST="/etc/systemd/system/vitals-collector.service"

if ! diff -q "$SERVICE_SRC" "$SERVICE_DST" &>/dev/null; then
    _yellow "  vitals-collector.service cambió — actualizando..."
    sudo cp "$SERVICE_SRC" "$SERVICE_DST"
    sudo systemctl daemon-reload
fi

sudo systemctl restart vitals-collector

sleep 2
if systemctl is-active --quiet vitals-collector; then
    _green "  Servicio reiniciado y activo."
    _green "  Versión: $(git rev-parse --short HEAD)"
else
    _red "  El servicio no arrancó. Ver logs con: journalctl -u vitals-collector -n 50"
    exit 1
fi
