from __future__ import annotations

import logging
import queue
import socket
import threading
import time
import uuid
from datetime import datetime
from typing import Optional

from config import (
    ECHO_INTERVAL,
    PORT,
    QRY_DELAY,
    RECONNECT_DELAY,
    VITAL_COLS,
)
from drivers.base import BaseDriver, VitalReading
from protocol import (
    build_echo,
    build_qry,
    extract_frames,
    parse_bed,
    parse_ctl_id,
    parse_vitals,
)

_SETUP = {
    "106", "103", "11", "12", "51", "58", "60", "53",
    "54",  "56",  "159", "160", "161", "251", "253",
    "256", "205", "207", "320", "451", "501", "504",
    "701", "1202", "5",
}

_APERIODIC_PREFIXES = ("NIBP_", "IBP", "ART_", "PA_", "CVP_")
_EMPTY_VITALS: dict[str, None] = {c: None for c in VITAL_COLS}
_QUEUE_MAXSIZE = 500


class MindrayDriver(BaseDriver):

    def __init__(self, ip: str, label: str = "") -> None:
        self.ip    = ip
        self.label = label

        self._bed: Optional[str] = None
        self._last_nibp: dict    = {}   # cache de presiones aperiódicas
        self._last_vitals: dict  = {}   # última lectura completa (para fusión de módulos)

        self._queue: queue.Queue[VitalReading] = queue.Queue(maxsize=_QUEUE_MAXSIZE)
        self._stop  = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self.log = logging.getLogger(f"driver.mindray.{ip}")

    @property
    def bed(self) -> Optional[str]:
        return self._bed

    def connect(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name=f"mindray-{self.ip}",
            daemon=True,
        )
        self._thread.start()

    def disconnect(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def read_next(self, timeout: float = 1.0) -> Optional[VitalReading]:
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None


    def _run(self) -> None:
        while not self._stop.is_set():
            self.log.info("Conectando a %s:%d …", self.ip, PORT)
            try:
                sock = socket.create_connection((self.ip, PORT), timeout=10)
            except (ConnectionRefusedError, socket.timeout, OSError) as e:
                self.log.warning("Fallo: %s — reintentando en %ds.", e, RECONNECT_DELAY)
                time.sleep(RECONNECT_DELAY)
                continue

            self.log.info("Conectado.")
            stop_echo = threading.Event()
            threading.Thread(
                target=self._echo_loop,
                args=(sock, stop_echo),
                daemon=True,
            ).start()

            try:
                self._session(sock)
            except Exception as e:
                self.log.warning("Sesión terminada: %s", e)
            finally:
                stop_echo.set()
                try:
                    sock.close()
                except OSError:
                    pass
                if not self._stop.is_set():
                    self.log.info("Reconectando en %ds …", RECONNECT_DELAY)
                    time.sleep(RECONNECT_DELAY)

    def _echo_loop(self, sock: socket.socket, stop_event: threading.Event) -> None:
        pkt = build_echo()
        while not stop_event.is_set():
            try:
                sock.sendall(pkt)
            except OSError:
                break
            time.sleep(ECHO_INTERVAL)

    def _session(self, sock: socket.socket) -> None:
        self.log.info("Esperando burst inicial (%.1fs) …", QRY_DELAY)
        time.sleep(QRY_DELAY)
        sock.sendall(build_qry())
        self.log.info("QRY enviado.")

        buf = b""
        sock.settimeout(5)

        while not self._stop.is_set():
            try:
                chunk = sock.recv(65536)
            except socket.timeout:
                continue
            if not chunk:
                raise ConnectionError("Monitor cerró la conexión.")
            buf += chunk
            messages, buf = extract_frames(buf)
            for msg in messages:
                self._handle(msg)


    def _handle(self, msg: str) -> None:
        ctl_id = parse_ctl_id(msg)

        if ctl_id in _SETUP:
            if ctl_id == "103":
                bed = parse_bed(msg)
                if bed:
                    self._bed = bed
                    self.log.info("Cama: %s", bed)
            return

        vitals, is_aperiodic = parse_vitals(msg)
        if not vitals:
            return

        if is_aperiodic:
            aperiodic = {
                k: v for k, v in vitals.items()
                if any(k.startswith(p) for p in _APERIODIC_PREFIXES)
            }
            if aperiodic:
                self._last_nibp.update(aperiodic)
                self.log.info("Aperiódico: %s", aperiodic)

        self._enqueue(vitals, is_aperiodic)

    def _enqueue(self, vitals: dict, is_aperiodic: bool) -> None:
        merged = {**_EMPTY_VITALS, **self._last_vitals, **self._last_nibp, **vitals}
        self._last_vitals = merged

        reading = VitalReading(
            reading_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            vitals=merged,
        )

        try:
            self._queue.put_nowait(reading)
        except queue.Full:
            # Cola llena: descartar la lectura más antigua para liberar espacio
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(reading)
            except queue.Full:
                self.log.warning("Cola llena, lectura descartada.")
