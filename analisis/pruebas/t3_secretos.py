"""T3 - Secretos en la imagen: busca credenciales en el .bin y en la configuracion de aura_nodo.

Valores buscados (se leen del disco y NUNCA se imprimen; solo se informa cuantas coincidencias hay):
  - SSID y contrasena que se cargaron antes por menuconfig (firmware\\wifi_sensing\\sdkconfig)
  - clave local y API key si existen en C:\\aura\\secretos\\
  - cada valor tambien en hexadecimal (asi viajan por la consola USB)
Patrones genericos: marcadores de menuconfig (myssid / mypassword / CONFIG_EXAMPLE_WIFI_*),
claves privadas PEM, "private_key", API keys de Google (AIza...), tokens JWT (eyJ...).
Criterio: 0 coincidencias en aura_nodo.bin, bootloader.bin, sdkconfig, sdkconfig.defaults y build\\config.
"""

import json
import re
import sys
from pathlib import Path

from registrar import registrar

RAIZ = Path(__file__).resolve().parents[2]
PROY = RAIZ / "firmware" / "aura_nodo"
ANTERIOR = RAIZ / "firmware" / "wifi_sensing" / "sdkconfig"
SECRETOS = RAIZ / "secretos"


def valores_conocidos() -> dict:
    vals = {}
    if ANTERIOR.exists():
        for linea in ANTERIOR.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r'CONFIG_EXAMPLE_WIFI_(SSID|PASSWORD)="(.*)"$', linea)
            if m and m.group(2) and m.group(2) not in ("myssid", "mypassword"):
                vals[f"wifi_{m.group(1).lower()}_menuconfig"] = m.group(2).encode()
    clave = SECRETOS / "clave_local.txt"
    if clave.exists():
        vals["clave_local"] = clave.read_text(encoding="utf-8").strip().encode()
    web = SECRETOS / "firebase_web.json"
    if web.exists():
        crudo = json.loads(web.read_text(encoding="utf-8-sig"))
        k = crudo.get("apiKey") or crudo.get("api_key")
        if k:
            vals["fb_api_key"] = k.encode()
    return vals


