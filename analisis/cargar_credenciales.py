"""Carga las credenciales de la placa en su NVS por USB (nunca se compilan en el firmware).

Claves: wifi1_ssid, wifi1_pass (red principal), wifi2_ssid, wifi2_pass (hotspot de respaldo),
        fb_api_key, fb_db_url (no secretas), fb_email, fb_pass (cuenta del DISPOSITIVO en Firebase),
        local_key (clave compartida de la via local; tambien se guarda en C:\\aura\\secretos\\clave_local.txt).

- Los valores se piden SIN eco (getpass), viajan por USB en hexadecimal ("AURA SET <clave> <hex>") y la
  placa nunca los repite: solo confirma el NOMBRE de la clave. Este script tampoco los imprime.
- Todo lo que se escribe a ciegas (SSID, contrasenas, correo, clave local escrita a mano) se pide DOS
  veces; si no coinciden, se vuelve a preguntar y no se envia nada hasta que coincidan.
- fb_email y fb_pass se prueban ANTES de enviarlos: la PC inicia sesion en Firebase con esa cuenta y solo
  dice "correcto" o "incorrecto" (no muestra valores ni guarda el token). Si es incorrecto, no se envian.
- local_key: si ya existe clave_local.txt, Enter la CONSERVA (y la reenvia a la placa si no la tiene).
  Para generar otra, --nueva-clave-local (habra que usar la nueva en la PC: se guarda en el mismo archivo).
- fb_api_key y fb_db_url se toman de C:\\aura\\secretos\\firebase_web.json si existe.

Ejemplo (placa conectada por USB, con aura_nodo grabado):
    python C:\\aura\\analisis\\cargar_credenciales.py --puerto COM5                 (todas)
    python C:\\aura\\analisis\\cargar_credenciales.py --puerto COM5 --solo fb_pass  (un solo dato)
    python C:\\aura\\analisis\\cargar_credenciales.py --puerto COM5 --claves wifi2_ssid wifi2_pass
    python C:\\aura\\analisis\\cargar_credenciales.py --puerto COM5 --listar
    python C:\\aura\\analisis\\cargar_credenciales.py --puerto COM5 --borrar fb_pass   (modo solo local)
Sin firebase_web.json funciona igual para el WiFi (--solo wifi1_ssid, --solo wifi1_pass, ...).
"""

import argparse
import getpass
import json
import secrets
import sys
import time
from pathlib import Path

import serial

from aura_proto import ARCHIVO_CLAVE_LOCAL
from capturar import abrir_puerto
from fb_rest import cargar_config, probar_inicio_sesion

RAIZ = Path(__file__).resolve().parent.parent
CONFIG_WEB = RAIZ / "secretos" / "firebase_web.json"
UID_PLACA_B = "RSZSiH4Qe5OXnuhwdhYvzYz9Ex22"      # UID de la cuenta de placa-b en las reglas (no es secreto)
CLAVES = ["wifi1_ssid", "wifi1_pass", "wifi2_ssid", "wifi2_pass", "fb_api_key", "fb_db_url",
          "fb_email", "fb_pass", "local_key"]
DESCRIPCION = {
    "wifi1_ssid": "SSID de la red PRINCIPAL", "wifi1_pass": "contrasena de la red PRINCIPAL",
    "wifi2_ssid": "SSID del hotspot de RESPALDO", "wifi2_pass": "contrasena del hotspot de RESPALDO",
    "fb_api_key": "API key web de Firebase", "fb_db_url": "URL de Realtime Database",
    "fb_email": "correo de la cuenta del DISPOSITIVO", "fb_pass": "contrasena de la cuenta del DISPOSITIVO",
}
INTENTOS = 3


def esperar_respuesta(ser, condicion, timeout=4.0):
    fin = time.time() + timeout
    while time.time() < fin:
        linea = ser.readline().decode("utf-8", errors="replace").strip()
        if not linea.startswith("HMS:"):
            continue
        try:
            msg = json.loads(linea[4:])
        except json.JSONDecodeError:
            continue
        if condicion(msg):
            return msg
    return None


