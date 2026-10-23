"""Genera database.rules.json a partir de la plantilla, con tu UID y el UID de la placa.

Los UID no son secretos (se ven en la consola de Firebase, pestana Authentication > Usuarios).

Ejemplo:
    python C:\\aura\\firebase\\preparar_reglas.py --uid-usuario AbC... --uid-placa XyZ...
Luego copia el contenido de C:\\aura\\firebase\\database.rules.json en la consola
(Realtime Database > Reglas > Publicar).
"""

import argparse
import json
import re
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent


def generar(uid_usuario: str, uid_placa: str, destino: Path) -> Path:
    for uid in (uid_usuario, uid_placa):
        if not re.fullmatch(r"[A-Za-z0-9_-]{6,128}", uid):
            raise ValueError(f"UID con formato inesperado: {uid!r}")
    if uid_usuario == uid_placa:
        raise ValueError("el UID del usuario y el de la placa deben ser distintos")
    txt = (DIR / "database.rules.plantilla.json").read_text(encoding="utf-8")
    txt = txt.replace("UID_USUARIO", uid_usuario).replace("UID_PLACA", uid_placa)
    json.loads(txt)  # valida que siga siendo JSON
    destino.write_text(txt, encoding="utf-8")
    return destino


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--uid-usuario", required=True)
    ap.add_argument("--uid-placa", required=True)
    ap.add_argument("--salida", type=Path, default=DIR / "database.rules.json")
    a = ap.parse_args()
    print("Reglas generadas en", generar(a.uid_usuario, a.uid_placa, a.salida))
    return 0


if __name__ == "__main__":
    sys.exit(main())
