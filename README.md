# Mindray — Recolector de Signos Vitales

Captura signos vitales en tiempo real desde monitores **Mindray uMEC 12** vía TCP (protocolo HL7/MLLP, PDS v14.2), los persiste localmente en SQLite y los envía a un servidor central en la nube desde donde Nivo-plus puede consultarlos.

## Flujo

```
Monitor Mindray  →  PC colectora (main.py)  →  Servidor central  →  Nivo-plus app
```

## Archivos

| Archivo | Rol |
|---|---|
| `main.py` | Punto de entrada — arranca collectors y la API local |
| `config.py` | **Configuración central** — IPs de monitores, parámetros de red, URL del servidor |
| `collector.py` | Thread TCP por monitor — conexión, keepalive, parseo, fusión de módulos |
| `protocol.py` | MLLP framing y parseo HL7 (funciones puras) |
| `database.py` | Persistencia SQLite + envío HTTP al servidor remoto |
| `api.py` | API REST Flask para consulta local (`/vitals`, `/records`) |
| `test_server.py` | Servidor receptor de prueba (corre en Railway mientras no haya backend real) |
| `Procfile` | Despliegue de `test_server.py` en Railway |

## Configuración rápida

Editar `config.py`:

```python
MONITORS = [
    {"ip": "192.168.68.117", "label": "UCE-4"},
]
REMOTE_URL = "https://mi-servidor.com/api/vitals"  # o None para desactivar
```

## Ejecución

```bash
pip install -r requirements.txt
python main.py
```

La API local queda disponible en `http://localhost:5000`.

## Endpoints de la API local

| Endpoint | Descripción |
|---|---|
| `GET /health` | Ping |
| `GET /monitors` | Estado de conexiones |
| `GET /vitals` | Último valor de todos los monitores |
| `GET /vitals/<ip>` | Último valor de un monitor |
| `GET /records/<ip>?from=...&to=...` | Historial por rango horario |
| `GET /records/<ip>/days` | Días con registros |

## Arquitecturas de red

Ver [ARQUITECTURAS.md](ARQUITECTURAS.md) para las tres opciones de conectividad (cable, Vonets bridge, Raspberry Pi por sala).
