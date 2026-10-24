"""Envia un comando autenticado a la placa por la via local (UDP) y muestra su ack.

La clave se lee de C:\\aura\\secretos\\clave_local.txt (fuera de git) o se pide sin eco.
Comandos permitidos por la red: RESET_BASELINE, TRAIN_START AP, TRAIN_STOP AP, SET_CFG AP k=v ...,
SET_AMPLITUDE_LOG on|off, GET_CFG.

Ejemplos:
    python C:\\aura\\analisis\\comando_local.py --ip 192.168.0.13 RESET_BASELINE
    python C:\\aura\\analisis\\comando_local.py --ip 192.168.0.13 TRAIN_START AP
    python C:\\aura\\analisis\\comando_local.py --ip 192.168.0.13 --clave-erronea RESET_BASELINE   (prueba)
"""

import argparse
import json
import socket
import sys
import time

from aura_proto import PUERTO_DATOS, leer_clave_local, mensaje_comando, nuevo_contador, parsear_datagrama


def enviar_comando(ip: str, texto: str, clave: str, espera: float = 5.0, puerto: int = PUERTO_DATOS) -> dict | None:
    """Se suscribe, envia el comando y espera el ack con su id (= contador). Devuelve el ack o None."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("", 0))
    s.settimeout(0.3)
    try:
        s.sendto(b"SUB comando", (ip, puerto))
        ctr = nuevo_contador()
        s.sendto(mensaje_comando(clave, texto, ctr).encode(), (ip, puerto))
        fin = time.time() + espera
        while time.time() < fin:
            try:
                datos, _ = s.recvfrom(65535)
            except socket.timeout:
                continue
            d = parsear_datagrama(datos.decode("utf-8", errors="replace"))
            if not d or d.tipo != "hms":
                continue
            try:
                m = json.loads(d.cuerpo)
            except json.JSONDecodeError:
                continue
            if m.get("type") == "ack" and m.get("id") == str(ctr):
                return m
        return None
    finally:
        try:
            s.sendto(b"UNSUB", (ip, puerto))
        except OSError:
            pass
        s.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Comando autenticado por la via local.")
    ap.add_argument("--ip", required=True)
    ap.add_argument("--clave-erronea", action="store_true", help="firmar con una clave falsa (prueba)")
    ap.add_argument("texto", nargs="+")
    args = ap.parse_args()
    clave = "clave-incorrecta-de-prueba" if args.clave_erronea else leer_clave_local()
    ack = enviar_comando(args.ip, " ".join(args.texto), clave)
    if ack is None:
        print("Sin respuesta (¿IP correcta? ¿firewall?)")
        return 1
    print(json.dumps(ack, ensure_ascii=False))
    return 0 if ack.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
