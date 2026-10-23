"""Propone tamanos de pila a partir de las marcas de agua medidas ({"type":"pilas"} cada 60 s).

Lee capturas USB (lineas "HMS:{...}") y locales (datagramas "A1 ... hms {...}") de datos\\crudos, por
ejemplo las de D1 y D3. Para cada tarea:
    usado_max = tam - min(libre_min)          (en bytes)
    propuesta = redondeo hacia arriba a 256 B de usado_max * 1,25   (margen del 25 %), minimo 2048 B
Solo propone: los tamanos se cambian a mano en firmware\\aura_nodo\\main\\aura_pilas.h.

Ejemplo:
    python pilas_propuesta.py ..\\..\\datos\\crudos\\D1_usb.csv ..\\..\\datos\\crudos\\D3_local.csv
"""

import csv
import json
import math
import sys
from pathlib import Path


def mensajes_pilas(ruta: Path):
    with open(ruta, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        next(r, None)
        for fila in r:
            if len(fila) < 2:
                continue
            linea = fila[1]
            if linea.startswith("HMS:"):
                cuerpo = linea[4:]
            elif linea.startswith("A1 ") and " hms " in linea[:40]:
                cuerpo = linea.split(" ", 4)[4]
            else:
                continue
            if '"type":"pilas"' not in cuerpo:
                continue
            try:
                yield json.loads(cuerpo)
            except json.JSONDecodeError:
                continue


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    tam, libre_min, n = {}, {}, 0
    for ruta in map(Path, sys.argv[1:]):
        for m in mensajes_pilas(ruta):
            n += 1
            for tarea, d in m.get("tareas", {}).items():
                if d.get("libre_min", -1) < 0:
                    continue
                tam[tarea] = d["tam"]
                libre_min[tarea] = min(libre_min.get(tarea, 1 << 30), d["libre_min"])
    if not n:
        print("No hay mensajes 'pilas' en esos archivos (se emiten cada 60 s).")
        return 1
    print(f"Mensajes 'pilas' analizados: {n}\n")
    print(f"{'tarea':<18}{'actual':>8}{'libre_min':>11}{'usado_max':>11}{'propuesta':>11}{'ahorro':>9}")
    total = 0
    for t in sorted(tam):
        usado = tam[t] - libre_min[t]
        prop = max(2048, math.ceil(usado * 1.25 / 256) * 256)
        total += tam[t] - prop
        print(f"{t:<18}{tam[t]:>8}{libre_min[t]:>11}{usado:>11}{prop:>11}{tam[t] - prop:>9}")
    print(f"\nAhorro total si se aplican las propuestas: {total} B ({total / 1024:.1f} KB)")
    print("Aviso: el maximo medido solo cubre los caminos de codigo ejecutados en esas capturas "
          "(por ejemplo, una OTA o una renovacion de token deben haber ocurrido durante la medicion).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
