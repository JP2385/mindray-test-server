"""
test_server.py — Servidor receptor de prueba.

Simula el endpoint del software real.
- Local:  corre en puerto 5001
- Cloud:  lee el puerto de la variable de entorno PORT (Railway / Render / Fly)

Uso local:
    python test_server.py

Uso en Railway / Render:
    Procfile →  web: python test_server.py
"""

import os
import threading
from flask import Flask, request, jsonify
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("test-server")

app = Flask(__name__)

# Almacén en memoria: bed → última lectura recibida
_store      = {}   # bed → dict con todos los campos
_store_lock = threading.Lock()


@app.post("/vitals")
def receive_vitals():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "body vacío o no es JSON"}), 400

    readings = data if isinstance(data, list) else [data]
    with _store_lock:
        for r in readings:
            bed = r.get("bed") or r.get("monitor_ip", "unknown")
            _store[bed] = r
            log.info("  cama=%-8s  ts=%s  HR=%s  SpO2=%s",
                     bed, r.get("timestamp"), r.get("HR"), r.get("SpO2"))

    log.info("Recibidas %d lecturas de %s", len(readings), request.remote_addr)
    return jsonify({"ok": True, "received": len(readings)}), 200


@app.get("/vitals")
def get_vitals():
    """Devuelve la última lectura de todas las camas."""
    with _store_lock:
        return jsonify(list(_store.values())), 200


@app.get("/vitals/<bed>")
def get_vitals_bed(bed: str):
    """Devuelve la última lectura de una cama específica."""
    with _store_lock:
        reading = _store.get(bed)
    if reading is None:
        return jsonify({"error": f"cama '{bed}' no encontrada"}), 404
    return jsonify(reading), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    log.info("Servidor de prueba escuchando en http://0.0.0.0:%d", port)
    log.info("Endpoint: POST /vitals")
    app.run(host="0.0.0.0", port=port, debug=False)