def listar(ser) -> dict | None:
    ser.write(b"AURA LIST\n")
    m = esperar_respuesta(ser, lambda m: m.get("type") == "credenciales")
    return m.get("definidas") if m else None


def pedir_doble(texto: str) -> str:
    """Pide un valor sin eco dos veces. Enter en la primera = omitir. Devuelve "" si se omite."""
    for _ in range(INTENTOS):
        v1 = getpass.getpass(f"{texto} (Enter = omitir; no se muestra): ")
        if not v1:
            return ""
        v2 = getpass.getpass("  repitelo para confirmar: ")
        if v1 == v2:
            return v1
        print("  NO COINCIDEN; se vuelve a preguntar (no se envio nada).")
    print(f"  {INTENTOS} intentos sin coincidencia: se omite.")
    return ""


def enviar(ser, clave: str, valor: str) -> bool:
    ser.write(f"AURA SET {clave} {valor.encode('utf-8').hex()}\n".encode())
    r = esperar_respuesta(ser, lambda m: m.get("type") == "ack" and m.get("cmd") == "AURA_SET"
                          and m.get("detail") == clave)
    ok = bool(r and r.get("ok"))
    print(f"  {clave}: {'guardada' if ok else 'ERROR (sin confirmacion)'}")
    return ok


def cuenta_firebase(web: dict, claves: list[str], uid_esperado: str) -> dict:
    """Pide correo y/o contrasena de la cuenta del dispositivo y la prueba. Devuelve lo que se debe enviar."""
    if not web.get("api_key"):
        print("  Falta firebase_web.json: no se puede probar la cuenta; fb_email/fb_pass no se envian.")
        return {}
    for _ in range(INTENTOS):
        email = pedir_doble(f"{DESCRIPCION['fb_email']} [fb_email]"
                            + ("" if "fb_email" in claves else " (solo para la prueba; no se envia)"))
        if not email:
            print("  fb_email/fb_pass: omitidas")
            return {}
        password = pedir_doble(f"{DESCRIPCION['fb_pass']} [fb_pass]"
                               + ("" if "fb_pass" in claves else " (solo para la prueba; no se envia)"))
        if not password:
            print("  fb_email/fb_pass: omitidas")
            return {}
        resultado, uid = probar_inicio_sesion(web, email, password)
        if resultado == "correcto" and uid != uid_esperado:
            print("  Inicio de sesion: correcto, pero NO es la cuenta de la placa de las reglas. No se envia.")
        elif resultado == "correcto":
            print("  Inicio de sesion en Firebase: correcto")
            return {k: v for k, v in (("fb_email", email), ("fb_pass", password)) if k in claves}
        elif resultado == "sin_conexion":
            print("  No se pudo comprobar (sin conexion a internet). No se envia; reintenta con internet.")
            return {}
        else:
            print("  Inicio de sesion en Firebase: incorrecto. No se envia; vuelve a escribirlos.")
    print(f"  {INTENTOS} intentos: fb_email/fb_pass no se enviaron.")
    return {}


def clave_local(nueva: bool) -> tuple[str, str]:
    """Devuelve (valor, origen). Enter conserva la clave existente; sin archivo, Enter genera una."""
    existe = ARCHIVO_CLAVE_LOCAL.exists() and ARCHIVO_CLAVE_LOCAL.read_text(encoding="utf-8").strip()
    if nueva:
        valor, origen = secrets.token_urlsafe(24), "generada (nueva)"
    elif existe:
        v = getpass.getpass("clave local [local_key]: Enter = CONSERVAR la de clave_local.txt; "
                            "o escribe otra (no se muestra): ")
        if not v:
            return ARCHIVO_CLAVE_LOCAL.read_text(encoding="utf-8").strip(), "conservada"
        if v != getpass.getpass("  repitela para confirmar: "):
            print("  NO COINCIDEN: se conserva la clave existente.")
            return ARCHIVO_CLAVE_LOCAL.read_text(encoding="utf-8").strip(), "conservada"
        valor, origen = v, "escrita"
    else:
        v = pedir_doble("clave local [local_key]: Enter = GENERAR una aleatoria (no existe clave_local.txt); "
                        "o escribe una")
        valor, origen = (v, "escrita") if v else (secrets.token_urlsafe(24), "generada")
    ARCHIVO_CLAVE_LOCAL.parent.mkdir(parents=True, exist_ok=True)
    ARCHIVO_CLAVE_LOCAL.write_text(valor, encoding="utf-8")
    print(f"  clave local {origen}; guardada en {ARCHIVO_CLAVE_LOCAL} (fuera de git)")
    return valor, origen


