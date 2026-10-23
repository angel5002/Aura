"""Registra resultados de pruebas en C:\\aura\\docs\\resultados_pruebas.md (una fila por ejecucion).

Estados: APROBADA, FALLIDA, NO EJECUTADA. Una prueba fallida NUNCA se reescribe como aprobada: cada
ejecucion agrega una fila nueva con su fecha, asi queda el historial completo.
"""

import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
RESULTADOS = RAIZ / "docs" / "resultados_pruebas.md"
ENCABEZADO = """# Resultados de pruebas

Generado por los scripts de `C:\\aura\\analisis\\pruebas\\`. Criterios en `plan_pruebas.md`.
Cada ejecucion agrega una fila; no se editan filas anteriores.

| Fecha | Prueba | Valor medido | Criterio | Resultado | Notas |
|---|---|---|---|---|---|
"""
ESTADOS = ("APROBADA", "FALLIDA", "NO EJECUTADA")


def _limpiar(t) -> str:
    return str(t).replace("|", "/").replace("\n", " ")


def registrar(prueba: str, valor, criterio: str, estado: str, notas: str = "") -> None:
    if estado not in ESTADOS:
        raise ValueError(f"estado invalido: {estado}")
    if not RESULTADOS.exists():
        RESULTADOS.write_bytes(ENCABEZADO.encode("utf-8"))
    fila = (f"| {datetime.now():%Y-%m-%d %H:%M} | {_limpiar(prueba)} | {_limpiar(valor)} | {_limpiar(criterio)} "
            f"| **{estado}** | {_limpiar(notas)} |\n")
    with open(RESULTADOS, "a", encoding="utf-8", newline="\n") as f:
        f.write(fila)
    print(f"[{estado}] {prueba}: {valor}  (criterio: {criterio})")


if __name__ == "__main__":
    registrar(*sys.argv[1:5], *(sys.argv[5:6] or [""]))
