"""
config.py — Configuración del colector de signos vitales.

Editar MONITORS con la IP y label de cada monitor de la sala.
La IP debe coincidir con la configurada en el menú de red del monitor.

Variables de entorno reconocidas (sobreescriben los valores por defecto):
  INGEST_URL   — URL del endpoint de ingestión de vitales
  LOG_LEVEL    — DEBUG | INFO | WARNING (default: INFO)
"""

import os

from dotenv import load_dotenv

load_dotenv()  # carga .env si existe (no falla si no está)

# ── Monitores a conectar ───────────────────────────────────────────────────
MONITORS = [
    {"ip": "10.0.0.2", "label": "QF-1"},
]

# ── Red ───────────────────────────────────────────────────────────────────
PORT             = 4601   # puerto Mindray Realtime Interface
ECHO_INTERVAL    = 1.0    # keepalive TCP cada 1s (monitor corta a los 10s sin él)
QRY_DELAY        = 2.0    # esperar burst inicial antes de enviar QRY
RECONNECT_DELAY  = 10.0   # segundos entre reintentos de conexión

# ── Pusher ──────────────────────────────────────────────────────────────
SAVE_INTERVAL    = 15     # segundos entre escrituras al buffer por monitor
REMOTE_TIMEOUT   = 5      # segundos de timeout HTTP
BUFFER_PATH      = "vitals_buffer.db"
INGEST_URL       = os.environ.get("INGEST_URL", "https://api-reda.fly.dev/api/vitals/ingest")

# ── API REST ──────────────────────────────────────────────────────────────
API_HOST         = "0.0.0.0"
API_PORT         = 5000
HISTORY_RAM      = 120    # últimas N lecturas en RAM (para /vitals rápido)

# ── Parámetros Mindray (Appendix B.1 del manual PDS v14.2) ────────────────
# Formato: {param_id: "nombre_en_JSON"}
PARAM_IDS = {
    # ECG
    101: "HR",
    151: "RR",
    # SpO2
    160: "SpO2",
    161: "PR",
    # NIBP — aperiódico (llega al completar medición)
    170: "NIBP_S",
    171: "NIBP_D",
    172: "NIBP_M",
    # IBP canales genéricos CH1–CH2 — periódico
    174: "IBP1_M",  175: "IBP1_S",  176: "IBP1_D",
    178: "IBP2_M",  179: "IBP2_S",  180: "IBP2_D",
    # IBP canales nombrados
    500: "ART_S",   501: "ART_M",   502: "ART_D",
    503: "PA_S",    504: "PA_M",    505: "PA_D",    # presión arterial pulmonar
    566: "CVP_M",                                   # presión venosa central (media)
    # Temperatura
    200: "T1",
    201: "T2",
    # Capnografía — módulo CO2
    220: "EtCO2",
    222: "AWRR",
    # Capnografía + O2 — módulo AG multigas
    250: "EtCO2_AG",
    251: "InsCO2_AG",
    254: "O2_Fi",
}

# Valores centinela del monitor = sensor desconectado → guardar como NULL
INVALID_VALUES = {"-100", "-100.00", "-1000"}

# Lista ordenada de columnas de signos vitales (para la tabla SQLite)
VITAL_COLS = [
    "HR", "RR", "SpO2", "PR",
    "NIBP_S", "NIBP_D", "NIBP_M",
    "IBP1_S", "IBP1_D", "IBP1_M",
    "IBP2_S", "IBP2_D", "IBP2_M",
    "ART_S",  "ART_D",  "ART_M",
    "PA_S",   "PA_M",   "PA_D",
    "CVP_M",
    "T1", "T2",
    "EtCO2", "AWRR",
    "EtCO2_AG", "InsCO2_AG",
    "O2_Fi",
]
