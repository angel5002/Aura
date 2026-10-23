"""Agrega una sesión a C:\\aura\\registro_sesiones.csv (UTF-8 sin BOM, fin de línea LF).

Usar SIEMPRE esto (o el módulo csv de Python) para editar el registro; nunca PowerShell.

Ejemplo:
    python C:\\aura\\analisis\\registro.py --id-sesion S001 placa_tx=hotspot placa_rx=B banda=2.4 \\
        personas_en_sala=0 "observaciones=primer arranque de wifi_sensing"
"""

import argparse
import csv
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
REGISTRO = RAIZ / "registro_sesiones.csv"
CONDICIONES = ("vacia", "caminando", "sentada_quieta", "tramos", "")


def columnas() -> list[str]:
    with open(REGISTRO, newline="", encoding="utf-8") as f:
        return next(csv.reader(f))


def ids_existentes() -> set[str]:
    with open(REGISTRO, newline="", encoding="utf-8") as f:
        return {fila["id_sesion"] for fila in csv.DictReader(f)}


def agregar_sesion(fila: dict) -> None:
    cols = columnas()
    desconocidas = set(fila) - set(cols)
    if desconocidas:
        raise ValueError(f"columnas que no existen en el registro: {sorted(desconocidas)}")
    if not fila.get("id_sesion"):
        raise ValueError("falta id_sesion")
    if fila["id_sesion"] in ids_existentes():
        raise ValueError(f"id_sesion {fila['id_sesion']} ya está en el registro")
    if fila.get("condicion_real", "") not in CONDICIONES:
        raise ValueError(f"condicion_real debe ser una de {CONDICIONES}")
    contenido = REGISTRO.read_bytes()
    with open(REGISTRO, "a", newline="", encoding="utf-8") as f:
        if contenido and not contenido.endswith(b"\n"):
            f.write("\n")
        csv.writer(f, lineterminator="\n").writerow([fila.get(c, "") for c in cols])


def main() -> int:
    ap = argparse.ArgumentParser(description="Agrega una fila a registro_sesiones.csv")
    ap.add_argument("--id-sesion", required=True)
    ap.add_argument("campos", nargs="*", help="columna=valor (p. ej. placa_rx=B)")
    args = ap.parse_args()
    fila = {"id_sesion": args.id_sesion}
    for par in args.campos:
        clave, _, valor = par.partition("=")
        fila[clave] = valor
    try:
        agregar_sesion(fila)
    except ValueError as e:
        print(f"ERROR: {e}")
        return 1
    print(f"Sesión {args.id_sesion} agregada a {REGISTRO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
