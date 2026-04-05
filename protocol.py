from config import PARAM_IDS, INVALID_VALUES


MLLP_START = b"\x0B"
MLLP_END   = b"\x1C\x0D"
CR         = "\r"


def mllp_wrap(msg: str) -> bytes:
    return MLLP_START + msg.encode("iso-8859-1") + MLLP_END



def build_echo() -> bytes:
    """Keepalive obligatorio cada 1s (sección 6.7 del manual)."""
    return mllp_wrap(f"MSH|^~\\&|||||||ORU^R01|106|P|2.3.1|{CR}")


def build_qry() -> bytes:
    """QRY^R02 directo al monitor. Enviar DESPUÉS del burst inicial (~2s)."""
    from datetime import datetime
    now  = datetime.now().strftime("%Y%m%d%H%M%S") + "000"
    msg  = f"MSH|^~\\&|||||||QRY^R02|1203|P|2.3.1{CR}"
    msg += f"QRD|{now}|R|I|Q839572|||||RES{CR}"
    msg += f"QRF|MON||||0&0^1^1^1^{CR}"
    return mllp_wrap(msg)


def parse_ctl_id(msg: str) -> str:
    fields = msg.split(CR)[0].split("|")
    return fields[9] if len(fields) > 9 else ""


def parse_bed(msg: str) -> str | None:
    """PV1-3: ^^DEPT&BED& → retorna 'DEPT-BED'."""
    for line in msg.split(CR):
        if not line.startswith("PV1"):
            continue
        fields = line.split("|")
        loc    = fields[3] if len(fields) > 3 else ""
        parts  = loc.split("&")
        if len(parts) >= 2:
            dept = parts[0].lstrip("^")
            bed  = parts[1]
            if dept and bed:
                return f"{dept}-{bed}"
    return None


def parse_vitals(msg: str) -> tuple[dict, bool]:
    vitals       = {}
    is_aperiodic = False

    for line in msg.split(CR):
        if not line.startswith("OBX"):
            continue
        f = line.split("|")
        if len(f) < 6:
            continue

        # OBX-3: "<param_id>^<nombre>"
        obs3   = f[3] if len(f) > 3 else ""
        pid_s  = obs3.split("^")[0].strip()

        value  = f[5]  if len(f) > 5  else ""
        status = f[11] if len(f) > 11 else ""
        flag   = f[13] if len(f) > 13 else ""

        # Solo procesar valores finales
        if status != "F":
            continue

        if flag == "APERIODIC":
            is_aperiodic = True

        try:
            param_id = int(pid_s)
        except ValueError:
            continue

        if param_id not in PARAM_IDS:
            continue

        name = PARAM_IDS[param_id]

        if value in INVALID_VALUES:
            vitals[name] = None
        else:
            try:
                vitals[name] = int(value) if "." not in value else float(value)
            except ValueError:
                vitals[name] = None

    return vitals, is_aperiodic


def extract_frames(buffer: bytes) -> tuple[list[str], bytes]:
    messages = []
    while True:
        i = buffer.find(MLLP_START)
        j = buffer.find(MLLP_END, i)
        if i == -1 or j == -1:
            break
        raw    = buffer[i+1 : j]
        buffer = buffer[j+2 :]
        messages.append(raw.decode("iso-8859-1", errors="replace"))
    return messages, buffer
