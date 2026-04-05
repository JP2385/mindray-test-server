from __future__ import annotations

import json
import logging
import threading

import requests

from buffer import Buffer
from config import INGEST_URL, REMOTE_TIMEOUT
from identity import Identity

log = logging.getLogger("pusher")

PUSH_INTERVAL = 60   # segundos entre ciclos de envío
BATCH_MAX     = 5000  # máximo de lecturas por POST


class Pusher(threading.Thread):
    def __init__(self, buffer: Buffer, identity: Identity) -> None:
        super().__init__(name="pusher", daemon=True)
        self._buffer   = buffer
        self._identity = identity
        self._stop     = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        log.info(
            "Pusher iniciado (intervalo=%ds, batch_max=%d, url=%s).",
            PUSH_INTERVAL, BATCH_MAX, INGEST_URL,
        )
        self._push_batch()
        self._buffer.purge_old()

        while not self._stop.wait(PUSH_INTERVAL):
            self._push_batch()
            self._buffer.purge_old()

    def _push_batch(self) -> None:
        pending = self._buffer.get_pending(limit=BATCH_MAX)
        if not pending:
            log.debug("Sin lecturas pendientes.")
            return

        payload = {
            "readings": [
                {
                    "reading_id": r["reading_id"],
                    "timestamp":  r["timestamp"],
                    "vitals":     json.loads(r["vitals"]),
                }
                for r in pending
            ]
        }

        try:
            resp = requests.post(
                INGEST_URL,
                json=payload,
                headers={
                    "X-Monitor-Id": self._identity.monitor_id,
                    "X-Api-Key":    self._identity.api_key,
                    "Content-Type": "application/json",
                },
                timeout=REMOTE_TIMEOUT,
            )
        except requests.RequestException as e:
            log.warning("Error de red al enviar batch: %s — se reintentará en %ds.", e, PUSH_INTERVAL)
            return

        if resp.ok:
            ids = [r["reading_id"] for r in pending]
            self._buffer.mark_sent(ids)
            log.info(
                "Batch enviado: %d lecturas → %s (%d).",
                len(ids), INGEST_URL, resp.status_code,
            )
        else:
            log.warning(
                "Servidor rechazó el batch (%d): %s — se reintentará en %ds.",
                resp.status_code, resp.text[:200], PUSH_INTERVAL,
            )
