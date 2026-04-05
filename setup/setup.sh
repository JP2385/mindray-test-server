#!/usr/bin/env bash
# setup.sh — Puesta en producción de vitals-collector en una Raspberry Pi
#
# Uso (desde el directorio raíz del repositorio clonado):
#   bash setup/setup.sh
#
# Requisitos previos:
#   - Raspberry Pi OS Lite 64-bit, recién instalado
#   - Conectado por SSH (usuario: vitals)
#   - Repositorio ya clonado en /home/vitals/vitals-collector

set -euo pipefail

# ──────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────
_green()  { printf '\033[0;32m%s\033[0m\n' "$1"; }
_yellow() { printf '\033[1;33m%s\033[0m\n' "$1"; }
_red()    { printf '\033[0;31m%s\033[0m\n' "$1"; }
_step()   { echo; _yellow "▶ $1"; }

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ──────────────────────────────────────────────────────────────────────────
# Validaciones iniciales
# ──────────────────────────────────────────────────────────────────────────
if [[ "$(id -u)" -eq 0 ]]; then
    _red "No ejecutar como root. Usar: bash setup/setup.sh"
    exit 1
fi

if [[ ! -f "$REPO_DIR/main.py" ]]; then
    _red "No se encontró main.py en $REPO_DIR — ejecutar desde el directorio del repositorio clonado."
    exit 1
fi

# ──────────────────────────────────────────────────────────────────────────
# Paso 1 — Recolectar datos de configuración
# ──────────────────────────────────────────────────────────────────────────
_step "Configuración de la unidad"

read -rp "  Codigo de institucion (ej. hpc, snr, cmi): " INST_CODE
read -rp "  Numero de unidad dentro de la institucion (ej. 01, 02): " UNIT_NUMBER
HOSTNAME="vitals-${INST_CODE}-${UNIT_NUMBER}"

read -rp "  INGEST_URL (Enter para producción: https://api-reda.fly.dev/api/vitals/ingest): " INGEST_URL_INPUT
INGEST_URL="${INGEST_URL_INPUT:-https://api-reda.fly.dev/api/vitals/ingest}"

echo
_yellow "  Registrar el monitor en el panel de administración antes de continuar."
_yellow "  El sistema generará un monitor_id y una api_key."
echo
read -rp "  monitor_id: " MONITOR_ID
read -rsp "  api_key (oculta): " API_KEY
echo

# ──────────────────────────────────────────────────────────────────────────
# Paso 2 — Actualizar sistema e instalar dependencias del sistema
# ──────────────────────────────────────────────────────────────────────────
_step "Actualizar sistema e instalar dependencias"

sudo apt-get update -y
sudo apt-get upgrade -y
sudo apt-get install -y python3-venv python3-pip

# ──────────────────────────────────────────────────────────────────────────
# Paso 3 — Configurar hostname
# ──────────────────────────────────────────────────────────────────────────
_step "Configurar hostname: $HOSTNAME"

CURRENT_HOSTNAME="$(hostname)"
if [[ "$CURRENT_HOSTNAME" != "$HOSTNAME" ]]; then
    sudo hostnamectl set-hostname "$HOSTNAME"
    # Actualizar /etc/hosts para que el hostname resuelva a localhost
    if ! grep -q "127.0.1.1" /etc/hosts; then
        echo "127.0.1.1    $HOSTNAME" | sudo tee -a /etc/hosts > /dev/null
    else
        sudo sed -i "s/^127\.0\.1\.1.*/127.0.1.1    $HOSTNAME/" /etc/hosts
    fi
    _green "  Hostname configurado: $HOSTNAME"
else
    _green "  Hostname ya es correcto: $HOSTNAME"
fi

# ──────────────────────────────────────────────────────────────────────────
# Paso 4 — Configurar IP estática en eth0 (interfaz hacia el monitor)
# ──────────────────────────────────────────────────────────────────────────
_step "Configurar IP estática en eth0 (10.0.0.1/24)"

