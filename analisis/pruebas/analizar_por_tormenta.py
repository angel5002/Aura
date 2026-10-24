"""Criterios de memoria separados en intervalos CON tormenta (>= umbral broadcast/10 s) y SIN ella.

    python analizar_por_tormenta.py C:\\aura\\datos\\crudos\\M2_013_tormenta.csv [--umbral 300]
Solo cuenta desde la marca "#AURA inicio de la tormenta" (si existe).
Criterios: 0 asignaciones fallidas; minimo por intervalo >= 30 KB; CSI dentro del 5 % de 101,4/s (p5 >= 94,5);
p95 del intervalo entre muestras <= 65 ms; 0 reinicios.
"""

import argparse
import csv
import json
import statistics as st

REF_CSI, REF_P5, MIN_KB = 101.4, 94.5, 30 * 1024


def q(v, p):
    s = sorted(v)
    return s[int(p * (len(s) - 1))] if s else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("archivo")
    ap.add_argument("--umbral", type=int, default=300)
    a = ap.parse_args()
    filas, contar, tel_prev, ultimo = [], False, None, None
    epis = []
    with open(a.archivo, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        next(r)
        tiene_marca = any("inicio de la tormenta" in x[1] for x in csv.reader(open(a.archivo, encoding="utf-8")) if len(x) > 1)
        contar = not tiene_marca
        for x in r:
            if len(x) < 2:
                continue
            l = x[1]
            if "inicio de la tormenta" in l:
                contar = True
                continue
            if not l.startswith("HMS:"):
                continue
            try:
                m = json.loads(l[4:])
            except json.JSONDecodeError:
                continue
            if m.get("type") == "telemetria":
                ultimo = (m, tel_prev)
                tel_prev = m
            elif m.get("type") == "pila_red" and ultimo and contar:
                filas.append((ultimo[0], ultimo[1], m))
            elif m.get("type") == "episodio" and contar:
                epis.append(m)
    grupos = {"CON tormenta": [], "SIN tormenta": []}
    for t, prev, red in filas:
        g = "CON tormenta" if red["entrada"]["bcast"] >= a.umbral else "SIN tormenta"
        grupos[g].append((t, prev, red))
    enc = [t["encendido_s"] for t, _, _ in filas]
    reinicios = sum(1 for x, y in zip(enc, enc[1:]) if y < x)
    print(f"Intervalos analizados: {len(filas)} (encendido {enc[0]} -> {enc[-1]} s); reinicios: {reinicios}; "
          f"episodios (< 30 KB por >= 20 ms): {len(epis)}")
    for nombre, g in grupos.items():
        if not g:
            print(f"\n== {nombre}: sin intervalos ==")
            continue
        mins = [t["heap_min_intervalo"] for t, _, _ in g]
        fallidas = sum(t["malloc_fallidos"] - p["malloc_fallidos"] for t, p, _ in g if p)
        csi = [(t["csi_total"] - p["csi_total"]) / max(1, t["encendido_s"] - p["encendido_s"]) for t, p, _ in g
               if p and t["csi_total"] >= p["csi_total"]]
        p95 = [t["ts_p95_ms"] for t, _, _ in g]
        bc = [r["entrada"]["bcast"] for _, _, r in g]
        cola = [r["cola_max"] for _, _, r in g]
        ok = {
            "0 asignaciones fallidas": (fallidas == 0, f"{fallidas}"),
            "minimo por intervalo >= 30 KB": (min(mins) >= MIN_KB,
                                              f"mediana {st.median(mins) / 1024:.1f} KB, p5 {q(mins, .05) / 1024:.1f}, "
                                              f"min {min(mins) / 1024:.1f} KB ({sum(1 for x in mins if x < MIN_KB)} de {len(mins)} < 30 KB)"),
            "CSI dentro del 5 % (p5 >= 94,5)": (abs(st.median(csi) / REF_CSI - 1) <= 0.05 and q(csi, .05) >= REF_P5,
                                                f"mediana {st.median(csi):.1f}/s ({100 * (st.median(csi) / REF_CSI - 1):+.1f} %), p5 {q(csi, .05):.1f}"),
            "p95 <= 65 ms": (max(p95) <= 65, f"max {max(p95)} ms"),
        }
        print(f"\n== {nombre}: {len(g)} intervalos; broadcast/10 s mediana {st.median(bc):.0f} (max {max(bc)}); "
              f"cola tiT max {max(cola)}/32 ==")
        for k, (bien, v) in ok.items():
            print(f"  [{'CUMPLE' if bien else 'NO CUMPLE'}] {k}: {v}")
    for e in epis[:10]:
        print(f"  episodio {e['inicio_ms'] / 1000:.1f} s dur {e['dur_ms']} ms libre_min {e['libre_min']} cola_max {e['cola_max']} "
              f"bcast {e['entrada']['bcast']}")


if __name__ == "__main__":
    main()
