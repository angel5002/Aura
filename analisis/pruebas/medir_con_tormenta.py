"""Medicion de memoria CON tormenta de ARP: los minutos cuentan solo desde que la tormenta empieza.

Captura el USB (mismo formato que capturar.py) y vigila {"type":"pila_red"}: la tormenta empieza en el primer
intervalo de 10 s con >= --umbral broadcast. Si no aparece en --espera-max s, se detiene y lo informa como prueba
NO VALIDA. Si aparece, sigue --minutos desde ese momento.

    python medir_con_tormenta.py --puerto COM5 --id-sesion M2_013_tormenta --minutos 20
"""

import argparse
import csv
import json
import sys
import time
from datetime import datetime

from comun import DIR_CRUDOS

sys.path.insert(0, str(DIR_CRUDOS.parents[1] / "analisis"))
from capturar import LectorSerie, nuevo_destino  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--puerto", required=True)
    ap.add_argument("--id-sesion", required=True)
    ap.add_argument("--minutos", type=float, default=20)
    ap.add_argument("--espera-max", type=float, default=600)
    ap.add_argument("--umbral", type=int, default=300)
    a = ap.parse_args()
    destino = nuevo_destino(a.id_sesion)
    lector = LectorSerie(a.puerto, 115200)
    t0 = time.time()
    t_tormenta = None
    fin = t0 + a.espera_max
    with open(destino, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_pc_unix", "linea"])
        while time.time() < fin:
            b = lector.leer_linea()
            for t_ev, txt in lector.eventos:
                w.writerow([f"{t_ev:.6f}", "#AURA " + txt])
            lector.eventos.clear()
            if b is None:
                continue
            t = time.time()
            linea = b.decode("utf-8", errors="replace").rstrip("\r\n")
            w.writerow([f"{t:.6f}", linea])
            if linea.startswith('HMS:{"type":"pila_red"'):
                try:
                    bc = json.loads(linea[4:])["entrada"]["bcast"]
                except (json.JSONDecodeError, KeyError):
                    continue
                hora = datetime.fromtimestamp(t).strftime("%H:%M:%S")
                print(f"{hora}  broadcast en el intervalo: {bc}", flush=True)
                if t_tormenta is None and bc >= a.umbral:
                    t_tormenta = t
                    fin = t + a.minutos * 60
                    w.writerow([f"{t:.6f}", f"#AURA inicio de la tormenta (>= {a.umbral} broadcast/10 s)"])
                    print(f"TORMENTA DETECTADA a las {hora}: cuentan {a.minutos:.0f} min desde ahora", flush=True)
    lector.cerrar()
    if t_tormenta is None:
        print(f"NO VALIDA: no aparecio la tormenta en {a.espera_max:.0f} s. Archivo: {destino}")
        return 2
    print(f"FIN: {a.minutos:.0f} min con tormenta desde las {datetime.fromtimestamp(t_tormenta):%H:%M:%S}. "
          f"Archivo: {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
