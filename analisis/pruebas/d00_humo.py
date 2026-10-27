"""D0 - Prueba de humo: obligatoria para TODO firmware nuevo, antes de cualquier otra prueba.

Escucha el USB sin enviar ninguna orden de reinicio (salvo --reiniciar) o analiza una captura ya hecha.
Criterio (los tres):
  1. arranca: llega al menos un mensaje HMS "arranque" o "telemetria" (y la version, si se da --version);
  2. no se reinicia durante al menos 120 s observados: encendido_s de la telemetria crece sin volver
     atras, cubre >= 120 s, no aparece un segundo "arranque" ni lineas de panico/assert/reinicio, y el
     puerto no se reconecta;
  3. reporta memoria: al menos una telemetria con heap_libre y heap_minimo.
Con --reiniciar (decision de Deisy, 26/10/2026): se ignora UNA sola linea "rst:0xc (SW_CPU)" que llegue en los
primeros VENTANA_RST_PEDIDO_S segundos tras el AURA REBOOT pedido por consola; cualquier otro reinicio, panico o
linea rst es FALLIDA. Sin --reiniciar el criterio no cambia.
Observaciones (no cambian el resultado): pila minima libre por tarea y lineas "HMS:" sin cuerpo.

  python d00_humo.py --puerto COM5 --id-sesion D0_011 --version 0.1.1
  python d00_humo.py --archivo C:\\aura\\datos\\crudos\\A003.csv
"""

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

from comun import DIR_CRUDOS
from registrar import registrar

sys.path.insert(0, str(DIR_CRUDOS.parents[1] / "analisis"))
from capturar import LectorSerie, nuevo_destino  # noqa: E402

MIN_OBSERVADO_S = 120
PANICO = re.compile(r"assert failed|Guru Meditation|abort\(\) was called|Backtrace:|Rebooting\.\.\.|"
                    r"rst:0x|stack overflow|Stack protection fault", re.IGNORECASE)
# Reinicio pedido con AURA REBOOT: la ROM imprime esta linea ~0,33 s despues (F2, 26/10/2026; el firmware espera
# 300 ms antes de esp_restart, aura_comandos.c:275). 5 s de margen.
EVENTO_REBOOT_CONSOLA = "#AURA reinicio de la placa por consola (AURA REBOOT)"
RST_PEDIDO = re.compile(r"rst:0xc \(SW_CPU\)")
VENTANA_RST_PEDIDO_S = 5.0


