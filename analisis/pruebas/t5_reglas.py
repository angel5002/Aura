"""T5 - Reglas de Firebase en el emulador (no toca el proyecto real).

Herramientas instaladas en local en C:\\aura\\firebase (npm, autorizado el 23/10/2026).

Modos:
  python t5_reglas.py
      plantilla database.rules.plantilla.json con UID de prueba.
  python t5_reglas.py --reglas C:\\aura\\firebase\\reglas_publicar.json --uid-usuario <UID> --uid-placa <UID>
      prueba EXACTAMENTE ese archivo (sin sustituciones) con esas identidades; registra su SHA-256 para
      comprobar que lo publicado es lo probado.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from registrar import registrar

RAIZ = Path(__file__).resolve().parents[2]
FB = RAIZ / "firebase"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reglas", type=Path)
    ap.add_argument("--uid-usuario")
    ap.add_argument("--uid-placa")
    a = ap.parse_args()
    instalado = (FB / "node_modules" / "firebase-tools").exists() and \
                (FB / "node_modules" / "@firebase" / "rules-unit-testing").exists()
    if not instalado or not shutil.which("npx"):
        registrar("T5 reglas en emulador", "sin ejecutar", "39/39 casos como se espera", "NO EJECUTADA",
                  "faltan firebase-tools y @firebase/rules-unit-testing en C:\\aura\\firebase\\node_modules")
        return 2
    entorno = dict(os.environ)
    etiqueta = "plantilla (UID de prueba)"
    sha_archivo = None
    if a.reglas:
        if not (a.uid_usuario and a.uid_placa):
            print("ERROR: con --reglas hay que dar --uid-usuario y --uid-placa")
            return 2
        entorno.update(AURA_REGLAS=str(a.reglas.resolve()), AURA_UID_USUARIO=a.uid_usuario, AURA_UID_PLACA=a.uid_placa)
        sha_archivo = hashlib.sha256(a.reglas.read_bytes()).hexdigest()
        etiqueta = f"{a.reglas.name} (SHA-256 {sha_archivo[:16]}...)"
    res_path = FB / "pruebas" / "resultado_t5.json"
    if res_path.exists():
        res_path.unlink()           # resultado de una ejecucion anterior de esta misma prueba
    r = subprocess.run("npx firebase emulators:exec --only database --project demo-aura "
                       "\"node pruebas/reglas.test.mjs\"", cwd=FB, shell=True, capture_output=True, text=True,
                       env=entorno)
    print(r.stdout[-6000:])
    if not res_path.exists():
        registrar(f"T5 reglas en emulador: {etiqueta}", "el emulador no produjo resultados", "39/39", "FALLIDA",
                  (r.stderr or r.stdout)[-300:])
        return 1
    res = json.loads(res_path.read_text(encoding="utf-8"))
    ok = res["fallas"] == 0 and (sha_archivo is None or res.get("sha256") == sha_archivo)
    malos = [f"{x['n']}" for x in res["resultados"] if not x["ok"]]
    notas = []
    if sha_archivo:
        notas.append(f"SHA-256 probado {res.get('sha256')} {'=' if res.get('sha256') == sha_archivo else '!='} archivo")
    if malos:
        notas.append("casos con otro resultado: " + ", ".join(malos))
    registrar(f"T5 reglas en emulador: {etiqueta}", f"{res['total'] - res['fallas']}/{res['total']} como se espera",
              "todos los casos como se espera", "APROBADA" if ok else "FALLIDA", "; ".join(notas))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
