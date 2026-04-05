from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class VitalReading:
    """Lectura normalizada de signos vitales, independiente de la marca/protocolo."""

    reading_id: str                  # UUID v4 generado en la RPi (garantiza idempotencia)
    timestamp: datetime              # momento de captura (hora local del dispositivo)
    vitals: dict[str, float | None]  # nombre_parámetro → valor (None = sin señal)


class BaseDriver(ABC):

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def read_next(self, timeout: float = 1.0) -> Optional[VitalReading]: ...
