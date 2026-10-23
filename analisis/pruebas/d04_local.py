"""D4 - Via local 30 min en la red domestica: perdida < 1 % segun el numero de secuencia."""

import argparse
import sys

from comun import Coleccion, ip_placa, recibir_en_hilo
from registrar import registrar


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ip")
    ap.add_argument("--minutos", type=float, default=30)
    a = ap.parse_args()
    ip = ip_placa(a.ip)
    h, r = recibir_en_hilo(ip, "D4", a.minutos * 60, Coleccion())
    h.join()
    ok = r.get("esperados", 0) > 0 and r["perdida_pct"] < 1.0
    registrar("D4 via local 30 min", f"perdida {r['perdida_pct']:.3f} % ({r['perdidos']}/{r['esperados']}), "
              f"desorden {r['desordenados']}, dup {r['duplicados']}, {r['tasa_total_por_s']:.1f} dgr/s, epocas {r['epocas']}",
              "< 1 %", "APROBADA" if ok else "FALLIDA", r["archivo"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
