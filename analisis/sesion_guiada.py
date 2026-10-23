"""Sesión guiada por tramos para evaluar wifi_sensing (p. ej. 1 min vacía, 1 min caminando, 1 min sentada quieta).

Hace todo en un solo proceso, porque el COM solo lo puede abrir un programa:
  1. Abre el puerto de la placa B y guarda TODAS las líneas en datos/crudos/<id>.csv (mismo formato que
     capturar.py: t_pc_unix, linea).
  2. (Opcional, --recalibrar) envía "HMSCMD RESET_BASELINE" y espera el ack de la placa.
  3. Espera a que el canal AP llegue a init_stage_name == "STABLE" (la habitación debe estar vacía y quieta).
     (Opcional, --entrenar SEG) entrena la presencia con TRAIN_START/TRAIN_STOP; sin esto la presencia
     queda siempre en falso, porque esp-radar solo calcula "wander" con muestras de entrenamiento.
  4. Recorre los tramos; en cada cambio imprime un aviso y emite pitidos (1 = vacía, 2 = caminando,
     3 = sentada quieta; uno largo = fin).
  5. Escribe datos/crudos/<id>_etiquetas.csv (t_rel_s,condicion; segundos desde la primera línea del archivo,
     el formato que lee evaluar_deteccion.py) y agrega la sesión a registro_sesiones.csv con condicion_real=tramos.

Formatos usados (verificados en web_serial_monitor.c): HMS:{"type":"sample","peer":"AP",...,"init_stage_name":..}
y HMS:{"type":"ack","cmd":"RESET_BASELINE","ok":true|false,...}.

Ejemplo:
    python C:\\aura\\analisis\\sesion_guiada.py --puerto COM5 --id-sesion S002 --recalibrar ^
        --tramos vacia=60 caminando=60 sentada_quieta=60 --distancia-persona 1.5
"""

import argparse
import csv
import json
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import serial

from capturar import DIR_CRUDOS, MARCA_AURA, MARCA_HMS, LectorSerie, nuevo_destino
from registro import agregar_sesion

CONDICIONES = ("vacia", "caminando", "sentada_quieta")
PITIDOS = {"vacia": 1, "caminando": 2, "sentada_quieta": 3}


def pitar(veces: int, largo: bool = False):
    def _sonar():
        try:
            import winsound
            for _ in range(veces):
                winsound.Beep(1000, 900 if largo else 250)
                time.sleep(0.15)
        except (ImportError, RuntimeError):
            print("\a" * veces, end="", flush=True)
    threading.Thread(target=_sonar, daemon=True).start()


def leer_hms(linea: str):
    if not linea.startswith(MARCA_HMS):
        return None
    try:
        return json.loads(linea[len(MARCA_HMS):])
    except json.JSONDecodeError:
        return None


def parsear_tramos(textos: list[str]) -> list[tuple[str, float]]:
    tramos = []
    for t in textos:
        cond, _, seg = t.partition("=")
        if cond not in CONDICIONES or not seg:
            raise ValueError(f"tramo inválido '{t}'; use condicion=segundos con condicion en {CONDICIONES}")
        tramos.append((cond, float(seg)))
    return tramos


