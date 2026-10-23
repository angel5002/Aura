"""T2 - Particiones: valida partitions.csv con gen_esp32part.py de ESP-IDF y comprueba que cabe en
4 MB, sin solapamientos, con las apps alineadas a 64 KB y sin pisar el cargador ni la tabla.

Necesita IDF_PATH (ejecutar desde la PowerShell de ESP-IDF) o --idf C:\\esp\\v5.5.6\\esp-idf.
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from registrar import registrar

RAIZ = Path(__file__).resolve().parents[2]
PROY = RAIZ / "firmware" / "aura_nodo"
FLASH = 4 * 1024 * 1024
TABLA = 0xA000           # CONFIG_PARTITION_TABLE_OFFSET
CARGADOR = 0x2000        # offset del bootloader en el C5


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--idf", default=os.environ.get("IDF_PATH", r"C:\esp\v5.5.6\esp-idf"))
    a = ap.parse_args()
    gen = Path(a.idf) / "components" / "partition_table" / "gen_esp32part.py"
    csv_ = PROY / "partitions.csv"
    with tempfile.TemporaryDirectory() as tmp:
        salida = Path(tmp) / "tabla.bin"
        r = subprocess.run([sys.executable, str(gen), "--flash-size", "4MB", "--offset", hex(TABLA),
                            str(csv_), str(salida)], capture_output=True, text=True)
        gen_ok = r.returncode == 0 and salida.exists()
        # Volver a convertir el .bin a CSV: lo que realmente queda grabado
        r2 = subprocess.run([sys.executable, str(gen), str(salida)], capture_output=True, text=True) if gen_ok else None
    errores = []
    if not gen_ok:
        errores.append("gen_esp32part: " + (r.stderr or r.stdout).strip()[-300:])
    filas = []
    if r2 and r2.returncode == 0:
        for linea in r2.stdout.splitlines():
            if linea.startswith("#") or not linea.strip():
                continue
            c = [x.strip() for x in linea.split(",")]
            def num(x):
                x = x.upper()
                return int(x[:-1]) * 1024 * 1024 if x.endswith("M") else int(x[:-1]) * 1024 if x.endswith("K") else int(x, 0)
            filas.append((c[0], c[1], num(c[3]), num(c[4])))
    filas.sort(key=lambda f: f[2])
    fin_cargador = None
    bl = PROY / "build" / "bootloader" / "bootloader.bin"
    if bl.exists():
        fin_cargador = CARGADOR + bl.stat().st_size
        if fin_cargador > TABLA:
            errores.append(f"el cargador termina en {hex(fin_cargador)} > tabla {hex(TABLA)}")
    previo_fin = TABLA + 0x1000
    for nombre, tipo, off, tam in filas:
        if off < previo_fin:
            errores.append(f"{nombre} solapa (empieza {hex(off)} < {hex(previo_fin)})")
        if tipo == "app" and off % 0x10000:
            errores.append(f"{nombre} no alineada a 64 KB")
        previo_fin = off + tam
    if previo_fin > FLASH:
        errores.append(f"la ultima particion termina en {hex(previo_fin)} > 4 MB")
    tabla_txt = "; ".join(f"{n} {hex(o)}+{hex(t)}" for n, _, o, t in filas)
    libre = FLASH - previo_fin
    estado = "APROBADA" if not errores and filas else "FALLIDA"
    registrar("T2 particiones (gen_esp32part)", f"{tabla_txt}; fin {hex(previo_fin)}, libres {libre // 1024} KB"
              + (f"; cargador hasta {hex(fin_cargador)}" if fin_cargador else ""),
              "valida, <= 4 MB, sin solapes, apps alineadas a 64 KB", estado, " / ".join(errores))
    return 0 if estado == "APROBADA" else 1


if __name__ == "__main__":
    sys.exit(main())
