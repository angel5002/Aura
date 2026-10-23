"""D1 - Arranque y credenciales (firmware >= 0.1.2).

1) Captura USB 180 s reiniciando la placa con AURA REBOOT (arranque completo) -> datos\\crudos\\D1_usb.csv.
   Registra la memoria libre y la minima historica en cada momento clave ({"type":"memoria"}): IP obtenida,
   detector creado/estable, primer inicio de sesion en Firebase y primera escritura. Regla de parada
   (23/10/2026): si la minima baja de 30 KB, D1c queda FALLIDA y no se sigue con las demas pruebas.
2) Captura por la via local 120 s -> datos\\crudos\\D1_local.csv
3) Pide SIN ECO cada secreto (Enter = omitir) y lo busca en ambas capturas: texto, hexadecimal y base64.
   Solo informa cuantas coincidencias hay.
Criterio: conecta (IP, mensajes HMS y telemetria) y 0 secretos en los registros.
"""

import argparse
import base64
import csv
import getpass
import json
import sys
import time

from comun import DIR_CRUDOS, Coleccion, ip_placa, recibir_en_hilo
from registrar import registrar

sys.path.insert(0, str(DIR_CRUDOS.parents[1] / "analisis"))
from capturar import LectorSerie, nuevo_destino  # noqa: E402

SECRETOS = ["wifi1_ssid", "wifi1_pass", "wifi2_ssid", "wifi2_pass", "fb_email", "fb_pass", "local_key"]
MINIMA_PARADA = 30 * 1024      # regla de parada del 23/10/2026


def capturar_usb(puerto: str, segundos: float) -> tuple:
    destino = nuevo_destino("D1_usb")
    lector = LectorSerie(puerto, 115200)
    n = n_hms = 0
    tipos = set()
    memoria = []
    with open(destino, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_pc_unix", "linea"])
        lector.reiniciar_por_consola()
        fin = time.time() + segundos
        while time.time() < fin:
            b = lector.leer_linea()
            for t_ev, txt in lector.eventos:
                w.writerow([f"{t_ev:.6f}", "#AURA " + txt])
            lector.eventos.clear()
            if b is None:
                continue
            linea = b.decode("utf-8", errors="replace").rstrip("\r\n")
            w.writerow([f"{time.time():.6f}", linea])
            n += 1
            if linea.startswith("HMS:"):
                n_hms += 1
                try:
                    m = json.loads(linea[4:])
                except json.JSONDecodeError:
                    continue
                tipos.add(m.get("type"))
                if m.get("type") == "memoria":
                    memoria.append(m)
                    print(f"   memoria [{m.get('momento')}]: libre {m.get('heap_libre')} B, "
                          f"minima {m.get('heap_minimo')} B (encendido {m.get('encendido_ms')} ms)")
    lector.cerrar()
    return destino, n, n_hms, tipos, memoria


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--puerto", required=True)
    ap.add_argument("--ip")
    a = ap.parse_args()

    print("1/3 Captura USB 180 s con reinicio (AURA REBOOT)...")
    usb, n, n_hms, tipos, memoria = capturar_usb(a.puerto, 180)
    print(f"   {n} lineas, {n_hms} HMS, tipos: {sorted(t for t in tipos if t)}")
    momentos = {m.get("momento"): m for m in memoria}
    requeridos = ["ip", "detector_creado", "nube_sesion"]
    minima = min((m.get("heap_minimo", 0) for m in memoria), default=None)
    mem_ok = all(k in momentos for k in requeridos) and minima is not None and minima >= MINIMA_PARADA
    registrar("D1c memoria en momentos clave", "; ".join(
              f"{k}: libre {m.get('heap_libre')} / min {m.get('heap_minimo')} B" for k, m in momentos.items())
              or "sin mensajes de memoria", f"momentos ip, detector y nube_sesion presentes; minima >= {MINIMA_PARADA} B",
              "APROBADA" if mem_ok else "FALLIDA",
              "" if mem_ok else "REGLA DE PARADA: no seguir con las demas pruebas sin decidir el ajuste de memoria")
    print("2/3 Captura por la via local 120 s...")
    ip = ip_placa(a.ip)
    col = Coleccion()
    h, res = recibir_en_hilo(ip, "D1", 120, col)
    h.join()
    local = DIR_CRUDOS / "D1_local.csv"
    conecto = bool(ip) and n_hms > 0 and "telemetria" in tipos and len(col.telemetria) > 0
    registrar("D1a arranque y conexion", f"IP {ip}; HMS USB {n_hms}; telemetria USB {'si' if 'telemetria' in tipos else 'no'}; "
              f"telemetria local {len(col.telemetria)}", "conecta, HMS y telemetria por USB y local",
              "APROBADA" if conecto else "FALLIDA")

    print("3/3 Busqueda de secretos. Escribe cada valor (no se muestra); Enter para omitir.")
    textos = [usb.read_bytes(), local.read_bytes()]
    total = 0
    buscados = 0
    for clave in SECRETOS:
        v = getpass.getpass(f"   {clave}: ").encode("utf-8")
        if not v:
            continue
        buscados += 1
        formas = [v, v.hex().encode(), v.hex().upper().encode(), base64.b64encode(v)]
        total += sum(t.count(f) for t in textos for f in formas)
        v = None
    registrar("D1b secretos en registros (USB y local)", f"{total} coincidencias ({buscados} secretos buscados)",
              "0 coincidencias", "APROBADA" if total == 0 and buscados > 0 else ("NO EJECUTADA" if buscados == 0 else "FALLIDA"),
              f"{usb.name}, {local.name}")
    return 0 if conecto and total == 0 and mem_ok else 1


if __name__ == "__main__":
    sys.exit(main())
