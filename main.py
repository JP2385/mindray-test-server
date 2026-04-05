from __future__ import annotations

import logging
import os
import threading
import time

from api import create_app
from buffer import Buffer
from collector import store
from config import API_HOST, API_PORT, MONITORS, SAVE_INTERVAL, VITAL_COLS
from drivers.mindray import MindrayDriver
from identity import load_identity
from pusher import Pusher

_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _LOG_LEVEL, logging.INFO),
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

log = logging.getLogger("main")

_EMPTY_VITALS = {c: None for c in VITAL_COLS}


def _driver_loop(driver: MindrayDriver, buf: Buffer, ip: str, label: str) -> None:
    store.register(ip, label)
    driver.connect()

    last_buf_save: float = 0.0

    while True:
        reading = driver.read_next(timeout=1.0)
        if reading is None:
            continue

        store.push(ip, {
            "monitor_ip": ip,
            "bed":        driver.bed,
            "timestamp":  reading.timestamp.strftime("%Y-%m-%dT%H:%M:%S"),
            **_EMPTY_VITALS,
            **reading.vitals,
        })

        now = time.time()
        if now - last_buf_save >= SAVE_INTERVAL:
            buf.save(reading)
            last_buf_save = now


def main() -> None:
    identity = load_identity()
    log.info("Identidad cargada: monitor_id=%s", identity.monitor_id)

    buf = Buffer()

    pusher = Pusher(buf, identity)
    pusher.start()

    for m in MONITORS:
        ip    = m["ip"]
        label = m.get("label", "")
        driver = MindrayDriver(ip, label)
        threading.Thread(
            target=_driver_loop,
            args=(driver, buf, ip, label),
            name=f"driver-loop-{ip}",
            daemon=True,
        ).start()
        log.info("Driver iniciado: %s (%s)", ip, label)

    app = create_app()
    log.info("API en http://%s:%d  (CTRL+C para detener)", API_HOST, API_PORT)
    app.run(host=API_HOST, port=API_PORT, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
