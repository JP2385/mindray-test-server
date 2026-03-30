"""
test_server.py — Servidor receptor con persistencia PostgreSQL.

Recibe lecturas del colector y las guarda en PostgreSQL (Railway).
Todos los registros quedan disponibles para consulta por rango de tiempo.

Variables de entorno:
  DATABASE_URL  → provista por Railway al agregar el plugin PostgreSQL
  PORT          → provista por Railway (default local: 5001)

Endpoints:
  GET  /health
  POST /vitals
  GET  /vitals?bed=UCE-4&from=2026-03-28T08:00:00&to=2026-03-28T11:00:00

Uso local:
    DATABASE_URL=postgresql://user:pass@host/db python test_server.py
"""

import os
import logging
from datetime import datetime

import psycopg2
import psycopg2.extras
from flask import Flask, request, jsonify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("server")

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("Falta la variable de entorno DATABASE_URL")
# Railway usa 'postgres://' (antigua forma) — psycopg2 necesita 'postgresql://'
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_DDL = """
CREATE TABLE IF NOT EXISTS vitals (
    id         SERIAL      PRIMARY KEY,
    monitor_ip TEXT        NOT NULL,
    bed        TEXT,
    ts         TIMESTAMPTZ NOT NULL,
    data       JSONB       NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vitals_bed_ts ON vitals (bed, ts);
CREATE INDEX IF NOT EXISTS idx_vitals_ip_ts  ON vitals (monitor_ip, ts);
"""


def get_conn():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(_DDL)
    log.info("PostgreSQL listo.")


init_db()


@app.get("/health")
def health():
    return jsonify({"status": "ok", "ts": datetime.now().isoformat()})


@app.post("/vitals")
def receive_vitals():
    """
    Recibe un JSON con una o varias lecturas del colector y las inserta en PostgreSQL.
    """
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "body vacío o no es JSON"}), 400

    readings = data if isinstance(data, list) else [data]
    rows = []
    for r in readings:
        ip  = r.get("monitor_ip", "unknown")
        bed = r.get("bed") or ip
        ts  = r.get("timestamp")
        if not ts:
            continue
        rows.append((ip, bed, ts, psycopg2.extras.Json(r)))
        log.info("  cama=%-8s  ts=%s  HR=%s  SpO2=%s",
                 bed, ts, r.get("HR"), r.get("SpO2"))

    if rows:
        with get_conn() as conn:
            with conn.cursor() as cur:
                psycopg2.extras.execute_values(
                    cur,
                    "INSERT INTO vitals (monitor_ip, bed, ts, data) VALUES %s",
                    rows,
                )

    log.info("Recibidas %d lecturas de %s", len(rows), request.remote_addr)
    return jsonify({"ok": True, "received": len(rows)}), 200


@app.get("/vitals")
def query_vitals():
    """
    Consulta todas las lecturas en un rango de tiempo.

    Parámetros:
      from  → inicio ISO  ej: 2026-03-28T08:00:00  (requerido)
      to    → fin   ISO  ej: 2026-03-28T11:30:00  (requerido)
      bed   → label de la cama  (opcional — sin filtro = todas las camas)
      limit → máximo de filas (default 5000, máximo 50000)

    Ejemplo:
      GET /vitals?bed=UCE-4&from=2026-03-28T08:00:00&to=2026-03-28T11:00:00
    """
    since = request.args.get("from")
    until = request.args.get("to")
    bed   = request.args.get("bed")
    limit = min(int(request.args.get("limit", 5000)), 50000)

    if not since or not until:
        return jsonify({"error": "Se requieren los parámetros 'from' y 'to'"}), 400

    where  = ["ts >= %s", "ts <= %s"]
    params = [since, until]
    if bed:
        where.append("bed = %s")
        params.append(bed)
    params.append(limit)

    sql = (f"SELECT data FROM vitals "
           f"WHERE {' AND '.join(where)} "
           f"ORDER BY ts ASC LIMIT %s")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = [r[0] for r in cur.fetchall()]

    return jsonify({
        "bed":      bed,
        "from":     since,
        "to":       until,
        "n":        len(rows),
        "readings": rows,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    log.info("Servidor escuchando en http://0.0.0.0:%d", port)
    app.run(host="0.0.0.0", port=port, debug=False)
