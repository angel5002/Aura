"""Protocolo AURA compartido por las herramientas de la PC (via local, comandos, OTA, CSI).

Formatos (definidos en C:\\aura\\firmware\\aura_nodo\\main\\aura_local.h y aura_ota.h):
  Anuncio  (broadcast, puerto 45455):  "AURA-ANUNCIO {json}"
  Datos    (unicast, a cada suscriptor): "A1 <seq> <t_us> <tipo> <cuerpo>"   tipo = hms | csi
  Hora:      "TIEMPO <t_pc_us>"  ->  "TIEMPO <t_pc_us> <t_placa_us> <sntp_ok>"
  Comando:   "CMD <ctr> <hmac_hex> <texto>"   hmac = HMAC-SHA256(clave, f"{ctr} {texto}")
  OTA (TCP 45456): "AURAOTA <ctr> <tamano> <sha256> <hmac>\\n" + imagen;  hmac sobre f"{ctr} OTA {tamano} {sha256}"
"""

import base64
import hashlib
import hmac
import json
import struct
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

PUERTO_DATOS = 45454
PUERTO_ANUNCIO = 45455
PUERTO_OTA = 45456
RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO_CLAVE_LOCAL = RAIZ / "secretos" / "clave_local.txt"


@dataclass
class Datagrama:
    seq: int
    t_us: int
    tipo: str
    cuerpo: str


def parsear_datagrama(texto: str) -> Datagrama | None:
    """'A1 <seq> <t_us> <tipo> <cuerpo>' -> Datagrama; None si no es un datagrama de datos."""
    if not texto.startswith("A1 "):
        return None
    partes = texto.split(" ", 4)
    if len(partes) < 5:
        return None
    try:
        return Datagrama(int(partes[1]), int(partes[2]), partes[3], partes[4])
    except ValueError:
        return None


def parsear_anuncio(texto: str) -> dict | None:
    if not texto.startswith("AURA-ANUNCIO "):
        return None
    try:
        return json.loads(texto[len("AURA-ANUNCIO "):])
    except json.JSONDecodeError:
        return None


# ---------------- autenticacion ----------------

def leer_clave_local(ruta: Path | None = None) -> str:
    """Lee la clave compartida de C:\\aura\\secretos\\clave_local.txt (fuera de git) o la pide sin eco."""
    ruta = ruta or ARCHIVO_CLAVE_LOCAL
    if ruta.exists():
        return ruta.read_text(encoding="utf-8").strip()
    import getpass
    return getpass.getpass("Clave local compartida (no se muestra): ")


def firmar(clave: str, mensaje: str) -> str:
    return hmac.new(clave.encode("utf-8"), mensaje.encode("utf-8"), hashlib.sha256).hexdigest()


def nuevo_contador() -> int:
    """Contador creciente = milisegundos UNIX (la placa exige que este a < 120 s de su hora SNTP)."""
    return int(time.time() * 1000)


def mensaje_comando(clave: str, texto: str, ctr: int | None = None) -> str:
    ctr = ctr or nuevo_contador()
    return f"CMD {ctr} {firmar(clave, f'{ctr} {texto}')} {texto}"


def cabecera_ota(clave: str, tamano: int, sha256_hex: str, ctr: int | None = None) -> str:
    ctr = ctr or nuevo_contador()
    return f"AURAOTA {ctr} {tamano} {sha256_hex} {firmar(clave, f'{ctr} OTA {tamano} {sha256_hex}')}\n"


# ---------------- CSI ----------------

def decodificar_csi(cuerpo: dict) -> dict:
    """Decodifica un mensaje 'csi' (JSON con base64).

    raw   = buffer del driver tal cual (sin filtrar ni compensar).
            tipo_dato 1 (C5 en modo LLTF de 16 bits): palabras little-endian de 16 bits con valores de 12 bits
            con signo (misma extension de signo que esp-radar: ((int16)(w << 4)) >> 4).
            tipo_dato 0: bytes con signo.
    valid = subportadoras validas segun la tabla de esp-radar, multiplicadas por 'comp' (esp_csi_gain_ctrl).
    Cada subportadora es un par de valores; la amplitud no depende del orden (Im, Re) del par.
    """
    raw = base64.b64decode(cuerpo.get("raw", ""))
    valid = base64.b64decode(cuerpo.get("valid", ""))
    if cuerpo.get("tipo_dato") == 1:
        palabras = np.frombuffer(raw[: len(raw) // 2 * 2], dtype="<u2").astype(np.int32)
        raw_vals = ((palabras << 4) & 0xFFFF).astype(np.uint16).view(np.int16) >> 4
        valid_vals = np.frombuffer(valid[: len(valid) // 2 * 2], dtype="<i2").astype(np.int32)
    else:
        raw_vals = np.frombuffer(raw, dtype=np.int8).astype(np.int32)
        valid_vals = np.frombuffer(valid, dtype=np.int8).astype(np.int32)
    pares = valid_vals[: len(valid_vals) // 2 * 2].reshape(-1, 2)
    amplitud = np.hypot(pares[:, 0], pares[:, 1])
    return {**{k: v for k, v in cuerpo.items() if k not in ("raw", "valid")},
            "raw_vals": raw_vals, "valid_vals": valid_vals, "amplitud": amplitud}
