"""Descarga /crudo/<sensor> de Firebase a la PC y, tras verificarlo, lo BORRA de la nube.

Usa tu cuenta de usuario (las reglas permiten a tu UID leer y borrar /crudo, pero no escribir datos).
Guarda en C:\\aura\\datos\\crudos\\nube_<sensor>_<AAAAMMDD_HHMMSS>.json (fuera de git).
Solo borra los bloques que quedaron guardados y verificados en disco.

Ejemplo:
    python C:\\aura\\analisis\\descargar_crudo.py --sensor hab1            (descarga y borra)
    python C:\\aura\\analisis\\descargar_crudo.py --sensor hab1 --no-borrar
"""

import argparse
import json
import sys
import time
from pathlib import Path

from fb_rest import Sesion, cargar_config, peticion

RAIZ = Path(__file__).resolve().parent.parent
DIR_CRUDOS = RAIZ / "datos" / "crudos"


def main() -> int:
    ap = argparse.ArgumentParser(description="Descarga y borra /crudo de Firebase.")
    ap.add_argument("--sensor", default="hab1")
    ap.add_argument("--no-borrar", action="store_true")
    args = ap.parse_args()

    cfg = cargar_config()
    ses = Sesion(cfg, etiqueta="usuario (lectura de /crudo)")
    codigo, datos = peticion(cfg, "GET", f"/crudo/{args.sensor}", ses)
    if codigo != 200:
        print(f"ERROR: lectura HTTP {codigo}: {datos}")
        return 1
    datos = datos or {}
    print(f"Bloques en la nube: {len(datos)}")
    if not datos:
        return 0
    DIR_CRUDOS.mkdir(parents=True, exist_ok=True)
    destino = DIR_CRUDOS / f"nube_{args.sensor}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    destino.write_text(json.dumps(datos, separators=(",", ":")), encoding="utf-8")
    verificado = json.loads(destino.read_text(encoding="utf-8"))
    if set(verificado) != set(datos):
        print("ERROR: la copia en disco no coincide; no se borra nada.")
        return 1
    tam = destino.stat().st_size
    print(f"Guardado: {destino} ({tam / 1024:.1f} KB)")
    if args.no_borrar:
        return 0
    # Borrado por lotes con PATCH {clave: null} (solo las claves descargadas).
    claves = sorted(datos)
    borrados = 0
    for i in range(0, len(claves), 200):
        lote = {k: None for k in claves[i:i + 200]}
        c, r = peticion(cfg, "PATCH", f"/crudo/{args.sensor}", ses, cuerpo=lote)
        if c != 200:
            print(f"ERROR al borrar (HTTP {c}): {r}. Borrados hasta ahora: {borrados}")
            return 1
        borrados += len(lote)
    print(f"Borrados de la nube: {borrados} bloques")
    return 0


if __name__ == "__main__":
    sys.exit(main())
