"""Convierte un registro guardado en el celular (terminal serie USB o recepcion UDP) al formato de capturar.py
(t_pc_unix,linea), para usarlo despues con visor.py --reproducir y evaluar_deteccion.py.

Cada linea del registro debe empezar con la hora del celular, p. ej. "01:23:45.678 HMS:{...}" o
"2026-10-25 01:23:45.678 HMS:{...}" (activar las marcas de tiempo en la app ANTES de grabar). Las lineas sin hora
toman la hora de la ultima linea con hora (se avisa cuantas fueron). Si el registro ya es un CSV de
receptor_local.py hecho en Termux, no hace falta convertirlo.

    python convertir_log_celular.py registro.txt --fecha 2026-10-25 --id-sesion C001
"""

import argparse
import csv
import re
import sys
from datetime import datetime
from pathlib import Path

DIR_CRUDOS = Path(__file__).resolve().parent.parent / "datos" / "crudos"
RX = re.compile(r"^\s*(?:(\d{4}-\d{2}-\d{2})[ T])?(\d{1,2}:\d{2}:\d{2}(?:[.,]\d{1,6})?)\s+(.*)$")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("registro", type=Path)
    ap.add_argument("--fecha", required=True, help="AAAA-MM-DD de la grabacion (si la linea no la trae)")
    ap.add_argument("--id-sesion", required=True)
    a = ap.parse_args()
    destino = DIR_CRUDOS / f"{a.id_sesion}.csv"
    if destino.exists():
        print(f"ERROR: {destino} ya existe (no se sobrescribe).")
        return 1
    filas, sin_hora, t_ult = [], 0, None
    for linea in a.registro.read_text(encoding="utf-8", errors="replace").splitlines():
        m = RX.match(linea)
        if m:
            fecha = m.group(1) or a.fecha
            t_ult = datetime.fromisoformat(f"{fecha} {m.group(2).replace(',', '.')}").timestamp()
            texto = m.group(3)
        elif t_ult is not None:
            sin_hora += 1
            texto = linea
        else:
            continue
        if texto.strip():
            filas.append((t_ult, texto.rstrip("\r\n")))
    if not filas:
        print("ERROR: ninguna linea con hora. Activa las marcas de tiempo en la app y vuelve a grabar.")
        return 1
    DIR_CRUDOS.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_pc_unix", "linea"])
        for t, texto in filas:
            w.writerow([f"{t:.6f}", texto])
    n_hms = sum(1 for _, x in filas if x.startswith("HMS:"))
    print(f"{destino.name}: {len(filas)} lineas ({n_hms} HMS); {sin_hora} sin hora propia")
    return 0


if __name__ == "__main__":
    sys.exit(main())
