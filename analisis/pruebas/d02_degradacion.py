"""D2 - Sin degradacion con todas las vias activas.

Recibe 10 min por la via local (con la nube operando y el USB conectado) y evalua:
  - intervalo de ts_ms: mediana de las medianas por ventana de 10 s (telemetria de la placa) <= 62 ms y
    percentil 95 de los p95 por ventana <= 65 ms (referencia S001 con wifi_sensing: 60 y 61 ms);
  - hms_por_s >= 90 % de 16,3/s (tasa por canal medida en S001).
Tambien recalcula los intervalos desde las muestras recibidas (informativo: la perdida local los afecta).
"""

import argparse
import sys

from comun import Coleccion, intervalos_ts, ip_placa, mediana, percentil, recibir_en_hilo
from registrar import registrar

REF_HMS = 16.3


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ip")
    ap.add_argument("--minutos", type=float, default=10)
    ap.add_argument("--id-sesion", default="D2")
    a = ap.parse_args()
    ip = ip_placa(a.ip)
    col = Coleccion()
    h, res = recibir_en_hilo(ip, a.id_sesion, a.minutos * 60, col)
    h.join()
    tel = [t for _, t in col.telemetria if t.get("n_intervalos", 0) > 0]
    if not tel:
        registrar("D2 sin degradacion", "sin telemetria", "mediana <= 62, p95 <= 65, hms >= 90 %", "FALLIDA")
        return 1
    med = mediana([t["ts_mediana_ms"] for t in tel])
    p95 = percentil([t["ts_p95_ms"] for t in tel], 95)
    hms = mediana([t["hms_por_s"] for t in tel])
    nube = {t.get("nube") for t in tel}
    usb = {t.get("usb") for t in tel}
    iv = intervalos_ts(col.muestras)
    ok = med <= 62 and p95 <= 65 and hms >= 0.9 * REF_HMS
    registrar("D2 sin degradacion", f"mediana {med:.1f} ms, p95 {p95:.1f} ms, hms {hms:.2f}/s "
              f"(desde muestras locales: mediana {mediana(iv):.1f}, p95 {percentil(iv, 95):.1f}); "
              f"nube {sorted(map(str, nube))}, usb {sorted(map(str, usb))}",
              f"mediana <= 62 ms, p95 <= 65 ms, hms >= {0.9 * REF_HMS:.1f}/s", "APROBADA" if ok else "FALLIDA",
              "" if nube == {"operando"} else "AVISO: la nube no estuvo 'operando' todo el tiempo")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
