"""Convierte las marcas de teclado (<id>_marcas.csv: E entra a la zona, S sale, M marca libre) en
<id>_etiquetas.csv (t_rel_s,condicion) para evaluar_deteccion.py.

Para un salon (nunca vacio) la prueba es de MOVIMIENTO de la persona observada:
  desde E hasta S -> "caminando" (la persona observada se mueve en la zona, cerca de la linea placa-celular)
  desde S hasta E -> "vacia"     (OJO: aqui significa "persona observada fuera de la zona"; el salon esta ocupado)
  antes de la primera marca E/S -> "excluir". Las M se ignoran (quedan solo como referencia).
t_rel_s se cuenta desde la primera linea de la captura USB <id>.csv (como espera el evaluador).

    python marcas_a_etiquetas.py --id-sesion C001
"""

import argparse
import csv
import sys
from pathlib import Path

DIR_CRUDOS = Path(__file__).resolve().parent.parent / "datos" / "crudos"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--id-sesion", required=True)
    a = ap.parse_args()
    captura = DIR_CRUDOS / f"{a.id_sesion}.csv"
    marcas = DIR_CRUDOS / f"{a.id_sesion}_marcas.csv"
    salida = DIR_CRUDOS / f"{a.id_sesion}_etiquetas.csv"
    if salida.exists():
        print(f"ERROR: {salida.name} ya existe (no se sobrescribe).")
        return 1
    t0 = None
    for f in csv.reader(open(captura, encoding="utf-8")):
        if len(f) > 1 and f[0] != "t_pc_unix":
            t0 = float(f[0])
            break
    filas = [("0.000", "excluir")]
    for m in csv.DictReader(open(marcas, encoding="utf-8")):
        cond = {"E": "caminando", "S": "vacia"}.get(m["tecla"])
        if cond:
            filas.append((f"{max(0.0, float(m['t_pc_unix']) - t0):.3f}", cond))
    with open(salida, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_rel_s", "condicion"])
        w.writerows(filas)
    print(f"{salida.name}: {len(filas) - 1} cambios (E -> caminando, S -> vacia = fuera de la zona)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
