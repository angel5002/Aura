"""Verifica en la PC una captura exportada desde el celular con kit_movil/scripts/exportar.sh.

La carpeta Download/aura_export/<codigo>/ se pasa a la PC por USB en modo "Transferencia de archivos" (MTP, sin
depuracion USB). Este script comprueba cada archivo contra SHA256SUMS (escrito en el celular con los SHA-256 de los
originales). Con --copiar-a-crudos, si TODO coincide, copia los archivos a C:\\aura\\datos\\crudos\\ sin
sobrescribir nada. Despues hay que borrar la copia en el celular (datos de personas).

    python C:\\aura\\analisis\\verificar_export.py C:\\Users\\...\\aura_export\\K001 --copiar-a-crudos
"""

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

DIR_CRUDOS = Path(__file__).resolve().parent.parent / "datos" / "crudos"


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def leer_sumas(ruta: Path) -> dict[str, str]:
    """Formato de sha256sum: '<hex>  <nombre>' (o '<hex> *<nombre>')."""
    sumas = {}
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        hexa, nombre = linea.split(maxsplit=1)
        nombre = nombre.lstrip("*")
        if "/" in nombre or "\\" in nombre or nombre.startswith("."):
            raise ValueError(f"nombre no permitido en SHA256SUMS: {nombre!r}")
        sumas[nombre] = hexa.lower()
    return sumas


def main() -> int:
    ap = argparse.ArgumentParser(description="Verifica una exportacion del kit movil (SHA256SUMS).")
    ap.add_argument("carpeta", type=Path)
    ap.add_argument("--copiar-a-crudos", action="store_true", help=f"si todo coincide, copiar a {DIR_CRUDOS}")
    args = ap.parse_args()
    archivo_sumas = args.carpeta / "SHA256SUMS"
    if not archivo_sumas.exists():
        print(f"ERROR: no existe {archivo_sumas}")
        return 2
    try:
        sumas = leer_sumas(archivo_sumas)
    except ValueError as e:
        print(f"ERROR: {e}")
        return 2
    if not sumas:
        print("ERROR: SHA256SUMS esta vacio")
        return 2
    ok = True
    for nombre, esperado in sumas.items():
        ruta = args.carpeta / nombre
        if not ruta.exists():
            print(f"  FALTA      {nombre}")
            ok = False
            continue
        real = sha256(ruta)
        coincide = real == esperado
        ok = ok and coincide
        print(f"  {'OK        ' if coincide else 'DISTINTO  '} {nombre}  ({real[:16]}...)")
    extra = sorted(p.name for p in args.carpeta.iterdir() if p.is_file() and p.name != "SHA256SUMS"
                   and p.name not in sumas)
    if extra:
        print(f"  AVISO: archivos sin SHA-256 (no se copian): {extra}")
    if not ok:
        print("Resultado: FALLIDO. No uses estos archivos; vuelve a copiar la carpeta desde el celular.")
        return 1
    print(f"Resultado: los {len(sumas)} archivo(s) coinciden con los SHA-256 del celular.")
    if args.copiar_a_crudos:
        ya = [n for n in sumas if (DIR_CRUDOS / n).exists()]
        if ya:
            print(f"ERROR: ya existen en {DIR_CRUDOS}: {ya} (no se sobrescriben datos). No se copio nada.")
            return 3
        DIR_CRUDOS.mkdir(parents=True, exist_ok=True)
        for nombre, esperado in sumas.items():
            destino = DIR_CRUDOS / nombre
            shutil.copy2(args.carpeta / nombre, destino)
            if sha256(destino) != esperado:
                print(f"ERROR: la copia en {destino} no coincide")
                return 1
        print(f"Copiados a {DIR_CRUDOS} y comprobados.")
    print("Ahora BORRA Download/aura_export/<codigo> del celular (datos de personas).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
