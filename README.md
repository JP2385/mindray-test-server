# vitals-collector

Software para Raspberry Pi que captura signos vitales de monitores de paciente, los bufferiza localmente y los envia al backend central.

## Arquitectura

```
Monitor (Mindray)
      | Ethernet directo
      v
Raspberry Pi
      +- drivers/mindray.py   captura TCP/HL7
      +- buffer.py             SQLite pending/sent
      +- pusher.py             POST batch cada 60s
                | WiFi
                v
      api-reda (NestJS)
                |
                v
            MongoDB
```

## Estructura

```
drivers/
  base.py        interfaz BaseDriver + dataclass VitalReading
  mindray.py     driver Mindray RTI (TCP/HL7)
buffer.py        SQLite con estados pending/sent, purga automatica 7 dias
pusher.py        thread que envia batches al servidor central
identity.py      carga monitor_id y api_key desde identity.json
collector.py     Store en RAM (lecturas en tiempo real)
api.py           API Flask local: /health, /monitors, /vitals
config.py        configuracion: monitores, red, paths, URL de ingest
main.py          punto de entrada
```

## Convencion de nombres

Cada Raspberry Pi recibe un nombre de host con el formato:

```
vitals-<inst>-NN
```

Donde:
- `<inst>` es un codigo corto de la institucion (3-4 letras minusculas, ej. `hpc` para Hospital Provincial Cordoba, `snr` para Sanatorio Norte).
- `NN` es el numero correlativo dentro de esa institucion (01, 02, ...).

Ejemplos: `vitals-hpc-01`, `vitals-hpc-02`, `vitals-snr-01`, ...

El codigo de institucion mas el numero correlativo identifican el equipo de forma unica en toda la flota. Usar el mismo esquema en el nombre del monitor dentro del panel de administracion para facilitar la trazabilidad (ej. el dispositivo `vitals-hpc-03` gestiona el monitor `HPC-3`).

---

## Puesta en produccion (desde cero)

### 1. Instalar Raspberry Pi OS (unico paso manual en PC)

**Prerequisitos:**
- Raspberry Pi 4 Model B o superior (Ethernet + WiFi simultaneos)
- Tarjeta microSD de 16 GB o mas
- PC con [Raspberry Pi Imager](https://www.raspberrypi.com/software/) instalado

**Pasos:**

1. Abrir Raspberry Pi Imager.
2. Elegir dispositivo: **Raspberry Pi 4**.
3. Elegir sistema operativo: **Raspberry Pi OS Lite (64-bit)** (sin interfaz grafica).
4. Elegir la tarjeta SD como destino.
5. Antes de escribir, abrir **ajustes avanzados** (icono de engranaje o Ctrl+Shift+X) y configurar:
   - **Usuario:** `vitals` / contrasena segura
   - **WiFi:** SSID y contrasena de la red hospitalaria
   - **Locale:** America/Argentina/Buenos_Aires / es_AR
   - **Habilitar SSH:** activado, con autenticacion por contrasena
   - **Hostname:** dejar en blanco (lo configura `setup.sh`)
6. Escribir la imagen en la SD, insertarla en la RPi y encender.
7. Esperar ~60 segundos y conectarse (buscar la IP en el router si el nombre .local no resuelve):

```
ssh vitals@raspberrypi.local
```

### 2. Registrar el monitor en el panel de administracion

Crear el monitor en la app antes de continuar. Guardar el `monitor_id` y la `api_key` que genera el sistema.

### 3. Clonar el repositorio y ejecutar el setup

```bash
git clone https://github.com/<org>/vitals-collector.git
cd vitals-collector
bash setup/setup.sh
```

El script solicita de forma interactiva:
- Codigo de institucion (ej. `hpc`) + numero de unidad (ej. `01`) → configura hostname `vitals-hpc-01`
- `INGEST_URL` (Enter para usar produccion)
- `monitor_id` y `api_key` obtenidos en el paso anterior

Al finalizar, el servicio queda activo y arranca automaticamente en cada reinicio.

### 4. Configurar el monitor Mindray

En el menu de red del equipo Mindray: IP `10.0.0.2` / Mascara `255.255.255.0`.

La RPi ya tiene configurada la IP `10.0.0.1/24` en el puerto Ethernet.

### Verificar

```bash
journalctl -u vitals-collector -f
```

Logs esperados:

```
INFO  identity   Identidad cargada: monitor_id=...
INFO  buffer     Buffer SQLite listo: vitals_buffer.db
INFO  pusher     Pusher iniciado (intervalo=60s ...)
INFO  driver...  Conectado.
INFO  driver...  Cama: UCE-1
```

---

## Actualizaciones

Para actualizar el software en una RPi ya instalada:

```bash
cd vitals-collector
bash setup/update.sh
```

Hace `git pull`, reinstala dependencias si cambiaron, actualiza el `.service` si cambio y reinicia el proceso.

## Reconfiguracion

Para cambiar `monitor_id`, `api_key` o `INGEST_URL` sin reinstalar nada:

```bash
bash setup/reconfigure.sh
```

---

## Agregar soporte para otra marca de monitor

1. Crear `drivers/<marca>.py` implementando `BaseDriver` (ver `drivers/base.py`)
2. Instanciar el nuevo driver en `main.py` igual que `MindrayDriver`
3. No hay ningun otro cambio en el pipeline
