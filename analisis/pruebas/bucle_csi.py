"""Confirmacion del bucle de CSI por retransmision (docs/ensayos/bucle_csi_procedimiento.md).

Escucha el USB de la placa SIN reiniciarla y mide la tasa de CSI que cuenta la PROPIA placa: en cada par de
telemetrias consecutivas (cada 10 s), (csi_total2 - csi_total1) / (encendido_s2 - encendido_s1). No depende del
receptor ni de su perdida. Criterios (fijados antes de ejecutar, ver el procedimiento):
  caso 1 (ningun receptor suscrito, local_subs = 0):          mediana <= 150 CSI/s
  caso 2 (celular recibiendo por WiFi, local_subs >= 1):      mediana >= 300 CSI/s
  caso 3 (PC por cable al Huawei, local_subs >= 1; opcional): mediana <= 150 CSI/s
Validez de cada caso: >= 6 intervalos con la condicion de local_subs del caso y sin reinicio (encendido_s creciente).

  python pruebas\\bucle_csi.py --caso 1 --id-sesion B1 --segundos 120        (captura por USB y evalua)
  python pruebas\\bucle_csi.py --caso 2 --archivo C:\\aura\\datos\\crudos\\B2.csv  (solo evalua una captura)
"""

import argparse
import csv
import json
import statistics
import sys
import time
from pathlib import Path

from comun import DIR_CRUDOS
from registrar import registrar

sys.path.insert(0, str(DIR_CRUDOS.parents[1] / "analisis"))
from capturar import LectorSerie, nuevo_destino  # noqa: E402

MIN_INTERVALOS = 6
CASOS = {
    1: ("ningun receptor suscrito", lambda subs: subs == 0, "<=", 150.0),
    2: ("celular recibiendo por WiFi (AURA-LAB)", lambda subs: subs >= 1, ">=", 300.0),
    3: ("PC recibiendo por cable (puerto LAN del Huawei)", lambda subs: subs >= 1, "<=", 150.0),
}


def capturar(puerto: str, id_sesion: str, segundos: float) -> Path:
    destino = nuevo_destino(id_sesion)
    lector = LectorSerie(puerto, 115200)          # abre con DTR/RTS en bajo: no reinicia la placa
    with open(destino, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_pc_unix", "linea"])
        fin = time.time() + segundos
        while time.time() < fin:
            b = lector.leer_linea()
            for t_ev, txt in lector.eventos:
                w.writerow([f"{t_ev:.6f}", "#AURA " + txt])
            lector.eventos.clear()
            if b is not None:
                w.writerow([f"{time.time():.6f}", b.decode("utf-8", errors="replace").rstrip("\r\n")])
    lector.cerrar()
    return destino


def telemetrias(archivo: Path) -> list[dict]:
    out = []
    with open(archivo, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        next(r, None)
        for fila in r:
            if len(fila) < 2 or not fila[1].startswith("HMS:") or '"type":"telemetria"' not in fila[1]:
                continue
            try:
                m = json.loads(fila[1][4:])
            except json.JSONDecodeError:
                continue
            if all(isinstance(m.get(k), (int, float)) for k in ("csi_total", "encendido_s", "local_subs")):
                out.append(m)
    return out


def evaluar(archivo: Path, caso: int) -> dict:
    nombre, cond_subs, op, umbral = CASOS[caso]
    tel = telemetrias(archivo)
    tasas, fuera_condicion, reinicios = [], 0, 0
    for a, b in zip(tel, tel[1:]):
        dt = b["encendido_s"] - a["encendido_s"]
        if dt <= 0:
            reinicios += 1
            continue
        if not (cond_subs(a["local_subs"]) and cond_subs(b["local_subs"])):
            fuera_condicion += 1
            continue
        tasas.append((b["csi_total"] - a["csi_total"]) / dt)
    r = {"caso": caso, "nombre": nombre, "archivo": archivo.name, "telemetrias": len(tel), "intervalos": len(tasas),
         "fuera_condicion": fuera_condicion, "reinicios": reinicios,
         "mediana": statistics.median(tasas) if tasas else None,
         "min": min(tasas) if tasas else None, "max": max(tasas) if tasas else None,
         "local_subs": sorted({t["local_subs"] for t in tel}), "criterio": f"mediana {op} {umbral:g} CSI/s"}
    valido = len(tasas) >= MIN_INTERVALOS and reinicios == 0
    if not valido:
        r["estado"] = "NO EJECUTADA"
    else:
        ok = r["mediana"] <= umbral if op == "<=" else r["mediana"] >= umbral
        r["estado"] = "APROBADA" if ok else "FALLIDA"
    return r


def main() -> int:
    ap = argparse.ArgumentParser(description="Confirmacion del bucle de CSI (casos 1, 2 y 3).")
    ap.add_argument("--caso", type=int, choices=sorted(CASOS), required=True)
    ap.add_argument("--puerto", default="auto")
    ap.add_argument("--id-sesion")
    ap.add_argument("--segundos", type=float, default=120)
    ap.add_argument("--archivo", type=Path, help="evalua una captura ya hecha en vez de capturar")
    ap.add_argument("--nota", default="")
    a = ap.parse_args()
    if a.archivo:
        archivo = a.archivo
    elif a.id_sesion:
        print(f"Caso {a.caso}: escuchando el USB {a.segundos:.0f} s sin reiniciar la placa...")
        archivo = capturar(a.puerto, a.id_sesion, a.segundos)
    else:
        ap.error("usa --id-sesion (capturar) o --archivo (evaluar)")
    r = evaluar(archivo, a.caso)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    valor = (f"mediana {r['mediana']:.1f} CSI/s (min {r['min']:.1f}, max {r['max']:.1f}) en {r['intervalos']} "
             f"intervalos de 10 s; local_subs {r['local_subs']}" if r["mediana"] is not None
             else f"sin intervalos validos ({r['telemetrias']} telemetrias)")
    notas = (f"{r['archivo']}; {r['nombre']}; fuera de condicion {r['fuera_condicion']}, reinicios {r['reinicios']}"
             + (f"; {a.nota}" if a.nota else ""))
    if r["estado"] == "NO EJECUTADA":
        notas += f"; invalida: hacen falta >= {MIN_INTERVALOS} intervalos con la condicion y sin reinicio"
    registrar(f"Bucle CSI caso {a.caso}", valor, r["criterio"], r["estado"], notas)
    return 0 if r["estado"] == "APROBADA" else 1


if __name__ == "__main__":
    sys.exit(main())
