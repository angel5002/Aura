"""Lee la IP de la placa por USB (sin red, sin descubrimiento por broadcast y sin cambiar el firmware).

ESP-IDF imprime al conectarse "esp_netif_handlers: sta ip: <IP>, mask: ..., gw: ...". Este script escucha el USB
hasta --espera segundos; si no aparece (la placa ya estaba conectada) y se da --reiniciar, envia "AURA REBOOT"
y espera la linea tras el arranque (~15 s). Imprime solo la IP.

    python ip_placa_usb.py --puerto COM7 --reiniciar
Despues:  python receptor_local.py --id-sesion V001 --duracion 2400 --ip <IP> --sin-bind
(El puerto COM no se puede usar a la vez desde dos programas: primero este script, luego capturar.py.)
"""

import argparse
import re
import sys
import time

from capturar import LectorSerie

PATRON = re.compile(r"sta ip: (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})")


def buscar(lector: LectorSerie, segundos: float) -> str | None:
    fin = time.time() + segundos
    while time.time() < fin:
        b = lector.leer_linea()
        if b is None:
            continue
        m = PATRON.search(b.decode("utf-8", errors="replace"))
        if m:
            return m.group(1)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="IP de la placa leida por USB.")
    ap.add_argument("--puerto", default="auto", help="COM de la placa o auto (por defecto: detecta la placa por VID 303A)")
    ap.add_argument("--espera", type=float, default=5, help="segundos escuchando antes de reiniciar")
    ap.add_argument("--reiniciar", action="store_true", help="si no aparece, reiniciar con AURA REBOOT y esperar")
    a = ap.parse_args()
    lector = LectorSerie(a.puerto, 115200)
    try:
        ip = buscar(lector, a.espera)
        if not ip and a.reiniciar:
            print("No aparecio la IP; se reinicia la placa (AURA REBOOT) para que la vuelva a informar...")
            lector.reiniciar_por_consola()
            ip = buscar(lector, 40)
    finally:
        lector.cerrar()
    if not ip:
        print("ERROR: no se encontro la IP. ¿La placa tiene WiFi cargado y la red esta disponible?")
        return 1
    print(ip)
    return 0


if __name__ == "__main__":
    sys.exit(main())