def main() -> int:
    ap = argparse.ArgumentParser(description="Carga credenciales en la NVS de la placa por USB.")
    ap.add_argument("--puerto", required=True)
    grupo = ap.add_mutually_exclusive_group()
    grupo.add_argument("--claves", nargs="+", choices=CLAVES, help="solo estas claves")
    grupo.add_argument("--solo", choices=CLAVES, help="cambiar un unico dato")
    ap.add_argument("--listar", action="store_true", help="solo mostrar que claves estan definidas")
    ap.add_argument("--borrar", choices=CLAVES, help="borrar SOLO esta clave de la placa (AURA DEL)")
    ap.add_argument("--nueva-clave-local", action="store_true",
                    help="generar otra local_key (reemplaza la de clave_local.txt)")
    ap.add_argument("--uid-placa", default=UID_PLACA_B, help="UID esperado de la cuenta del dispositivo")
    ap.add_argument("--reiniciar", action="store_true", help="reiniciar la placa al terminar (AURA REBOOT)")
    args = ap.parse_args()
    claves = [args.solo] if args.solo else (args.claves or CLAVES)

    try:
        ser = abrir_puerto(args.puerto, 115200)
    except serial.SerialException as e:
        print(f"ERROR al abrir {args.puerto}: {e}")
        return 1
    ser.timeout = 0.3
    try:
        estado = listar(ser)
        if estado is None:
            print("ERROR: la placa no respondio a 'AURA LIST'. ¿Esta grabado aura_nodo?")
            return 1
        print("Definidas en la placa:", ", ".join(f"{k}={'si' if v else 'no'}" for k, v in estado.items()))
        if args.listar:
            return 0
        if args.borrar:
            ser.write(f"AURA DEL {args.borrar}\n".encode())
            r = esperar_respuesta(ser, lambda m: m.get("type") == "ack" and m.get("cmd") == "AURA_DEL"
                                  and m.get("detail") == args.borrar)
            print(f"  {args.borrar}: {'borrada' if r and r.get('ok') else 'ERROR (sin confirmacion)'}")
            estado = listar(ser)
            print("Definidas en la placa:", ", ".join(f"{k}={'si' if v else 'no'}" for k, v in (estado or {}).items()))
            if args.reiniciar:
                ser.write(b"AURA REBOOT\n")
                print("Reiniciando la placa...")
            return 0
        web = cargar_config() if CONFIG_WEB.exists() else {}     # apiKey/databaseURL de la consola
        cuenta_hecha = False
        for clave in claves:
            if clave in ("fb_email", "fb_pass"):
                if not cuenta_hecha:
                    cuenta_hecha = True
                    for k, v in cuenta_firebase(web, [c for c in claves if c in ("fb_email", "fb_pass")],
                                                args.uid_placa).items():
                        enviar(ser, k, v)
                continue
            if clave == "fb_api_key" and web.get("api_key"):
                valor = web["api_key"]
            elif clave == "fb_db_url" and web.get("db_url"):
                valor = web["db_url"]
            elif clave == "local_key":
                valor, origen = clave_local(args.nueva_clave_local)
                if origen == "conservada" and estado.get("local_key"):
                    print("  local_key: la placa ya tiene una; se reenvia la conservada para asegurar que coincidan")
            else:
                valor = pedir_doble(f"{DESCRIPCION[clave]} [{clave}]")
            if not valor:
                print(f"  {clave}: omitida")
                continue
            enviar(ser, clave, valor)
            valor = None
        estado = listar(ser)
        print("Definidas en la placa:", ", ".join(f"{k}={'si' if v else 'no'}" for k, v in (estado or {}).items()))
        if args.reiniciar:
            ser.write(b"AURA REBOOT\n")
            print("Reiniciando la placa...")
    finally:
        ser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
