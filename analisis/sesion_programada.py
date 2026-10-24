"""Sesion etiquetada con HORAS ABSOLUTAS, para guiar a la persona a distancia (por chat, sin ver la PC ni oir pitidos).

Un solo proceso (el COM solo lo puede abrir un programa):
  - captura el USB en datos/crudos/<id>.csv (formato de capturar.py) y envia los comandos por la consola USB
    ("HMSCMD RESET_BASELINE", "HMSCMD TRAIN_START AP", "HMSCMD TRAIN_STOP AP");
  - recibe a la vez la via local (CSI crudo) por IP directa, sin descubrimiento ni bind: <id>_local.csv;
  - escribe <id>_etiquetas.csv (t_rel_s desde la primera linea de <id>.csv; 'excluir' = transiciones) y
    agrega la sesion a registro_sesiones.csv.

Linea de tiempo (S0 = inicio, la persona ya esta FUERA de la sala):
  S0        RESET_BASELINE; se espera init_stage_name == STABLE en el canal AP (hasta S0+40)
  S0+40     TRAIN_START AP (solo si hubo STABLE)       S0+40+E  TRAIN_STOP AP   (E = --entrenar, 20 s)
  S0+75     vacia (60 s)                               S0+135   excluir (la persona vuelve)
  S0+150    caminando (60 s)                           S0+210   excluir (se sienta)
  S0+220    sentada_quieta (60 s)                      S0+280   fin
"""

import argparse
import csv
import json

import sys
import threading
import time
from datetime import datetime

from capturar import DIR_CRUDOS, MARCA_AURA, MARCA_HMS, LectorSerie, nuevo_destino
from registro import agregar_sesion
import receptor_local as rl

PEER = "AP"


