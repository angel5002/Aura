"""D3 - Duracion >= 2 h sin PC por USB (placa con cargador), todas las vias activas.

Graba la via local y cada 60 s consulta /sensores/<sensor>/latido con TU cuenta.
Criterios:
  - 0 reinicios (encendido_s nunca retrocede, ni en la telemetria local ni en el latido de la nube);
  - heap minimo historico >= 40 KB (40960 B);
  - al menos 1 renovacion del token (renov >= 1) con la prueba durando mas de 60 min;
  - /sensores sin cortes: ningun hueco > 150 s entre latidos distintos (latido cada 60 s + muestreo de 60 s).
"""

import argparse
import sys
import time

from comun import Coleccion, ip_placa, recibir_en_hilo, reinicios
from registrar import registrar

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
from fb_rest import Sesion, cargar_config, peticion  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ip")
    ap.add_argument("--horas", type=float, default=2.1)
    ap.add_argument("--sensor", default="hab1")
    a = ap.parse_args()
    cfg = cargar_config()
    ses = Sesion(cfg, etiqueta="usuario")
    ip = ip_placa(a.ip)
    col = Coleccion()
    dur = a.horas * 3600
    h, res = recibir_en_hilo(ip, "D3", dur, col)
    latidos = []       # (t_pc, latido)
    fin = time.time() + dur
    while time.time() < fin:
        try:
            c, lat = peticion(cfg, "GET", f"/sensores/{a.sensor}/latido", ses)
            if c == 200 and isinstance(lat, dict):
                latidos.append((time.time(), lat))
        except Exception as e:  # red de la PC caida un momento: se registra y se sigue
            print("consulta fallida:", e)
        time.sleep(60)
    h.join()

    distintos = []
    for t, l in latidos:
        if not distintos or l.get("t") != distintos[-1][1].get("t"):
            distintos.append((t, l))
    huecos = [(b[1]["t"] - a_[1]["t"]) / 1000 for a_, b in zip(distintos, distintos[1:])]
    max_hueco = max(huecos) if huecos else float("inf")
    ups = [l.get("up", 0) for _, l in distintos]
    rein_nube = sum(1 for x, y in zip(ups, ups[1:]) if y < x)
    rein_local = reinicios(col.telemetria)
    heap_min = min([t.get("heap_minimo", 1 << 30) for _, t in col.telemetria] +
                   [l.get("heap_min", 1 << 30) for _, l in distintos])
    renov = max([l.get("renov", 0) for _, l in distintos] + [t.get("nube_renovaciones", 0) for _, t in col.telemetria])
    duracion_h = (latidos[-1][0] - latidos[0][0]) / 3600 if len(latidos) > 1 else 0

    ok_rein = rein_nube == 0 and rein_local == 0
    ok_heap = heap_min >= 40960
    ok_renov = renov >= 1 and duracion_h * 60 > 60
    ok_cont = max_hueco <= 150
    registrar("D3a reinicios", f"nube {rein_nube}, local {rein_local}", "0", "APROBADA" if ok_rein else "FALLIDA")
    registrar("D3b heap minimo", f"{heap_min} B", ">= 40960 B", "APROBADA" if ok_heap else "FALLIDA")
    registrar("D3c renovacion de token", f"{renov} renovaciones en {duracion_h:.2f} h", ">= 1 tras > 60 min",
              "APROBADA" if ok_renov else "FALLIDA")
    registrar("D3d /sensores sin cortes", f"hueco maximo entre latidos {max_hueco:.0f} s ({len(distintos)} latidos)",
              "<= 150 s", "APROBADA" if ok_cont else "FALLIDA",
              f"via local: perdida {res.get('perdida_pct', float('nan')):.2f} %")
    return 0 if (ok_rein and ok_heap and ok_renov and ok_cont) else 1


if __name__ == "__main__":
    sys.exit(main())
