"""Diagnostico de memoria de aura_nodo (>= 0.1.2) a partir de capturas USB (capturar.py / d00_humo.py).

Une en una linea de tiempo (ms desde el arranque) los mensajes:
  memoria  (momentos clave)       tls / auth (inicio, fin, fallo de handshake y de sesion)
  telemetria (cada 10 s: heap_min_intervalo, bloque_max, malloc_fallidos)
y atribuye cada CAIDA (intervalo de 10 s con heap_min_intervalo bajo) a lo que ocurrio en ese intervalo:
handshake inicial, renovacion del token, reconexion de la base, o "sin TLS" (rafaga WiFi u otra causa).
Tambien lista advertencias/errores de esp-tls, mbedtls y asignaciones fallidas.

    python diagnostico_memoria.py C:\\aura\\datos\\crudos\\D0_012.csv C:\\aura\\datos\\crudos\\P2_012.csv
"""

import csv
import json
import re
import sys
from pathlib import Path

PERIODO_MS = 10000
ERRORES = re.compile(r"esp-tls|mbedtls|HTTP_CLIENT|alloc|memoria|heap|E \(|W \(", re.IGNORECASE)


def leer(archivos):
    eventos, telem, logs = [], [], []
    for a in archivos:
        with open(a, newline="", encoding="utf-8") as f:
            r = csv.reader(f)
            next(r, None)
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
                        telem.append(m)
                    elif t in ("memoria", "tls", "auth", "arranque", "red", "ota"):
                        eventos.append(m)
                elif ERRORES.search(l) and not l.startswith("I ("):
                    logs.append(l[:200])
    return eventos, telem, logs


def ms_evento(m):
    return m.get("encendido_ms")


def main():
    archivos = [Path(a) for a in sys.argv[1:]]
    eventos, telem, logs = leer(archivos)
    # telemetria: el intervalo que cierra en encendido_s cubre (encendido_s - 10 s, encendido_s]
    vistos = set()
    tel = []
    for t in telem:
        k = t.get("encendido_s")
        if k in vistos:
            continue
        vistos.add(k)
        tel.append(t)
    tel.sort(key=lambda t: t["encendido_s"])
    enc = [t["encendido_s"] for t in tel]
    reinicios = sum(1 for a, b in zip(enc, enc[1:]) if b < a)

    print(f"Telemetrias: {len(tel)} (encendido {enc[0] if enc else '?'} -> {enc[-1] if enc else '?'} s), reinicios: {reinicios}")
    print("\n== Linea de tiempo de memoria / TLS / sesion ==")
    for m in sorted([e for e in eventos if ms_evento(e) is not None], key=ms_evento):
        t = m.get("type")
        desc = m.get("momento") or f"{m.get('fase')} {m.get('destino')}"
        extra = {k: m[k] for k in ("ms", "reconexion", "ok", "http", "error") if k in m}
        print(f"{ms_evento(m) / 1000:9.1f} s  {t:8s} {desc:28s} libre {m.get('heap_libre')}  "
              f"min_int {m.get('heap_min_intervalo')}  bloque {m.get('bloque_max')}  {extra if extra else ''}")

    print("\n== Intervalos de 10 s con caida (heap_min_intervalo < libre - 8 KB) ==")
    for t in tel:
        fin_ms = t["encendido_s"] * 1000
        ini_ms = fin_ms - PERIODO_MS
        caida = t["heap_libre"] - t.get("heap_min_intervalo", t["heap_libre"])
        if caida < 8192:
            continue
        dentro = [e for e in eventos if ms_evento(e) is not None and ini_ms - 2000 <= ms_evento(e) <= fin_ms]
        causas = sorted({(e.get("type"), e.get("momento") or e.get("destino"), e.get("fase")) for e in dentro} - {(None, None, None)})
        if any(c[0] == "auth" and c[1] == "renovacion" for c in causas):
            atrib = "renovacion del token"
        elif any(c[0] == "auth" and c[1] == "login" for c in causas):
            atrib = "inicio de sesion (handshake inicial)"
        elif any(c[0] == "tls" and c[1] == "db" for c in causas):
            atrib = "handshake con la base (" + ("reconexion" if any(e.get("reconexion") for e in dentro) else "nueva") + ")"
        elif any(c[0] == "memoria" for c in causas):
            atrib = "arranque / momento clave"
        else:
            atrib = "SIN TLS en el intervalo (rafaga WiFi u otra causa)"
        print(f"  {ini_ms / 1000:7.0f}-{fin_ms / 1000:<7.0f} s  min {t['heap_min_intervalo']:6d}  libre {t['heap_libre']:6d}  "
              f"caida {caida:6d}  bloque {t.get('bloque_max')}  -> {atrib}")

    if tel:
        peor = min(tel, key=lambda t: t.get("heap_min_intervalo", 1 << 30))
        print(f"\nMinimo de intervalo mas bajo: {peor.get('heap_min_intervalo')} B en el intervalo que cierra a los "
              f"{peor['encendido_s']} s (bloque mayor al informar {peor.get('bloque_max')} B)")
        print(f"Minimo historico al final: {tel[-1].get('heap_minimo')} B; bloque mayor minimo informado: "
              f"{min(t.get('bloque_max', 1 << 30) for t in tel)} B")
        print(f"malloc fallidos: {tel[-1].get('malloc_fallidos')} (mayor {tel[-1].get('malloc_fallido_max')} B); "
              f"handshakes TLS: {tel[-1].get('tls_handshakes')}; tokens {tel[-1].get('nube_tokens')}, "
              f"renovaciones {tel[-1].get('nube_renovaciones')}, errores nube {tel[-1].get('nube_errores')}")
        print(f"CSI: hms_por_s mediana {sorted(t['hms_por_s'] for t in tel)[len(tel) // 2]}, "
              f"red {sorted({t.get('red') for t in tel})}, nube {sorted({t.get('nube') for t in tel})}")
    print(f"\n== Advertencias/errores ({len(logs)}) ==")
    for l in logs[:40]:
        print("  " + l)


if __name__ == "__main__":
    main()