def hora(t: float) -> str:
    return datetime.fromtimestamp(t).strftime("%H:%M:%S")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--puerto", default="auto", help="COM de la placa o auto (por defecto: detecta la placa por VID 303A)")
    ap.add_argument("--ip", required=True)
    ap.add_argument("--id-sesion", required=True)
    ap.add_argument("--inicio", required=True,
                    help="HH:MM:SS de S0 (hora de la PC). REGLA 24/10/2026: solo despues de que la persona responda "
                         "'listo' al plan, y al menos 120 s despues de ese 'listo'")
    ap.add_argument("--entrenar", type=float, default=20)
    ap.add_argument("--registro", nargs="*", default=[], help="columna=valor para registro_sesiones.csv")
    a = ap.parse_args()

    destino = nuevo_destino(a.id_sesion)
    destino_local = DIR_CRUDOS / f"{a.id_sesion}_local.csv"
    if destino_local.exists():
        print(f"ERROR: {destino_local} ya existe")
        return 1
    ahora = time.time()
    hh, mm, ss = (int(x) for x in a.inicio.split(":"))
    s0 = datetime.now().replace(hour=hh, minute=mm, second=ss, microsecond=0).timestamp()
    if s0 - ahora < 120:
        print(f"ERROR: S0 {a.inicio} esta a {s0 - ahora:.0f} s; la regla exige al menos 120 s tras el 'listo'.")
        return 1
    E = a.entrenar
    plan = [(s0, "excluir"), (s0 + 75, "vacia"), (s0 + 135, "excluir"), (s0 + 150, "caminando"),
            (s0 + 210, "excluir"), (s0 + 220, "sentada_quieta"), (s0 + 280, "excluir")]
    fin = s0 + 285
    print(f"PLAN (hora de la PC) S0={hora(s0)}: fuera antes de {hora(s0)}; RESET {hora(s0)}; "
          f"TRAIN {hora(s0 + 40)}-{hora(s0 + 40 + E)}; vacia {hora(s0 + 75)}-{hora(s0 + 135)}; "
          f"volver {hora(s0 + 150)}; caminando {hora(s0 + 150)}-{hora(s0 + 210)}; sentarse {hora(s0 + 210)}; "
          f"sentada {hora(s0 + 220)}-{hora(s0 + 280)}; fin {hora(fin)}", flush=True)

    res_local = {}
    hilo = threading.Thread(target=lambda: res_local.update(
        rl.recibir(a.ip, rl.PUERTO_DATOS, destino_local, fin - time.time() + 5, nombre=a.id_sesion,
                   silencioso=True, bind_explicito=False)), daemon=True)
    hilo.start()

    lector = LectorSerie(a.puerto, 115200)
    t_primera = None
    etiquetas = [(time.time(), "excluir")]          # desde el arranque hasta S0: preparacion
    eventos = {}
    estado = "espera_s0"
    t_stable = None
    with open(destino, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_pc_unix", "linea"])

        def marca(texto):
            t = time.time()
            w.writerow([f"{t:.6f}", MARCA_AURA + texto])
            print(f"{hora(t)} {texto}", flush=True)

        i_plan = 0
        while time.time() < fin:
            t = time.time()
            while i_plan < len(plan) and t >= plan[i_plan][0]:
                etiquetas.append((plan[i_plan][0], plan[i_plan][1]))
                marca(f"tramo {plan[i_plan][1]}")
                i_plan += 1
            if estado == "espera_s0" and t >= s0:
                lector.escribir(b"HMSCMD RESET_BASELINE\n")
                eventos["reset"] = t
                marca("RESET_BASELINE enviado")
                estado = "espera_stable"
            elif estado == "espera_stable" and t >= s0 + 40:
                if t_stable:
                    lector.escribir(f"HMSCMD TRAIN_START {PEER}\n".encode())
                    eventos["train_start"] = t
                    marca("TRAIN_START enviado")
                    estado = "entrenando"
                else:
                    marca("SIN STABLE a los 40 s: NO se entrena (presencia no evaluable)")
                    estado = "tramos"
            elif estado == "entrenando" and t >= s0 + 40 + E:
                lector.escribir(f"HMSCMD TRAIN_STOP {PEER}\n".encode())
                eventos["train_stop"] = t
                marca("TRAIN_STOP enviado")
                estado = "tramos"
            for t_ev, txt in lector.eventos:
                w.writerow([f"{t_ev:.6f}", MARCA_AURA + txt])
            lector.eventos.clear()
            b = lector.leer_linea()
            if b is None:
                continue
            t = time.time()
            linea = b.decode("utf-8", errors="replace").rstrip("\r\n")
            if t_primera is None:
                t_primera = t
            w.writerow([f"{t:.6f}", linea])
            if not linea.startswith(MARCA_HMS):
                continue
            try:
                m = json.loads(linea[len(MARCA_HMS):])
            except json.JSONDecodeError:
                continue
            if m.get("type") == "ack":
                marca(f"ack {m.get('cmd')} ok={m.get('ok')} {m.get('detail')}")
            elif (m.get("type") == "sample" and m.get("peer") == PEER and estado == "espera_stable"
                  and t_stable is None and m.get("init_stage_name") == "STABLE" and t > s0 + 1):
                t_stable = t
                marca(f"STABLE a los {t - s0:.1f} s del RESET")
            elif (m.get("type") == "sample" and m.get("peer") == PEER and estado == "tramos" and "valid" not in eventos
                  and "train_stop" in eventos and t > eventos["train_stop"] + 3):
                eventos["valid"] = bool(m.get("train_thresholds_valid"))
                marca(f"train_thresholds_valid={eventos['valid']}")
    lector.cerrar()
    hilo.join(timeout=15)

    with open(DIR_CRUDOS / f"{a.id_sesion}_etiquetas.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_rel_s", "condicion"])
        for t, c in etiquetas:
            w.writerow([f"{max(0.0, t - t_primera):.3f}", c])
    fila = {"id_sesion": a.id_sesion, "fecha": datetime.fromtimestamp(s0).strftime("%Y-%m-%d"),
            "hora_inicio": hora(s0), "hora_fin": hora(fin), "placa_rx": "B", "personas_en_sala": "1",
            "archivo_datos": f"{destino.name}; {destino_local.name}", "condicion_real": "tramos"}
    for kv in a.registro:
        k, _, v = kv.partition("=")
        fila[k] = v
    agregar_sesion(fila)
    print(f"FIN {hora(time.time())}: USB {destino.name}; local {destino_local.name} "
          f"(perdida {res_local.get('perdida_pct', float('nan')):.2f} %, csi {res_local.get('por_tipo', {}).get('csi')}); "
          f"STABLE {'si' if t_stable else 'NO'}; entrenamiento valido {eventos.get('valid')}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