def capturar(puerto: str, id_sesion: str, segundos: float, reiniciar: bool) -> Path:
    destino = nuevo_destino(id_sesion)
    lector = LectorSerie(puerto, 115200)
    with open(destino, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_pc_unix", "linea"])
        if reiniciar:
            lector.reiniciar_por_consola()
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


def analizar(archivo: Path, version: str | None) -> dict:
    arranques, encendidos, telemetria, pilas, panico, eventos = [], [], [], [], [], []
    hms_vacias = 0
    with open(archivo, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        next(r, None)
        t_reinicio = None
        rst_pedido_pendiente = False     # se puede ignorar UNA linea rst del AURA REBOOT pedido
        rst_ignorado = []
        for fila in r:
            if len(fila) < 2:
                continue
            linea = fila[1]
            if linea.startswith("#AURA reinicio de la placa"):
                # Reinicio pedido por la prueba: solo cuenta lo que llega despues (y la reconexion que provoca).
                t_reinicio = float(fila[0])
                rst_pedido_pendiente = linea.startswith(EVENTO_REBOOT_CONSOLA)
                arranques, encendidos, telemetria, pilas, panico, eventos = [], [], [], [], [], []
                hms_vacias = 0
                continue
            if linea.startswith("#AURA "):
                if not (t_reinicio and float(fila[0]) - t_reinicio < 20 and "puerto" in linea):
                    eventos.append(linea[6:])
                continue
            if PANICO.search(linea):
                if (rst_pedido_pendiente and RST_PEDIDO.search(linea)
                        and float(fila[0]) - t_reinicio <= VENTANA_RST_PEDIDO_S):
                    rst_pedido_pendiente = False
                    rst_ignorado.append(linea[:160])
                else:
                    panico.append(linea[:160])
            if not linea.startswith("HMS:"):
                continue
            cuerpo = linea[4:].strip()
            if not cuerpo:
                hms_vacias += 1
                continue
            try:
                m = json.loads(cuerpo)
            except json.JSONDecodeError:
                continue
            tipo = m.get("type")
            if tipo == "arranque":
                arranques.append(m)
            elif tipo == "telemetria":
                telemetria.append(m)
                encendidos.append(m.get("encendido_s"))
            elif tipo == "pilas":
                pilas.append(m)
    enc = [e for e in encendidos if isinstance(e, (int, float))]
    monotono = all(b > a for a, b in zip(enc, enc[1:]))
    observado = (enc[-1] - enc[0]) if len(enc) >= 2 else 0
    ver = (arranques[0].get("ver") if arranques else None) or (telemetria[0].get("ver") if telemetria else None)
    memoria = [t for t in telemetria if "heap_libre" in t and "heap_minimo" in t]
    c1 = bool(arranques or telemetria) and (version is None or ver == version)
    c2 = monotono and observado >= MIN_OBSERVADO_S and len(arranques) <= 1 and not panico and not eventos
    c3 = bool(memoria)
    return {
        "c1": c1, "c2": c2, "c3": c3, "ver": ver, "arranques": len(arranques),
        "motivo": (arranques[0].get("motivo_reinicio") if arranques else
                   (telemetria[0].get("motivo_reinicio") if telemetria else None)),
        "observado_s": observado, "encendido": (enc[0], enc[-1]) if enc else None, "monotono": monotono,
        "panico": panico[:3], "rst_pedido_ignorado": rst_ignorado, "eventos": eventos[:3], "hms_vacias": hms_vacias,
        "heap_libre_ult": memoria[-1]["heap_libre"] if memoria else None,
        "heap_libre_min": min(t["heap_libre"] for t in memoria) if memoria else None,
        "heap_minimo": min(t["heap_minimo"] for t in memoria) if memoria else None,
        "pilas": pilas[-1].get("tareas") if pilas else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--puerto")
    ap.add_argument("--id-sesion")
    ap.add_argument("--segundos", type=float, default=150)
    ap.add_argument("--reiniciar", action="store_true", help="reinicia con AURA REBOOT al empezar (por defecto NO)")
    ap.add_argument("--archivo", type=Path, help="analiza una captura existente en vez de capturar")
    ap.add_argument("--version", help="version esperada (p. ej. 0.1.1)")
    ap.add_argument("--nota", default="")
    a = ap.parse_args()
    if a.archivo:
        archivo = a.archivo
    elif a.puerto and a.id_sesion:
        print(f"Escuchando {a.puerto} {a.segundos:.0f} s {'(con AURA REBOOT)' if a.reiniciar else '(sin reiniciar)'}...")
        archivo = capturar(a.puerto, a.id_sesion, a.segundos, a.reiniciar)
    else:
        ap.error("usa --archivo, o --puerto con --id-sesion")
    r = analizar(archivo, a.version)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    ok = r["c1"] and r["c2"] and r["c3"]
    pmin = ""
    if r["pilas"]:
        nombre, t = min(r["pilas"].items(), key=lambda kv: kv[1].get("libre_min", 1 << 30))
        pmin = f"; pila minima libre: {nombre} {t.get('libre_min')} B de {t.get('tam')}"
    valor = (f"ver {r['ver']}, motivo {r['motivo']}, {r['arranques']} arranque(s), encendido_s "
             f"{r['encendido'][0] if r['encendido'] else '?'}->{r['encendido'][1] if r['encendido'] else '?'} "
             f"({r['observado_s']} s sin reinicio), heap_libre {r['heap_libre_ult']} B, heap_minimo {r['heap_minimo']} B")
    fallas = [n for n, c in (("no arranca o version distinta", r["c1"]), ("reinicio/panico o < 120 s observados", r["c2"]),
                             ("sin memoria reportada", r["c3"])) if not c]
    notas = f"{archivo.name}" + pmin + (f"; HMS vacias: {r['hms_vacias']}" if r["hms_vacias"] else "")
    if fallas:
        notas += "; falla: " + ", ".join(fallas)
    if r["panico"]:
        notas += "; panico: " + r["panico"][0]
    if r["rst_pedido_ignorado"]:
        notas += "; ignorada 1 linea rst del AURA REBOOT pedido (decision 26/10/2026)"
    if a.nota:
        notas += "; " + a.nota
    registrar("D0 humo (arranca, 2 min sin reinicio, reporta memoria)", valor,
              "arranca + >=120 s sin reinicio + telemetria con heap", "APROBADA" if ok else "FALLIDA", notas)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