def main() -> int:
    ap = argparse.ArgumentParser(description="Sesión guiada por tramos con wifi_sensing.")
    ap.add_argument("--puerto", required=True)
    ap.add_argument("--id-sesion", required=True)
    ap.add_argument("--tramos", nargs="+", default=["vacia=60", "caminando=60", "sentada_quieta=60"],
                    help="condicion=segundos, en orden (defecto: vacia=60 caminando=60 sentada_quieta=60)")
    ap.add_argument("--peer", default="AP")
    ap.add_argument("--recalibrar", action="store_true", help="Envía HMSCMD RESET_BASELINE antes de empezar")
    ap.add_argument("--max-espera-estable", type=float, default=300, help="Segundos máximos esperando STABLE")
    ap.add_argument("--sin-esperar-estable", action="store_true", help="Empieza los tramos sin esperar STABLE")
    ap.add_argument("--preparacion", type=float, default=5, help="Segundos entre STABLE y el primer tramo")
    ap.add_argument("--entrenar", type=float, default=0,
                    help="Segundos de entrenamiento de presencia (TRAIN_START/TRAIN_STOP) tras STABLE, con la "
                         "habitación vacía. 0 = sin entrenar (la presencia quedará siempre en falso)")
    # Campos del registro (opcionales)
    ap.add_argument("--placa-tx", default="hotspot")
    ap.add_argument("--placa-rx", default="B")
    ap.add_argument("--banda", default="")
    ap.add_argument("--canal", default="")
    ap.add_argument("--distancia-tx-rx", default="")
    ap.add_argument("--posicion-persona", default="")
    ap.add_argument("--distancia-persona", default="")
    ap.add_argument("--personas", default="1")
    ap.add_argument("--observaciones", default="")
    args = ap.parse_args()

    try:
        tramos = parsear_tramos(args.tramos)
        destino = nuevo_destino(args.id_sesion)
        lector = LectorSerie(args.puerto, 921600)
    except (ValueError, FileExistsError) as e:
        print(f"ERROR: {e}")
        return 1
    except serial.SerialException as e:
        print(f"ERROR al abrir {args.puerto}: {e}  (¿puente.py, capturar.py o el monitor lo tienen abierto?)")
        return 1

    inicio_local = datetime.now()
    t0 = None                      # hora de la primera fila del archivo (origen de t_rel_s)
    etiquetas: list[tuple[float, str]] = []
    etapa_actual, t_estable = None, None
    acks: dict[str, dict] = {}     # último ack recibido por comando
    n_hms = 0
    interrumpida = False

    with open(destino, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_pc_unix", "linea"])

        def anotar(texto: str, t: float | None = None):
            nonlocal t0
            t = time.time() if t is None else t
            t0 = t if t0 is None else t0
            w.writerow([f"{t:.6f}", MARCA_AURA + texto])

        def bombear(hasta: float, parar=lambda: False):
            """Lee y guarda líneas hasta 'hasta' (unix) o hasta que parar() sea verdadero."""
            nonlocal t0, etapa_actual, t_estable, n_hms
            while time.time() < hasta and not parar():
                bruto = lector.leer_linea()
                for t_ev, texto in lector.eventos:
                    anotar(texto, t_ev)
                    print(f"  [{texto}]")
                lector.eventos.clear()
                if bruto is None:
                    continue
                t = time.time()
                t0 = t if t0 is None else t0
                linea = bruto.decode("utf-8", errors="replace").rstrip("\r\n")
                w.writerow([f"{t:.6f}", linea])
                msg = leer_hms(linea)
                if msg is None:
                    continue
                n_hms += 1
                if msg.get("type") == "ack":
                    acks[msg.get("cmd")] = msg
                elif msg.get("type") == "sample" and msg.get("peer") == args.peer:
                    etapa = msg.get("init_stage_name")
                    if etapa != etapa_actual:
                        print(f"  {t - t0:7.1f} s  etapa de calibración: {etapa}")
                        etapa_actual = etapa
                        if etapa == "STABLE" and t_estable is None:
                            t_estable = t

        def comando(texto: str, clave_ack: str, espera: float = 3.0):
            """Envía 'HMSCMD <texto>' y espera el ack de 'clave_ack'. Devuelve el ack o None."""
            acks.pop(clave_ack, None)
            ok = lector.escribir(f"HMSCMD {texto}\n".encode())
            anotar(f"enviado HMSCMD {texto}" if ok else f"no se pudo enviar HMSCMD {texto}")
            bombear(time.time() + espera, parar=lambda: clave_ack in acks)
            a = acks.get(clave_ack)
            if a is None:
                print(f"Aviso: la placa no confirmó {texto} en {espera:.0f} s.")
            else:
                print(f"{texto}: ok={a.get('ok')} detalle={a.get('detail')}")
                anotar(f"ack {clave_ack} ok={a.get('ok')} detalle={a.get('detail')}")
            return a

        try:
            print(f"Capturando {args.puerto} -> {destino}")
            anotar("inicio de sesion guiada")
            if args.recalibrar:
                a = comando("RESET_BASELINE", "RESET_BASELINE")
                if a is not None:
                    t_estable, etapa_actual = None, None

            if not args.sin_esperar_estable:
                print(f"Esperando STABLE en {args.peer} (máx. {args.max_espera_estable:.0f} s). "
                      "Mantén la habitación VACÍA y quieta.")
                t_lim = time.time() + args.max_espera_estable
                bombear(t_lim, parar=lambda: t_estable is not None)
                if t_estable is None:
                    print("ERROR: no se llegó a STABLE. Se guarda lo capturado y no se inician los tramos.")
                    anotar("timeout esperando STABLE")
                    interrumpida = True
                else:
                    anotar("STABLE alcanzado", t_estable)

            # Entrenamiento de presencia: sin él, esp-radar entrega waveform_wander = 0 y la presencia
            # nunca se activa (csi_detection_compute_wander en esp_radar.c). Los umbrales viven en RAM.
            if not interrumpida and args.entrenar > 0:
                print(f"Entrenando presencia {args.entrenar:.0f} s: habitación VACÍA y quieta.")
                if comando(f"TRAIN_START {args.peer}", "TRAIN_START") is None:
                    interrumpida = True
                else:
                    bombear(time.time() + args.entrenar)
                    a = comando(f"TRAIN_STOP {args.peer}", "TRAIN_STOP")
                    if a is None or not a.get("ok"):
                        print("ERROR: el entrenamiento no produjo umbrales; no se inician los tramos.")
                        interrumpida = True

            if not interrumpida:
                bombear(time.time() + args.preparacion)
                for i, (cond, seg) in enumerate(tramos, 1):
                    t_ini = time.time()
                    etiquetas.append((t_ini, cond))
                    anotar(f"tramo {i}/{len(tramos)} {cond} inicio", t_ini)
                    pitar(PITIDOS[cond])
                    print(f"\n>>> TRAMO {i}/{len(tramos)}: {cond.upper()} durante {seg:.0f} s")
                    bombear(t_ini + seg)
                anotar("fin de tramos")
                pitar(1, largo=True)
                print("\n>>> FIN")
        except KeyboardInterrupt:
            interrumpida = True
            anotar("sesion interrumpida por el usuario")
            print("\nInterrumpida por el usuario. Se guarda lo capturado.")
        finally:
            lector.cerrar()

    # Etiquetas en segundos desde la primera fila del archivo (lo que espera evaluar_deteccion.py).
    if etiquetas:
        ruta_et = DIR_CRUDOS / f"{args.id_sesion}_etiquetas.csv"
        with open(ruta_et, "w", newline="", encoding="utf-8") as f:
            we = csv.writer(f, lineterminator="\n")
            we.writerow(["t_rel_s", "condicion"])
            for t, cond in etiquetas:
                we.writerow([f"{t - t0:.3f}", cond])
        print(f"Etiquetas: {ruta_et}")

    fin_local = datetime.now()
    resumen_tramos = " ".join(f"{c}={s:.0f}s" for c, s in tramos[:len(etiquetas)])
    obs = [args.observaciones] if args.observaciones else []
    obs.append(f"tramos: {resumen_tramos or 'ninguno'}")
    if t_estable is not None:
        obs.append(f"STABLE a los {t_estable - t0:.1f} s")
    if interrumpida:
        obs.append("INTERRUMPIDA")
    try:
        agregar_sesion({
            "id_sesion": args.id_sesion,
            "fecha": inicio_local.strftime("%Y-%m-%d"),
            "hora_inicio": inicio_local.strftime("%H:%M:%S"),
            "hora_fin": fin_local.strftime("%H:%M:%S"),
            "placa_tx": args.placa_tx, "placa_rx": args.placa_rx,
            "banda": args.banda, "canal": args.canal,
            "distancia_tx_rx_m": args.distancia_tx_rx,
            "posicion_persona": args.posicion_persona, "distancia_persona_m": args.distancia_persona,
            "postura": "segun_tramo", "referencia": "ninguna",
            "personas_en_sala": args.personas,
            "archivo_datos": destino.name,
            "observaciones": "; ".join(obs),
            "condicion_real": "tramos" if etiquetas else "",
        })
        print(f"Registrada en registro_sesiones.csv como {args.id_sesion}")
    except ValueError as e:
        print(f"Aviso: no se pudo registrar la sesión: {e}")

    print(f"Líneas HMS recibidas: {n_hms}  | reconexiones del puerto: {lector.reconexiones}")
    if etiquetas:
        print(f"Para evaluar:  python C:\\aura\\analisis\\evaluar_deteccion.py --sesiones {args.id_sesion}")
    return 1 if interrumpida else 0


if __name__ == "__main__":
    sys.exit(main())
