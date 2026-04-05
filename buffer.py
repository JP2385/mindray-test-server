from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timedelta

from config import BUFFER_PATH
from drivers.base import VitalReading

log = logging.getLogger("buffer")

_DDL = """
CREATE TABLE IF NOT EXISTS readings (
    reading_id   TEXT    PRIMARY KEY,
    timestamp    TEXT    NOT NULL,
    vitals       TEXT    NOT NULL,
    status       TEXT    NOT NULL DEFAULT 'pending',
    created_at   TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_status    ON readings (status);
CREATE INDEX IF NOT EXISTS idx_status_ts ON readings (status, timestamp);
"""


class Buffer:
    PURGE_DAYS = 7

    def __init__(self, path: str = BUFFER_PATH) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._init()
        log.info("Buffer SQLite listo: %s", path)

    def _init(self) -> None:
        with sqlite3.connect(self._path) as conn:
            conn.executescript(_DDL)
            conn.execute("PRAGMA journal_mode=WAL")

    def save(self, reading: VitalReading) -> None:
        row = (
            reading.reading_id,
            reading.timestamp.isoformat(timespec="milliseconds"),
            json.dumps(reading.vitals),
            "pending",
            datetime.utcnow().isoformat(timespec="milliseconds"),
        )
        with self._lock:
            with sqlite3.connect(self._path) as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO readings "
                    "(reading_id, timestamp, vitals, status, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    row,
                )

    def get_pending(self, limit: int = 200) -> list[dict]:
        with self._lock:
            with sqlite3.connect(self._path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT reading_id, timestamp, vitals "
                    "FROM readings WHERE status = 'pending' "
                    "ORDER BY timestamp ASC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def mark_sent(self, reading_ids: list[str]) -> None:
        if not reading_ids:
            return
        placeholders = ",".join("?" * len(reading_ids))
        with self._lock:
            with sqlite3.connect(self._path) as conn:
                conn.execute(
                    f"UPDATE readings SET status = 'sent' WHERE reading_id IN ({placeholders})",
                    reading_ids,
                )
        log.debug("Marcadas %d lecturas como sent.", len(reading_ids))

    def purge_old(self) -> None:
        cutoff = (
            datetime.utcnow() - timedelta(days=self.PURGE_DAYS)
        ).isoformat(timespec="milliseconds")
        with self._lock:
            with sqlite3.connect(self._path) as conn:
                cur = conn.execute(
                    "DELETE FROM readings WHERE status = 'sent' AND timestamp < ?",
                    (cutoff,),
                )
                if cur.rowcount:
                    log.info("Purgadas %d lecturas antiguas.", cur.rowcount)
