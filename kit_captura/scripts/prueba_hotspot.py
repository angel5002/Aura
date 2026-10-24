"""Mide cuanto tarda la placa en quedar conectada al hotspot (wifi2) cuando la red principal (wifi1) no esta.

Se ejecuta en la PC del proyecto (usa la clave local de C:\\aura\\secretos para el comando autenticado), con la placa
por USB y el HOTSPOT DEL CELULAR ENCENDIDO. Dos modos:

  --modo sim     Placa conectada al WiFi de la casa. Envia "SIM_PIERDE_PRINCIPAL <s>" por la via local: la placa
                 se desconecta, cuenta 3 intentos fallidos simulados (3 s cada uno) y pasa al hotspot.
                 Es una SIMULACION: el intento real sin AP (escaneo de todos los canales) puede tardar mas que 3 s.
  --modo reinicio Para cuando wifi1 NO existe de verdad (p. ej. tras cargar el hotspot como wifi1 o fuera de casa):
                 reinicia la placa (AURA REBOOT) y mide desde el reinicio hasta tener IP, e informa en que red quedo.

Lee el USB y busca los registros de aura_nodo: "paso a la red respaldo", "conectado a la red <red>" y la IP.
    python prueba_hotspot.py --puerto COM5 --modo sim --ip 192.168.0.13
    python prueba_hotspot.py --puerto COM5 --modo reinicio
Al terminar del modo sim: la placa sigue en el hotspot; para volver a casa, reiniciar (AURA REBOOT) o esperar 15 min.
"""

import argparse
import re
import sys
import time
from datetime import datetime

from capturar import LectorSerie
from comando_local import enviar_comando
from aura_proto import leer_clave_local

RX_RED = re.compile(r"aura_wifi: conectado a la red (\w+)")
RX_PASO = re.compile(r"aura_wifi: paso a la red (\w+)")
RX_IP = re.compile(r"sta ip: (\d+\.\d+\.\d+\.\d+)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--puerto", required=True)
    ap.add_argument("--modo", choices=["sim", "reinicio"], required=True)
    ap.add_argument("--ip", help="modo sim: IP actual de la placa en la red de la casa")
    ap.add_argument("--segundos-sim", type=int, default=300)
    ap.add_argument("--espera-max", type=float, default=180)
    a = ap.parse_args()
    lector = LectorSerie(a.puerto, 115200)
    t0 = time.time()
    if a.modo == "sim":
        if not a.ip:
            print("ERROR: --modo sim necesita --ip")
            return 1
        ack = enviar_comando(a.ip, f"SIM_PIERDE_PRINCIPAL {a.segundos_sim}", leer_clave_local())
        t0 = time.time()
        print(f"{datetime.now():%H:%M:%S} SIM_PIERDE_PRINCIPAL {a.segundos_sim} -> {ack}")
        if not ack or not ack.get("ok"):
            print("ERROR: la placa no acepto el comando (¿IP? ¿clave local?)")
            return 1
    else:
        lector.reiniciar_por_consola()
        t0 = time.time()
        print(f"{datetime.now():%H:%M:%S} AURA REBOOT enviado")
    eventos = []
    red = ip = None
    fin = t0 + a.espera_max
    while time.time() < fin and not (red and ip):
        b = lector.leer_linea()
        if b is None:
            continue
        l = b.decode("utf-8", errors="replace")
        for rx, nombre in ((RX_PASO, "paso a"), (RX_RED, "conectado a"), (RX_IP, "IP")):
            m = rx.search(l)
            if m:
                eventos.append((time.time() - t0, nombre, m.group(1)))
                print(f"  +{time.time() - t0:5.1f} s  {nombre} {m.group(1)}", flush=True)
                if nombre == "conectado a" and (a.modo == "reinicio" or m.group(1) == "respaldo"):
                    red = m.group(1)
                if nombre == "IP":
                    ip = m.group(1)     # puede llegar antes que "conectado a la red ..." (mismo milisegundo)
    lector.cerrar()
    if not red:
        print(f"NO CONECTO a ninguna red en {a.espera_max:.0f} s (¿hotspot encendido? ¿wifi2 cargado?)")
        return 2
    t_red = next(t for t, n, v in eventos if n == "conectado a" and v == red)
    print(f"RESULTADO ({a.modo}): conectada a la red {red} a los {t_red:.1f} s; IP {ip or '?'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
