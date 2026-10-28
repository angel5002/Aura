"""resumen.py — imprime el resultado de Playwright (pruebas/salida/resultado.json) en una línea por prueba."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
d = json.loads((Path(__file__).parent / "salida" / "resultado.json").read_text(encoding="utf-8"))


def recorrer(s):
    for sp in s.get("specs", []):
        for t in sp["tests"]:
            r = t["results"][-1]
            err = (r.get("error") or {}).get("message", "")
            notas = "; ".join(f"{a['type']}={a.get('description', '')}" for a in t.get("annotations", []))
            print(f"{r['status']:7s} | {sp['title']} | {r['duration'] / 1000:.1f} s | {notas} | {err[:700]}".replace("\n", " "))
    for c in s.get("suites", []):
        recorrer(c)


for s in d["suites"]:
    recorrer(s)
