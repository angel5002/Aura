"""Tasa de falsas alarmas en una sesion de sala vacia, en crudo y suavizado (mismas reglas que evaluar_deteccion.py).

    python falsas_alarmas.py --sesion S002 [--presencia-desde 01:13:33] [--margen 5]
Movimiento: todo el tramo 'vacia' (tras el margen). Presencia: solo desde --presencia-desde (umbrales validos);
antes del entrenamiento la presencia vale siempre "no" y no se cuenta.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import evaluar_deteccion as ev  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sesion", required=True)
    ap.add_argument("--presencia-desde", help="HH:MM:SS (hora de la PC) desde la que la presencia es valida")
    ap.add_argument("--fecha", default="2026-10-24")
    ap.add_argument("--margen", type=float, default=5.0)
    a = ap.parse_args()
    ruta = ev.DIR_CRUDOS / f"{a.sesion}.csv"
    muestras, _ = ev.leer_hms(ruta, "AP")
    muestras = muestras[muestras["init_stage_name"] == "STABLE"].reset_index(drop=True)
    tramos = ev.leer_verdad(a.sesion, None)
    rej = ev.en_rejilla(muestras, tramos, 1.0)
    rej = rej[(rej["condicion"] == "vacia") & (rej["seg_desde_cambio"] >= a.margen)]
    t_primera = None
    import csv
    for f in csv.reader(open(ruta, encoding="utf-8")):
        if len(f) > 1 and f[0] != "t_pc_unix":
            t_primera = float(f[0])
            break
    t_pres = 0.0
    if a.presencia_desde:
        t_pres = datetime.fromisoformat(f"{a.fecha} {a.presencia_desde}").timestamp() - t_primera
    print(f"{a.sesion}: sala vacia, rejilla 1 s, margen {a.margen} s")
    for nombre, campo, desde in (("movimiento crudo", "motion_status", 0), ("movimiento suav", "motion_suav", 0),
                                 ("presencia crudo", "presence_someone_status", t_pres),
                                 ("presencia suav", "presence_suav", t_pres)):
        r = rej[rej["t"] >= desde]
        fa = int(r[campo].sum())
        print(f"  {nombre:<17} falsas alarmas {fa}/{len(r)} s = {100 * fa / len(r):5.1f} %  "
              f"(especificidad {1 - fa / len(r):.3f}; {len(r) / 60:.1f} min evaluados)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