# Raspberry Pi OS Bookworm usa NetworkManager; versiones anteriores usan dhcpcd.
# Detectar cuál está activo.
if systemctl is-active --quiet NetworkManager 2>/dev/null; then
    # NetworkManager (Bookworm+)
    NM_CON="eth0-static"
    if nmcli connection show "$NM_CON" &>/dev/null; then
        _green "  Conexión '$NM_CON' ya existe en NetworkManager."
    else
        sudo nmcli connection add \
            type ethernet \
            ifname eth0 \
            con-name "$NM_CON" \
            ipv4.method manual \
            ipv4.addresses "10.0.0.1/24" \
            ipv4.never-default yes \
            connection.autoconnect yes
        _green "  Conexión '$NM_CON' creada en NetworkManager."
    fi
    sudo nmcli connection up "$NM_CON" || true

elif [[ -f /etc/dhcpcd.conf ]]; then
    # dhcpcd (Bullseye y anteriores)
    if grep -q "interface eth0" /etc/dhcpcd.conf; then
        _green "  IP estática ya configurada en dhcpcd.conf."
    else
        printf '\ninterface eth0\nstatic ip_address=10.0.0.1/24\n' | sudo tee -a /etc/dhcpcd.conf > /dev/null
        sudo systemctl restart dhcpcd
        _green "  IP estática configurada en dhcpcd.conf."
    fi

else
    _red "  No se detectó NetworkManager ni dhcpcd. Configurar eth0 manualmente."
    _red "  Continuar con el resto de la instalación..."
fi

# ──────────────────────────────────────────────────────────────────────────
# Paso 5 — Crear virtualenv e instalar dependencias Python
# ──────────────────────────────────────────────────────────────────────────
_step "Crear virtualenv e instalar dependencias Python"

cd "$REPO_DIR"
if [[ ! -d venv ]]; then
    python3 -m venv venv
fi
venv/bin/pip install --upgrade pip --quiet
venv/bin/pip install -r requirements.txt --quiet
_green "  Dependencias instaladas."

# ──────────────────────────────────────────────────────────────────────────
# Paso 6 — Generar .env
# ──────────────────────────────────────────────────────────────────────────
_step "Generar .env"

cat > "$REPO_DIR/.env" <<EOF
INGEST_URL=${INGEST_URL}
EOF
_green "  .env generado."

# ──────────────────────────────────────────────────────────────────────────
# Paso 7 — Generar identity.json
# ──────────────────────────────────────────────────────────────────────────
_step "Generar identity.json"

cat > "$REPO_DIR/identity.json" <<EOF
{
    "monitor_id": "${MONITOR_ID}",
    "api_key":    "${API_KEY}"
}
EOF
chmod 600 "$REPO_DIR/identity.json"
_green "  identity.json generado (permisos 600)."

# ──────────────────────────────────────────────────────────────────────────
# Paso 8 — Instalar y activar el servicio systemd
# ──────────────────────────────────────────────────────────────────────────
_step "Instalar servicio systemd"

SERVICE_SRC="$REPO_DIR/setup/vitals-collector.service"
SERVICE_DST="/etc/systemd/system/vitals-collector.service"

sudo cp "$SERVICE_SRC" "$SERVICE_DST"
sudo systemctl daemon-reload
sudo systemctl enable vitals-collector
sudo systemctl restart vitals-collector

# Esperar un momento y verificar
sleep 3
if systemctl is-active --quiet vitals-collector; then
    _green "  Servicio vitals-collector activo."
else
    _red "  El servicio no arrancó. Ver logs con: journalctl -u vitals-collector -n 50"
fi

# ──────────────────────────────────────────────────────────────────────────
# Resumen final
# ──────────────────────────────────────────────────────────────────────────
echo
_green "════════════════════════════════════════════════════"
_green "  Setup completo — $HOSTNAME"
_green "════════════════════════════════════════════════════"
echo "  Directorio : $REPO_DIR"
echo "  Servicio   : systemctl status vitals-collector"
echo "  Logs live  : journalctl -u vitals-collector -f"
echo
_yellow "  Próximo paso: configurar la IP del monitor en el menú de red del"
_yellow "  equipo Mindray → IP: 10.0.0.2 / Máscara: 255.255.255.0"
echo
