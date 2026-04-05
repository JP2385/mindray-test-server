import threading
import logging
from collections import deque

from config import HISTORY_RAM


class Store:
    def __init__(self):
        self._lock   = threading.Lock()
        self._last   = {}
        self._hist   = {}
        self._status = {}
        self._meta   = {}

    def register(self, ip: str, label: str = ""):
        with self._lock:
            if ip not in self._last:
                self._last[ip]   = None
                self._hist[ip]   = deque(maxlen=HISTORY_RAM)
                self._status[ip] = "disconnected"
                self._meta[ip]   = {"label": label or ip}

    def push(self, ip: str, reading: dict):
        with self._lock:
            self._last[ip] = reading
            self._hist[ip].append(reading)

    def get_last(self, ip: str = None):
        with self._lock:
            if ip:
                return self._last.get(ip)
            return {k: v for k, v in self._last.items()}

    def get_monitors(self):
        with self._lock:
            return [
                {
                    "ip":     ip,
                    "label":  self._meta[ip]["label"],
                    "status": self._status[ip],
                    "last_ts": (self._last[ip] or {}).get("timestamp"),
                }
                for ip in self._last
            ]


store = Store()
