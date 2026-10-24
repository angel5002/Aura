"""Verifica en un solo paso que el kit de captura de AURA funciona en esta PC con Windows.

    .\\.venv\\Scripts\\python.exe scripts\\verificar_kit.py              (pregunta antes de reiniciar la placa)
    .\\.venv\\Scripts\\python.exe scripts\\verificar_kit.py --reiniciar  (reinicia la placa sin preguntar si hace falta la IP)

Revisa: Windows y Python (3.12, 64 bits); dependencias fijadas en requirements.txt; Tk (ventana del visor); la placa
por USB (VID 303A); recepcion USB 10 s (version del firmware, red, muestras/s); la IP de la placa (solo se informa al
conectar: si no aparece, se ofrece reiniciar la placa con AURA REBOOT); si la PC esta en la misma red; y recepcion por
la red 10 s (via local con --ip y sin bind, como el visor). No cambia la configuracion de la placa ni graba nada en
ella; no guarda datos de sesion (la prueba de red usa un archivo temporal que se borra). Al final imprime un informe
con lo que funciona, lo que no y la solucion sugerida, y lo guarda en verificacion_<fecha>.txt (raiz del kit).
"""

import argparse
import importlib.metadata as md
import json
import os
import platform
import re
import socket
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if not (RAIZ / "requirements.txt").exists():        # ejecutado desde C:\aura\analisis (repo), no desde el kit
    RAIZ = RAIZ / "kit_captura"
REQ = RAIZ / "requirements.txt"
PY_SOPORTADO = (3, 12)
RX_IP = re.compile(r"sta ip: (\d+\.\d+\.\d+\.\d+)")

informe = []        # (prueba, estado, detalle, solucion)


def anotar(prueba, estado, detalle, solucion=""):
    informe.append((prueba, estado, detalle, solucion))
    print(f"[{estado:^10}] {prueba}: {detalle}" + (f"\n             -> {solucion}" if solucion and estado != "OK" else ""),
          flush=True)


def revisar_python() -> bool:
    v = sys.version_info
    bits = "64" if sys.maxsize > 2 ** 32 else "32"
    texto = f"Python {v.major}.{v.minor}.{v.micro} {bits} bits en {platform.system()} {platform.release()}"
    if sys.platform != "win32":
        anotar("Sistema", "FALLA", texto, "El kit solo esta preparado para Windows.")
        return False
    if (v.major, v.minor) != PY_SOPORTADO or bits != "64":
        anotar("Python", "FALLA", texto, "Instala Python 3.12 de 64 bits (python.org, 'Add python.exe to PATH') y "
               "vuelve a crear .venv con: py -3.12 -m venv .venv")
        return False
    anotar("Python", "OK", texto)
    return True


