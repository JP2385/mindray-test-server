from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("identity")

_DEFAULT_PATH = Path(__file__).parent / "identity.json"


@dataclass(frozen=True)
class Identity:
    monitor_id: str
    api_key: str


def load_identity(path: Path = _DEFAULT_PATH) -> Identity:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        log.error(
            "identity.json no encontrado en %s — "
            "generarlo al registrar el monitor en el panel de administración.",
            path,
        )
        raise
    except json.JSONDecodeError as e:
        log.error("identity.json no es JSON válido: %s", e)
        raise

    missing = [k for k in ("monitor_id", "api_key") if not data.get(k)]
    if missing:
        raise KeyError(f"Campos faltantes o vacíos en identity.json: {missing}")

    return Identity(monitor_id=data["monitor_id"], api_key=data["api_key"])
