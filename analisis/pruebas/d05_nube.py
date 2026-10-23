"""D5 - Via nube: estado y latido en /sensores/<sensor>, y 10 comandos con su confirmacion.

Escribe 10 veces /comandos/<sensor>/<push> = {"cmd": "GET_CFG AP", "t": hora del servidor} con TU cuenta y
mide el tiempo hasta que /sensores/<sensor>/comando muestra ese id. Borra cada comando al terminar.
Criterio: estado y latido presentes y recientes; las 10 confirmaciones en <= intervalo de consulta + 3 s.
"""

import argparse
import sys
import time
from pathlib import Path

from registrar import registrar

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fb_rest import Sesion, cargar_config, peticion  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sensor", default="hab1")
    ap.add_argument("--consulta-s", type=float, default=5, help="CONFIG_AURA_NUBE_CONSULTA_S")
    ap.add_argument("--repeticiones", type=int, default=10)
    a = ap.parse_args()
    cfg = cargar_config()
    ses = Sesion(cfg, etiqueta="usuario")
    limite = a.consulta_s + 3

    c1, est = peticion(cfg, "GET", f"/sensores/{a.sensor}/estado", ses)
    c2, lat = peticion(cfg, "GET", f"/sensores/{a.sensor}/latido", ses)
    edad = (time.time() * 1000 - lat.get("t", 0)) / 1000 if isinstance(lat, dict) else float("inf")
    ok_estado = c1 == 200 and isinstance(est, dict) and "estado" in est and c2 == 200 and edad < 150
    registrar("D5a estado y latido en la nube", f"estado={est.get('estado') if isinstance(est, dict) else est}, "
              f"latido hace {edad:.0f} s", "presentes; latido < 150 s", "APROBADA" if ok_estado else "FALLIDA")

    # D5c: presencia explicita. Nunca "vacia" sin entrenamiento; VACIA/PRESENCIA_QUIETA solo entrenada.
    est = est if isinstance(est, dict) else {}
    pres, entr, e = est.get("presencia"), est.get("entrenada"), est.get("estado")
    ok_pres = pres in ("no_disponible", "vacia", "presente") and (entr is True or pres == "no_disponible") \
        and (e not in ("VACIA", "PRESENCIA_QUIETA") or entr is True)
    registrar("D5c estado de presencia", f"presencia={pres}, entrenada={entr}, estado={e}",
              "valor permitido; sin entrenar => no_disponible", "APROBADA" if ok_pres else "FALLIDA",
              "repetir tras TRAIN_START/TRAIN_STOP para ver 'vacia'/'presente'" if pres == "no_disponible" else "")
    ok_estado = ok_estado and ok_pres

    tiempos = []
    for i in range(a.repeticiones):
        c, r = peticion(cfg, "POST", f"/comandos/{a.sensor}", ses, cuerpo={"cmd": "GET_CFG AP", "t": {".sv": "timestamp"}})
        if c != 200:
            print(f"  {i + 1}: no se pudo escribir el comando (HTTP {c}): {r}")
            tiempos.append(float("inf"))
            continue
        cid = r["name"]
        t0 = time.time()
        conf = float("inf")
        while time.time() - t0 < limite + 10:
            _, ack = peticion(cfg, "GET", f"/sensores/{a.sensor}/comando", ses)
            if isinstance(ack, dict) and ack.get("id") == cid:
                conf = time.time() - t0
                break
            time.sleep(0.25)
        tiempos.append(conf)
        print(f"  {i + 1}: {conf:.2f} s" + (f" ok={ack.get('ok')} origen={ack.get('origen')}" if conf < 1e9 else " SIN CONFIRMACION"))
        peticion(cfg, "DELETE", f"/comandos/{a.sensor}/{cid}", ses)
        time.sleep(1)
    dentro = sum(1 for t in tiempos if t <= limite)
    ok = dentro == a.repeticiones
    finitos = [t for t in tiempos if t < 1e9]
    registrar("D5b comandos por la nube", f"{dentro}/{a.repeticiones} dentro de {limite:.0f} s; "
              f"max {max(finitos) if finitos else float('nan'):.2f} s, media {sum(finitos) / len(finitos) if finitos else float('nan'):.2f} s",
              f"10/10 en <= {limite:.0f} s", "APROBADA" if ok else "FALLIDA")
    return 0 if ok and ok_estado else 1


if __name__ == "__main__":
    sys.exit(main())
