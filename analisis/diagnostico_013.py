"""Analisis de la observacion de diagnostico de 0.1.3 (telemetria, cpu, pila_red, episodio, tls, auth).

    python diagnostico_013.py C:\\aura\\datos\\crudos\\D0_013.csv C:\\aura\\datos\\crudos\\P3_013.csv
Criterios (23/10/2026): 0 asignaciones fallidas; minimo por intervalo >= 30 KB; CSI dentro del 5 % de la
referencia (mediana 101,4/s; p5 94,5); p95 del intervalo entre muestras <= 65 ms; nube sin errores ni
reintentos anomalos.
"""

import csv
import json
import re
import statistics as st
import sys
from collections import Counter, defaultdict

REF_CSI_MED, REF_CSI_P5 = 101.4, 94.5


def q(v, p):
    s = sorted(v)
    return s[int(p * (len(s) - 1))] if s else float("nan")


def main():
    tel, cpu, red, epis, marcas, logs = {}, {}, {}, [], [], []
    for a in sys.argv[1:]:
        with open(a, newline="", encoding="utf-8") as f:
            r = csv.reader(f)
            next(r, None)
            ultimo_enc = None
            for fila in r:
                if len(fila) < 2:
                    continue
                l = fila[1]
                if l.startswith("HMS:"):
                    try:
                        m = json.loads(l[4:])
                    except json.JSONDecodeError:
                        continue
                    t = m.get("type")
                    if t == "telemetria":
                        ultimo_enc = m["encendido_s"]
                        tel[ultimo_enc] = m
                    elif t == "cpu" and ultimo_enc is not None:
                        cpu[ultimo_enc] = m
                    elif t == "pila_red" and ultimo_enc is not None:
                        red[ultimo_enc] = m
                    elif t == "episodio":
                        epis.append(m)
                    elif t in ("tls", "auth"):
                        marcas.append(m)
                else:
                    mm = re.match(r"^([WE]) \((\d+)\) (.*)", l)
                    if mm and "ping timeout" not in l and "wifi:" not in l and "esp_radar" not in l:
                        logs.append((int(mm.group(2)), l[:180]))
    ks = sorted(tel)
    T = [tel[k] for k in ks]
    enc = [t["encendido_s"] for t in T]
    print(f"Telemetrias {len(T)}: encendido {enc[0]} -> {enc[-1]} s; reinicios {sum(1 for a, b in zip(enc, enc[1:]) if b < a)}; "
          f"ver {T[-1].get('ver')}")
    U = [t for t in T if t["encendido_s"] > 60]
    mins = [t["heap_min_intervalo"] for t in U]
    print("\n== MEMORIA ==")
    print(f"libre: mediana {st.median(t['heap_libre'] for t in U):.0f}; minimo por intervalo: mediana {st.median(mins):.0f}, "
          f"p5 {q(mins, .05)}, min {min(mins)}; intervalos < 30 KB: {sum(1 for x in mins if x < 30720)} de {len(mins)}")
    h = Counter(min(x // 5120 * 5, 60) for x in mins)
    print("  histograma (KB):", ", ".join(f"{k}-{k + 5}: {h[k]}" for k in sorted(h)))
    print(f"bloque mayor: min {min(t['bloque_max'] for t in U)}; asignaciones fallidas {T[-1].get('malloc_fallidos')} "
          f"(mayor {T[-1].get('malloc_fallido_max')} B, caps {T[-1].get('malloc_fallido_caps')}); historico {T[-1].get('heap_minimo')}")

    print("\n== CSI ==")
    csi = [(b["csi_total"] - a["csi_total"]) / (b["encendido_s"] - a["encendido_s"]) for a, b in zip(T, T[1:])
           if b["encendido_s"] > 60 and b["csi_total"] >= a["csi_total"] and b["encendido_s"] > a["encendido_s"]]
    hms = [t["hms_por_s"] for t in U]
    p95 = [t["ts_p95_ms"] for t in U]
    print(f"CSI/s mediana {st.median(csi):.1f} ({100 * (st.median(csi) / REF_CSI_MED - 1):+.1f} %), p5 {q(csi, .05):.1f} "
          f"(ref p5 {REF_CSI_P5}); muestras/s mediana {st.median(hms):.2f} p5 {q(hms, .05):.2f}; "
          f"ts_p95: mediana {st.median(p95)} max {max(p95)} (intervalos > 65 ms: {sum(1 for x in p95 if x > 65)})")

    print("\n== NUBE ==")
    u = T[-1]
    print({k: u.get(k) for k in ("nube", "nube_tokens", "nube_renovaciones", "nube_errores", "nube_escrituras",
                                  "tls_handshakes", "nube_espera_s")})
    fallos = [m for m in marcas if m.get("fase") == "fallo"]
    print(f"marcas tls/auth: {Counter((m['type'], m.get('fase'), m.get('destino')) for m in marcas)}")
    for m in fallos[:10]:
        print(f"  fallo {m.get('destino')} a {m.get('encendido_ms') / 1000:.1f} s: {m.get('error')}")
    errs_int = [(t["encendido_s"], t["nube_errores"]) for t in T]
    saltos = [(e, b - a) for (e, b), (_, a) in zip(errs_int[1:], errs_int) if b > a]
    print(f"intervalos con errores de nube: {saltos[:20]}")

    print("\n== CPU (% por intervalo de 10 s) ==")
    por = defaultdict(list)
    for k, c in cpu.items():
        if c.get("ventana_ms", 0) < 9000 or k <= 60:
            continue
        for n, p, pct in c["t"]:
            por[n].append(pct)
    for n in sorted(por, key=lambda n: -st.median(por[n])):
        v = por[n]
        print(f"  {n:22s} mediana {st.median(v):5.1f}  max {max(v):5.1f}  (n={len(v)})")

    print("\n== PILA DE RED (por intervalo) ==")
    R = [red[k] for k in sorted(red) if k > 60]
    cm = [x["cola_max"] for x in R]
    print(f"cola tcpip: max por intervalo mediana {st.median(cm)}, max {max(cm)} de {R[0]['cola_tam']}; "
          f"descartes por cola llena: {sum(x['entrada']['descartes_cola'] for x in R)}")
    for campo in ("uni", "bcast", "mcast", "ipv4", "ipv6", "arp"):
        v = [x["entrada"][campo] for x in R]
        print(f"  entrada {campo:5s}: mediana {st.median(v):6.0f}  max {max(v):6d}")
    for proto in ("ip", "ip6", "udp", "tcp", "icmp", "arp"):
        rv = [x["lwip"][proto][0] for x in R]
        dv = [x["lwip"][proto][1] for x in R]
        print(f"  lwip {proto:4s}: recibidas mediana {st.median(rv):6.0f} max {max(rv):6d}; descartadas total {sum(dv)}")

    print("\n== CORRELACION: intervalos con minimo < 30 KB vs. el resto ==")
    bajos = [k for k in ks if k > 60 and tel[k]["heap_min_intervalo"] < 30720]
    altos = [k for k in ks if k > 60 and tel[k]["heap_min_intervalo"] >= 30720]

    def media(keys, f):
        v = [f(k) for k in keys if k in red]
        return st.mean(v) if v else float("nan")
    for nombre, f in (("tcp recibidas", lambda k: red[k]["lwip"]["tcp"][0]),
                      ("bcast+mcast", lambda k: red[k]["entrada"]["bcast"] + red[k]["entrada"]["mcast"]),
                      ("cola_max", lambda k: red[k]["cola_max"]),
                      ("escrituras nube", lambda k: tel[k]["nube_escrituras"] - tel.get(k - 10, tel[k])["nube_escrituras"])):
        print(f"  {nombre:16s}: bajos {media(bajos, f):7.2f}   resto {media(altos, f):7.2f}")
    en_tls = sum(1 for k in bajos if any(k * 1000 - 10000 <= m.get("encendido_ms", -1) <= k * 1000 for m in marcas))
    print(f"  intervalos bajos con marca tls/auth: {en_tls} de {len(bajos)}")

    print(f"\n== EPISODIOS (muestreador 20 ms, umbral 30 KB): {len(epis)} ==")
    for e in epis[:12]:
        top = sorted(e["cpu"], key=lambda x: -x[2])[:6]
        print(f"  {e['inicio_ms'] / 1000:8.1f} s dur {e['dur_ms']} ms libre_min {e['libre_min']} bloque_min {e['bloque_min']} "
              f"cola_max {e['cola_max']} entrada {e['entrada']} tcp {e['lwip']['tcp']} cpu {top}")
    print(f"\n== Registros W/E relevantes ({len(logs)}) ==")
    for ms, l in logs[:25]:
        print("  " + l)


if __name__ == "__main__":
    main()
