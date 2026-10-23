"""T1 - Compilacion: con -Os, la imagen debe dejar al menos 20 % libre en cada ranura OTA de 1,5 MB.

Lee el tamano real de build\\aura_nodo.bin y el de las ranuras ota_0/ota_1 de partitions.csv.
Comprueba ademas que la compilacion uso -Os (sdkconfig) sin leer ninguna clave secreta.
"""

import sys
from pathlib import Path

from registrar import registrar

RAIZ = Path(__file__).resolve().parents[2]
PROY = RAIZ / "firmware" / "aura_nodo"


def ranuras_ota() -> dict:
    out = {}
    for linea in (PROY / "partitions.csv").read_text(encoding="utf-8").splitlines():
        if linea.strip().startswith("#") or not linea.strip():
            continue
        c = [x.strip() for x in linea.split(",")]
        if c[1] == "app":
            out[c[0]] = int(c[4], 0)
    return out


def main() -> int:
    binario = PROY / "build" / "aura_nodo.bin"
    if not binario.exists():
        registrar("T1 compilacion", "sin binario", ">= 20 % libre por ranura", "NO EJECUTADA",
                  "compilar primero con idf.py build")
        return 1
    tam = binario.stat().st_size
    o_size = any(l.strip() == "CONFIG_COMPILER_OPTIMIZATION_SIZE=y"
                 for l in (PROY / "sdkconfig").read_text(encoding="utf-8").splitlines())
    ok = o_size
    detalles = []
    for nombre, cap in ranuras_ota().items():
        libre = 100 * (cap - tam) / cap
        detalles.append(f"{nombre}: {tam} de {cap} B, {libre:.2f} % libre")
        ok = ok and libre >= 20.0
    registrar("T1 compilacion (-Os, margen OTA)", "; ".join(detalles) + f"; -Os={'si' if o_size else 'no'}",
              ">= 20 % libre en cada ranura de 1,5 MB y -Os", "APROBADA" if ok else "FALLIDA")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