PATRONES = {
    "marcador myssid": re.compile(rb"myssid"),
    "marcador mypassword": re.compile(rb"mypassword"),
    "CONFIG_EXAMPLE_WIFI_*": re.compile(rb"CONFIG_EXAMPLE_WIFI_(SSID|PASSWORD)"),
    "private_key": re.compile(rb"private_key"),
    "API key de Google": re.compile(rb"AIza[0-9A-Za-z_\-]{35}"),
    "token JWT": re.compile(rb"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
}

# Correccion de falso positivo (autorizada el 23/10/2026): se excluyen SOLO estas tres cadenas exactas, que
# mbedTLS define en components/mbedtls/mbedtls/library/pk_internal.h (lineas 36, 40, 42) para reconocer
# claves al parsearlas, y SOLO si no las sigue un bloque base64. Cualquier otro encabezado PEM de clave
# privada, o cualquier encabezado (incluidos estos) seguido de base64, cuenta como coincidencia.
PEM_ENCABEZADO = re.compile(rb"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")
PEM_EXCLUIDAS = {
    b"-----BEGIN RSA PRIVATE KEY-----",   # PEM_BEGIN_PRIVATE_KEY_RSA            (pk_internal.h:36)
    b"-----BEGIN EC PRIVATE KEY-----",    # PEM_BEGIN_PRIVATE_KEY_EC             (pk_internal.h:40)
    b"-----BEGIN PRIVATE KEY-----",       # PEM_BEGIN_PRIVATE_KEY_PKCS8          (pk_internal.h:42)
    b"-----BEGIN ENCRYPTED PRIVATE KEY-----",  # PEM_BEGIN_ENCRYPTED_PRIVATE_KEY_PKCS8 (pk_internal.h:44),
                                               # exclusion autorizada el 23/10/2026 (misma condicion)
}

# T3b: ningun sdkconfig de aura_nodo (principal y variantes) puede tener opciones de TEXTO con nombre
# sensible y valor no vacio, ni opciones CONFIG_EXAMPLE_WIFI_*. Los secretos viven solo en NVS.
NOMBRE_SENSIBLE = re.compile(r'^(CONFIG_[A-Z0-9_]*(SSID|PASS|PASSWORD|PSK|SECRET|TOKEN|EMAIL|API_KEY|PRIVATE|'
                             r'CREDENTIAL|KEY|USER)[A-Z0-9_]*)="(.*)"$')
SDKCONFIGS = ["sdkconfig", "sdkconfig.rollback", "sdkconfig.build_rx64", "sdkconfig.build_bajo_ram",
              "sdkconfig.defaults", "sdkconfig.prueba_rollback", "sdkconfig.rx64", "sdkconfig.bajo_ram"]


def revisar_sdkconfigs(valores: dict) -> tuple[int, list, int]:
    """Devuelve (hallazgos, detalle sin valores, archivos revisados)."""
    hallazgos, detalle, revisados = 0, [], 0
    for nombre in SDKCONFIGS:
        p = PROY / nombre
        if not p.exists():
            continue
        revisados += 1
        texto = p.read_text(encoding="utf-8", errors="replace")
        for linea in texto.splitlines():
            m = NOMBRE_SENSIBLE.match(linea)
            if m and m.group(3):
                hallazgos += 1
                detalle.append(f"{nombre}:{m.group(1)} con valor")
            if linea.startswith("CONFIG_EXAMPLE_WIFI_"):
                hallazgos += 1
                detalle.append(f"{nombre}:{linea.split('=')[0]}")
        datos = texto.encode("utf-8", errors="replace")
        for clave, v in valores.items():
            n = datos.count(v) + datos.lower().count(v.hex().encode())
            if n:
                hallazgos += n
                detalle.append(f"{nombre}:{clave}={n}")
    return hallazgos, detalle, revisados
BLOQUE_BASE64 = re.compile(rb"[\r\n \t]*[A-Za-z0-9+/]{40,}")


def contar_pem(datos: bytes) -> tuple[int, int]:
    """Devuelve (coincidencias que cuentan, constantes de mbedTLS excluidas)."""
    cuentan = excluidas = 0
    for m in PEM_ENCABEZADO.finditer(datos):
        con_base64 = BLOQUE_BASE64.match(datos, m.end()) is not None
        if m.group() in PEM_EXCLUIDAS and not con_base64:
            excluidas += 1
        else:
            cuentan += 1
    return cuentan, excluidas


def main() -> int:
    archivos = [PROY / "build" / "aura_nodo.bin", PROY / "build" / "bootloader" / "bootloader.bin",
                PROY / "sdkconfig", PROY / "sdkconfig.defaults",
                PROY / "build" / "config" / "sdkconfig.h", PROY / "build" / "config" / "sdkconfig.json"]
    faltan = [str(a) for a in archivos[:3] if not a.exists()]
    if faltan:
        registrar("T3 secretos en la imagen", "faltan archivos", "0 coincidencias", "NO EJECUTADA", ", ".join(faltan))
        return 1
    vals = valores_conocidos()
    total = 0
    detalle = []
    for a in archivos:
        if not a.exists():
            continue
        datos = a.read_bytes()
        n_a = 0
        for nombre, v in vals.items():
            n = datos.count(v) + datos.lower().count(v.hex().encode())
            n_a += n
            if n:
                detalle.append(f"{a.name}:{nombre}={n}")
        for nombre, p in PATRONES.items():
            n = len(p.findall(datos))
            n_a += n
            if n:
                detalle.append(f"{a.name}:{nombre}={n}")
        pem, pem_excl = contar_pem(datos)
        n_a += pem
        if pem:
            detalle.append(f"{a.name}:clave privada PEM={pem}")
        if pem_excl:
            detalle.append(f"{a.name}:constantes PEM de mbedTLS excluidas={pem_excl}")
        total += n_a
    # Informativo: la palabra "password" aparece como NOMBRE de campo (JSON de Identity Toolkit) y en
    # textos de bibliotecas; no es un secreto, pero se informa la cifra.
    n_palabra = (PROY / "build" / "aura_nodo.bin").read_bytes().count(b"password")
    # La contrasena de menuconfig sigue en el proyecto anterior (wifi_sensing), que es el grabado hoy.
    anterior = "no existe"
    if ANTERIOR.exists() and "wifi_password_menuconfig" in vals:
        anterior = f"{ANTERIOR.read_bytes().count(vals['wifi_password_menuconfig'])} coincidencia(s)"
    registrar("T3 secretos en la imagen y sdkconfig de aura_nodo",
              f"{total} coincidencias (valores conocidos buscados: {len(vals)}; patrones: {len(PATRONES)})",
              "0 coincidencias", "APROBADA" if total == 0 else "FALLIDA",
              ("; ".join(detalle) + "; " if detalle else "")
              + f"informativo: palabra 'password' en el .bin = {n_palabra} (nombre de campo/bibliotecas); "
              f"contrasena de menuconfig en firmware\\wifi_sensing\\sdkconfig (proyecto anterior): {anterior}")
    h, det, revisados = revisar_sdkconfigs(vals)
    registrar("T3b sdkconfig de aura_nodo sin valores secretos",
              f"{h} hallazgos en {revisados} archivos sdkconfig (principal, variantes y *.defaults)",
              "0 opciones de texto con nombre sensible y valor; 0 CONFIG_EXAMPLE_WIFI_*; 0 valores conocidos",
              "APROBADA" if h == 0 and revisados >= 4 else "FALLIDA", "; ".join(det))
    return 0 if total == 0 and h == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