def revisar_dependencias() -> bool:
    pedidas = {}
    for linea in REQ.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\s*([A-Za-z0-9_.\-]+)==([^\s#]+)", linea)
        if m:
            pedidas[m.group(1)] = m.group(2)
    faltan, distintas = [], []
    for nombre, ver in pedidas.items():
        try:
            inst = md.version(nombre)
        except md.PackageNotFoundError:
            faltan.append(nombre)
            continue
        if inst != ver:
            distintas.append(f"{nombre} {inst} (se probo {ver})")
    sol = r"Ejecuta: .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
    if faltan:
        anotar("Dependencias", "FALLA", "faltan: " + ", ".join(faltan), sol)
        return False
    if distintas:
        anotar("Dependencias", "AVISO", "versiones distintas: " + "; ".join(distintas), sol + " (instala las probadas)")
    else:
        anotar("Dependencias", "OK", f"{len(pedidas)} paquetes con las versiones probadas")
    try:
        import tkinter
        tkinter.Tcl()                   # carga Tcl/Tk sin abrir ventana
        anotar("Ventana del visor (Tk)", "OK", f"Tk {tkinter.TkVersion} disponible")
    except Exception:  # noqa: BLE001 - ImportError (sin tkinter) o TclError (falta la biblioteca Tcl/Tk)
        anotar("Ventana del visor (Tk)", "FALLA", "falta tkinter: el visor en vivo no puede abrir su ventana",
               "Reinstala Python 3.12 marcando 'tcl/tk and IDLE' (Modify en el instalador)")
    return True


def probar_usb(puerto_pedido: str, segundos: float, reiniciar: str) -> dict:
    """Devuelve {'puerto','ip','red','ver'} con lo que se pudo leer por USB."""
    import capturar
    out = {}
    try:
        puerto = capturar.resolver_puerto(puerto_pedido)
    except Exception as e:  # noqa: BLE001 - se informa tal cual
        anotar("Placa por USB", "FALLA", str(e),
               "Conecta la placa con un cable USB-C de datos; en el Administrador de dispositivos debe aparecer un "
               "'Dispositivo serie USB (COMx)'. Si hay varias placas, usa --puerto COMx.")
        return out
    anotar("Placa por USB", "OK", f"{puerto} (VID 303A)")
    out["puerto"] = puerto
    try:
        lector = capturar.LectorSerie(puerto, 115200)
    except Exception as e:  # noqa: BLE001
        anotar("Abrir el puerto", "FALLA", str(e), "Cierra cualquier programa que use ese COM (visor, captura, "
               "monitor serie de Arduino/ESP-IDF) y vuelve a intentar.")
        return out
    lector.escribir(b"AURA INFO\n")          # solo lectura: version y particion
    n_lineas = n_muestras = 0
    tele = info = None
    t0 = time.time()
    fin = t0 + segundos
    # la telemetria (red, RSSI) sale cada ~10 s: si no llego en la ventana, se espera hasta 8 s mas
    while time.time() < fin or (tele is None and n_lineas and time.time() < fin + 8):
        b = lector.leer_linea()
        if b is None:
            continue
        n_lineas += 1
        l = b.decode("utf-8", errors="replace")
        m = RX_IP.search(l)
        if m:
            out["ip"] = m.group(1)
        if l.startswith("HMS:"):
            try:
                j = json.loads(l[4:])
            except json.JSONDecodeError:
                continue
            if j.get("type") == "sample":
                n_muestras += 1
            elif j.get("type") == "telemetria":
                tele = j
            elif j.get("type") == "info":
                info = j
    if n_lineas == 0:
        anotar("Recepcion USB", "FALLA", f"0 lineas en {segundos:.0f} s",
               "Desconecta y reconecta la placa y repite. Si sigue igual, prueba otro cable/puerto.")
        lector.cerrar()
        return out
    dur = time.time() - t0
    ver = (info or {}).get("ver") or (tele or {}).get("ver") or "?"
    out["ver"] = ver
    anotar("Recepcion USB", "OK" if n_muestras / dur >= 10 else "AVISO",
           f"{n_lineas} lineas en {dur:.0f} s, {n_muestras / dur:.1f} muestras del detector/s; firmware {ver}",
           "Si las muestras/s son 0, la placa no tiene WiFi (el detector necesita estar conectado a una red).")
    if tele:
        out["red"] = tele.get("red")
        if tele.get("red") in (None, "ninguna"):
            anotar("WiFi de la placa", "FALLA", "la placa no esta conectada a ninguna red",
                   "Enciende el hotspot (o acerca la placa al router) y espera ~1 min: si no hay red principal pasa "
                   "sola al hotspot. Si cambiaron nombre/clave: scripts\\cargar_credenciales.py --solo wifi1_ssid / "
                   "wifi1_pass --reiniciar")
        else:
            anotar("WiFi de la placa", "OK", f"red {tele.get('red')}, RSSI {tele.get('rssi')} dBm")
    if not out.get("ip"):
        hacer = reiniciar == "si"
        if reiniciar == "preguntar":
            r = input("\nLa IP de la placa solo se informa al conectarse al WiFi. ¿Reinicio la placa (AURA REBOOT) "
                      "para leerla? Tarda ~1 min. [s/N]: ").strip().lower()
            hacer = r in ("s", "si", "sí", "y")
        if hacer:
            lector.reiniciar_por_consola()
            fin = time.time() + 60
            while time.time() < fin and not out.get("ip"):
                b = lector.leer_linea()
                if b is not None:
                    m = RX_IP.search(b.decode("utf-8", errors="replace"))
                    if m:
                        out["ip"] = m.group(1)
            if out.get("ip"):
                time.sleep(5)       # que arranque el detector antes de la prueba de red
    lector.cerrar()
    if out.get("ip"):
        anotar("IP de la placa", "OK", out["ip"])
    else:
        anotar("IP de la placa", "AVISO" if reiniciar == "no" else "FALLA",
               "no se pudo leer (solo aparece al conectarse)",
               "Ejecuta de nuevo con --reiniciar (reinicia la placa), o usa scripts\\ip_placa_usb.py --reiniciar.")
    return out


def probar_red(ip: str, segundos: float):
    import receptor_local as rl
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((ip, rl.PUERTO_DATOS))
        local = s.getsockname()[0]
        s.close()
    except OSError as e:
        anotar("Ruta a la placa", "FALLA", f"sin ruta hacia {ip}: {e}", "Conecta esta PC al mismo WiFi que la placa.")
        return
    misma = local.rsplit(".", 1)[0] == ip.rsplit(".", 1)[0]
    anotar("Misma red", "OK" if misma else "AVISO", f"esta PC {local}, placa {ip}",
           "Conecta esta PC al MISMO WiFi que la placa (en el salon: el hotspot del celular).")
    tmp = Path(tempfile.gettempdir()) / f"aura_verificacion_{os.getpid()}_local.csv"
    try:
        r = rl.recibir(ip, rl.PUERTO_DATOS, tmp, segundos, nombre="verificacion", silencioso=True,
                       bind_explicito=False)
    finally:
        if tmp.exists():
            tmp.unlink()
    csi = r.get("por_tipo", {}).get("csi", 0) / segundos
    hms = r.get("por_tipo", {}).get("hms", 0) / segundos
    if csi >= 50:
        anotar("Recepcion por red", "OK", f"CSI {csi:.0f}/s, muestras {hms:.0f}/s, perdida {r['perdida_pct']:.2f} %")
    elif csi > 0:
        anotar("Recepcion por red", "AVISO", f"CSI {csi:.0f}/s (esperado ~100/s), perdida {r['perdida_pct']:.2f} %",
               "Señal debil o red cargada: acerca la laptop al hotspot/router; el mapa de calor puede ir a saltos.")
    else:
        anotar("Recepcion por red", "FALLA", "no llego nada en 10 s",
               "La PC y la placa deben estar en la misma red y la red no debe aislar a los equipos (redes de "
               "invitados). Si no se puede: plan B solo USB (visor --vivo --puerto auto).")


def main() -> int:
    ap = argparse.ArgumentParser(description="Verifica el kit de captura de AURA en esta PC.")
    ap.add_argument("--puerto", default="auto", help="COM de la placa o auto (por defecto)")
    ap.add_argument("--segundos", type=float, default=10, help="duracion de cada prueba de recepcion")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--reiniciar", action="store_true", help="reiniciar la placa sin preguntar si falta la IP")
    g.add_argument("--sin-reiniciar", action="store_true", help="nunca reiniciar la placa")
    a = ap.parse_args()
    reiniciar = "si" if a.reiniciar else ("no" if a.sin_reiniciar else "preguntar")
    version = (RAIZ / "VERSION").read_text(encoding="utf-8").strip() if (RAIZ / "VERSION").exists() else "?"
    print(f"Verificacion del kit de captura de AURA {version} — {datetime.now():%Y-%m-%d %H:%M:%S}\n", flush=True)

    ok_py = revisar_python()
    ok_dep = ok_py and revisar_dependencias()
    if not ok_dep:
        anotar("Placa y recepcion", "NO PROBADO", "faltan Python o dependencias", "Resuelve lo anterior y repite.")
    else:
        usb = probar_usb(a.puerto, a.segundos, reiniciar)
        if usb.get("ip"):
            probar_red(usb["ip"], a.segundos)
        elif not usb.get("puerto"):
            anotar("Recepcion USB, IP y red", "NO PROBADO", "sin placa", "Conecta la placa y repite.")
        else:
            anotar("Recepcion por red", "NO PROBADO", "sin IP de la placa", "Ver 'IP de la placa'.")

    fallas = [x for x in informe if x[1] == "FALLA"]
    avisos = [x for x in informe if x[1] in ("AVISO", "NO PROBADO")]
    lineas = [f"Kit de captura de AURA {version} — verificacion {datetime.now():%Y-%m-%d %H:%M:%S} en "
              f"{platform.node()}", ""]
    for prueba, estado, detalle, sol in informe:
        lineas.append(f"[{estado}] {prueba}: {detalle}")
        if sol and estado != "OK":
            lineas.append(f"    Solucion: {sol}")
    de_red = {"Ruta a la placa", "Misma red", "Recepcion por red"}
    if fallas and all(x[0] in de_red for x in fallas):
        resumen = (f"RESULTADO: {len(fallas)} falla(s), solo de red: el USB funciona; si no se arregla, usa el plan B "
                   "(visor --vivo --puerto auto, sin mapa de calor).")
    elif fallas:
        resumen = f"RESULTADO: {len(fallas)} falla(s): aplica la solucion de cada FALLA y repite."
    elif avisos:
        resumen = "RESULTADO: funciona, con avisos (ver arriba)."
    else:
        resumen = "RESULTADO: TODO FUNCIONA (USB, IP y recepcion por red)."
    lineas += ["", resumen]
    salida = RAIZ / f"verificacion_{datetime.now():%Y%m%d_%H%M%S}.txt"
    salida.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n" + "=" * 70 + "\n" + "\n".join(lineas) + f"\n(informe guardado en {salida.name})")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
