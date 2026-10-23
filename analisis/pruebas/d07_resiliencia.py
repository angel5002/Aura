"""D7 - Resiliencia (requiere firmware >= 0.1.2 para los casos simulados).

  --caso r      Rechazo sin clave: SIM_SIN_INTERNET y SIM_PIERDE_PRINCIPAL firmados con una clave falsa deben
                volver RECHAZADO ("autenticacion fallida"), sumar en 'cmd_rechazados' de la telemetria y no
                activar nada (sim_*_s = 0). Con --puerto COMx tambien se prueban por USB (deben rechazarse:
                "solo por la via local autenticada").
  --caso a-sim  SIMULACION de corte de internet: SIM_SIN_INTERNET 300 (la placa bloquea solo sus conexiones a
                Firebase; WiFi, via local y SNTP siguen). Criterios: via local sin perdidas significativas
                (< 1 %), 0 reinicios, espera creciente durante el corte (nube_espera_s crece) y la nube vuelve
                sola a 'operando' al terminar.
  --caso b      Se apaga el receptor de la PC 3 min. Criterio: la nube sigue con latidos sin huecos > 150 s.
  --caso c-sim  SIMULACION de caida de la red principal: SIM_PIERDE_PRINCIPAL 600 con el hotspot encendido.
                Como la PC no tiene WiFi, se mide desde la NUBE (tu cuenta, sin eco): tiempo hasta la primera
                escritura por el hotspot, red=respaldo en el latido, presencia "no_disponible"; que NO vuelva
                antes de los 600 s; y que vuelva sola a la principal en el primer reintento (cada
                --reintento-min, 15 por defecto) tras terminar la simulacion, sin reinicios.
  --caso a-real OPCIONAL, en el horario que elijas: corte REAL de internet desconectando el cable coaxial del
                router 5 min (la casa queda ~10 min sin internet por la resincronizacion del modem). Mismos
                criterios que a-sim.

Los casos -sim prueban la logica de recuperacion de la placa, NO una caida real de la red; asi se registran.
"""

import argparse
import sys
import threading
import time
from pathlib import Path

from comun import Coleccion, ip_placa, recibir_en_hilo, reinicios, rl
from registrar import registrar

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aura_proto import leer_clave_local  # noqa: E402
from comando_local import enviar_comando  # noqa: E402
from fb_rest import Sesion, cargar_config, peticion  # noqa: E402

NOTA_SIM = "SIMULACION: prueba la logica de recuperacion de la placa, no una caida real de la red"


def ultima_telemetria(col: Coleccion) -> dict:
    with col.lock:
        return col.telemetria[-1][1] if col.telemetria else {}


def esperar_telemetria(col: Coleccion, n: int, limite: float = 40) -> None:
    fin = time.time() + limite
    while time.time() < fin and len(col.telemetria) < n:
        time.sleep(1)


# ---------------- r: rechazo sin clave ----------------

def caso_r(ip: str, puerto: str | None) -> bool:
    col = Coleccion()
    h, _ = recibir_en_hilo(ip, "D7r", 60, col)
    esperar_telemetria(col, 1)
    antes = ultima_telemetria(col).get("cmd_rechazados")
    acks = []
    for texto in ("SIM_SIN_INTERNET 10", "SIM_PIERDE_PRINCIPAL 10"):
        a = enviar_comando(ip, texto, "clave-incorrecta-de-prueba")
        acks.append((texto, a))
        print(f"  {texto} con clave falsa -> {a}")
    usb = []
    if puerto:
        usb = probar_usb(puerto)
    esperar_telemetria(col, len(col.telemetria) + 2)
    h.join()
    tel = ultima_telemetria(col)
    despues = tel.get("cmd_rechazados")
    rechazados_ok = all(a and not a.get("ok") and a.get("cmd") == "RECHAZADO" and "autenticacion" in a.get("detail", "")
                        for _, a in acks)
    contador_ok = isinstance(antes, int) and isinstance(despues, int) and despues - antes >= len(acks) + len(usb)
    sin_efecto = tel.get("sim_sin_internet_s") == 0 and tel.get("sim_pierde_principal_s") == 0
    usb_ok = all(ok for _, ok in usb)
    ok = rechazados_ok and contador_ok and sin_efecto and usb_ok
    registrar("D7r comandos SIM sin clave", f"acks {[(t, a and a.get('detail')) for t, a in acks]}; cmd_rechazados "
              f"{antes}->{despues}; sim activas {tel.get('sim_sin_internet_s')}/{tel.get('sim_pierde_principal_s')} s"
              + (f"; USB {usb}" if usb else ""),
              "2 RECHAZADO por autenticacion, contador +2 (o mas), ninguna simulacion activa",
              "APROBADA" if ok else "FALLIDA", "" if puerto else "sin prueba por USB (no se dio --puerto)")
    return ok


def probar_usb(puerto: str) -> list:
    """Envia los SIM por la consola USB; deben rechazarse ("solo por la via local autenticada")."""
    import json as _json
    from capturar import abrir_puerto
    res = []
    ser = abrir_puerto(puerto, 115200)
    ser.timeout = 0.3
    try:
        for texto in ("SIM_SIN_INTERNET 10", "SIM_PIERDE_PRINCIPAL 10"):
            ser.write(f"HMSCMD {texto}\n".encode())
            fin, ok = time.time() + 4, False
            while time.time() < fin:
                linea = ser.readline().decode("utf-8", errors="replace").strip()
                if linea.startswith("HMS:"):
                    try:
                        m = _json.loads(linea[4:])
                    except _json.JSONDecodeError:
                        continue
                    if m.get("type") == "ack" and m.get("cmd") == texto.split()[0]:
                        ok = (not m.get("ok")) and "solo por la via local" in m.get("detail", "")
                        break
            res.append((texto, ok))
    finally:
        ser.close()
    return res


# ---------------- a: corte de internet (simulado o real) ----------------

def analizar_corte(col, res, t_ini_corte, t_fin_corte, etiqueta, nota, t0):
    estados = [(t, x.get("nube"), x.get("nube_espera_s")) for t, x in col.telemetria]
    durante = [(t, e, w) for t, e, w in estados if t_ini_corte + 30 < t < t_fin_corte]
    esperas = [w for _, e, w in durante if e == "espera_reintento" and w]
    crece = len(esperas) >= 2 and all(b >= a for a, b in zip(esperas, esperas[1:])) and max(esperas) > min(esperas)
    efectiva = bool(durante) and all(e != "operando" for _, e, _ in durante)
    recupera = next((t - t_fin_corte for t, e, _ in estados if t > t_fin_corte and e == "operando"), None)
    esc = [(t, x.get("nube_escrituras")) for t, x in col.telemetria]
    esc_fin = next((e for t, e in esc if t >= t_fin_corte), None)
    esc_ult = esc[-1][1] if esc else None
    escribe_despues = esc_fin is not None and esc_ult is not None and esc_ult > esc_fin
    rein = reinicios(col.telemetria)
    ok = res["perdida_pct"] < 1 and rein == 0 and efectiva and crece and recupera is not None and escribe_despues
    registrar(etiqueta,
              f"perdida local {res['perdida_pct']:.2f} %, reinicios {rein}, nube durante el corte "
              f"{sorted({str(e) for _, e, _ in durante})}, esperas {sorted(set(esperas))} s, vuelve a 'operando' "
              f"{'en ' + str(round(recupera)) + ' s' if recupera is not None else 'NO'} tras el fin del corte, "
              f"escrituras despues {'si' if escribe_despues else 'no'}",
              "local < 1 %, 0 reinicios, espera creciente, nube se recupera sola",
              "APROBADA" if ok else "FALLIDA", f"{nota}; duracion total {time.time() - t0:.0f} s")
    return ok


def caso_a_sim(ip: str, segundos: int) -> bool:
    clave = leer_clave_local()
    col = Coleccion()
    total = 60 + segundos + 330          # 1 min normal + corte + hasta 5,5 min para recuperarse
    h, res = recibir_en_hilo(ip, "D7a_sim", total, col)
    t0 = time.time()
    print("Minuto 0-1: normal.")
    time.sleep(60)
    ack = enviar_comando(ip, f"SIM_SIN_INTERNET {segundos}", clave)
    t_ini = time.time()
    print(f"SIM_SIN_INTERNET {segundos} -> {ack}")
    if not ack or not ack.get("ok"):
        h.join()
        registrar("D7a-sim corte de internet (simulado)", f"comando no aceptado: {ack}", "comando aceptado",
                  "FALLIDA", NOTA_SIM)
        return False
    h.join()
    return analizar_corte(col, res, t_ini, t_ini + segundos, f"D7a-sim corte de internet {segundos} s (simulado)",
                          NOTA_SIM, t0)


def caso_a_real(ip: str) -> bool:
    col = Coleccion()
    h, res = recibir_en_hilo(ip, "D7a_real", 16 * 60, col)
    t0 = time.time()
    print("Minuto 0-1: normal.")
    time.sleep(60)
    input("\n>>> DESCONECTA AHORA el cable COAXIAL del router (deja el router encendido) y pulsa Enter.\n")
    t_corte = time.time()
    restante = 300 - (time.time() - t_corte)
    time.sleep(max(0, restante))
    input("\n>>> RECONECTA AHORA el cable coaxial y pulsa Enter (el modem tarda unos minutos en resincronizar).\n")
    t_vuelta = time.time()
    h.join()
    return analizar_corte(col, res, t_corte, t_vuelta, "D7a-real corte de internet 5 min (coaxial)",
                          "corte REAL de internet; incluye la resincronizacion del modem", t0)


# ---------------- b: receptor de la PC apagado ----------------

def caso_b(ip, sensor):
    cfg = cargar_config()
    ses = Sesion(cfg, etiqueta="usuario")
    col = Coleccion()
    h, _ = recibir_en_hilo(ip, "D7b", 60, col)
    h.join()
    print("Receptor local detenido; durante 3 min solo se consulta la nube.")
    t_ini = time.time()
    lat = []
    while time.time() - t_ini < 180:
        c, l = peticion(cfg, "GET", f"/sensores/{sensor}/latido", ses)
        if c == 200 and isinstance(l, dict):
            if not lat or l.get("t") != lat[-1].get("t"):
                lat.append(l)
        time.sleep(15)
    huecos = [(b["t"] - a["t"]) / 1000 for a, b in zip(lat, lat[1:])]
    ok = len(lat) >= 3 and (max(huecos) if huecos else 999) <= 150
    registrar("D7b receptor de la PC apagado", f"{len(lat)} latidos en 3 min; hueco maximo {max(huecos) if huecos else 'n/a'} s",
              ">= 3 latidos y huecos <= 150 s", "APROBADA" if ok else "FALLIDA")
    return ok


# ---------------- c-sim: caida simulada de la red principal ----------------

class Anuncios:
    """Escucha en segundo plano los anuncios de la placa en la red local (solo llegan si esta en la principal)."""

    def __init__(self):
        self.vistos = []          # tiempos de PC
        self._fin = False
        self.h = threading.Thread(target=self._correr, daemon=True)
        self.h.start()

    def _correr(self):
        while not self._fin:
            an = rl.descubrir(3)
            if an:
                self.vistos.append(time.time())

    def ultimo(self) -> float | None:
        return self.vistos[-1] if self.vistos else None

    def parar(self):
        self._fin = True


def caso_c_sim(ip: str, sensor: str, segundos: int, reintento_min: float) -> bool:
    cfg = cargar_config()
    clave = leer_clave_local()
    print("Inicia sesion con TU cuenta (persona) para leer /sensores desde la nube:")
    ses = Sesion(cfg, etiqueta="usuario")
    an = Anuncios()
    ack = enviar_comando(ip, f"SIM_PIERDE_PRINCIPAL {segundos}", clave)
    t_env = time.time()
    print(f"SIM_PIERDE_PRINCIPAL {segundos} -> {ack}")
    if not ack or not ack.get("ok"):
        an.parar()
        registrar("D7c-sim caida de la red principal (simulada)", f"comando no aceptado: {ack}", "comando aceptado",
                  "FALLIDA", NOTA_SIM)
        return False
    limite = t_env + segundos + reintento_min * 60 + 300
    ult = {"lat": None, "est": None, "crudo": None}
    eventos = []              # (t_pc, tipo, dato)
    latidos = []
    t_ult_escritura = t_env
    t_hueco = t_vuelta_nube = t_principal = None
    presencia_tras = red_tras = None
    while time.time() < limite:
        ahora = time.time()
        c1, lat = peticion(cfg, "GET", f"/sensores/{sensor}/latido", ses)
        c2, est = peticion(cfg, "GET", f"/sensores/{sensor}/estado", ses)
        c3, cru = peticion(cfg, "GET", f"/crudo/{sensor}", ses, consulta={"orderBy": '"$key"', "limitToLast": 1})
        nuevo = []
        if c1 == 200 and isinstance(lat, dict) and lat.get("t") != ult["lat"]:
            ult["lat"] = lat.get("t")
            latidos.append((ahora, lat))
            nuevo.append(("latido", lat.get("red")))
        if c2 == 200 and isinstance(est, dict) and est.get("t") != ult["est"]:
            ult["est"] = est.get("t")
            nuevo.append(("estado", est.get("presencia")))
        clave_cru = next(iter(cru), None) if c3 == 200 and isinstance(cru, dict) else None
        if clave_cru and clave_cru != ult["crudo"]:
            ult["crudo"] = clave_cru
            nuevo.append(("crudo", clave_cru))
        if nuevo and ahora > t_env + 5:
            eventos += [(ahora, k, v) for k, v in nuevo]
            if t_hueco and not t_vuelta_nube:
                t_vuelta_nube = ahora
                print(f"  +{ahora - t_env:5.0f} s: la placa vuelve a escribir en la nube ({nuevo})")
            t_ult_escritura = ahora
        if not t_hueco and ahora - t_ult_escritura > 25:
            t_hueco = t_ult_escritura
            print(f"  +{ahora - t_env:5.0f} s: sin escrituras desde +{t_hueco - t_env:.0f} s (la placa dejo la principal)")
        if t_vuelta_nube:
            if presencia_tras is None and any(k == "estado" and t >= t_vuelta_nube for t, k, _ in eventos):
                presencia_tras = next(v for t, k, v in eventos if k == "estado" and t >= t_vuelta_nube)
            if red_tras is None and any(k == "latido" and t >= t_vuelta_nube for t, k, _ in eventos):
                red_tras = next(v for t, k, v in eventos if k == "latido" and t >= t_vuelta_nube)
        u = an.ultimo()
        if t_vuelta_nube and u and u > t_vuelta_nube and not t_principal:
            t_principal = u
            print(f"  +{u - t_env:5.0f} s: anuncio en la red local: volvio a la principal")
        if t_principal and any(k == "latido" and v == "principal" and t > t_principal for t, k, v in eventos):
            break
        time.sleep(5)
    an.parar()
    ups = [l.get("up") for _, l in latidos if isinstance(l.get("up"), int)]
    rein = sum(1 for a, b in zip(ups, ups[1:]) if b < a)
    antes_de_tiempo = [t for t in an.vistos if t_hueco and t_hueco + 10 < t < t_env + segundos]
    t_reconexion = (t_vuelta_nube - t_env) if t_vuelta_nube else None
    plazo_vuelta = (t_vuelta_nube or t_env) + reintento_min * 60 + 120
    vuelve = bool(t_principal) and t_principal >= t_env + segundos and t_principal <= plazo_vuelta
    ok = (t_vuelta_nube is not None and red_tras == "respaldo" and presencia_tras == "no_disponible"
          and not antes_de_tiempo and vuelve and rein == 0)
    registrar(f"D7c-sim caida de la red principal {segundos} s (simulada)",
              f"reconecta por el hotspot (1a escritura en la nube) a los "
              f"{round(t_reconexion) if t_reconexion is not None else 'NO'} s; red en el latido {red_tras}; presencia "
              f"{presencia_tras}; vuelve a la principal a los "
              f"{round(t_principal - t_env) if t_principal else 'NO'} s; reinicios {rein}",
              f"pasa al respaldo, red=respaldo, presencia no_disponible, no vuelve antes de {segundos} s, vuelve sola "
              f"en <= {reintento_min:.0f} min + 2 min tras pasar al respaldo, 0 reinicios",
              "APROBADA" if ok else "FALLIDA",
              f"{NOTA_SIM}; medido desde la nube con sondeo cada 5 s (resolucion ~5 s; latido cada 60 s)"
              + ("; anuncios en la principal antes de tiempo" if antes_de_tiempo else ""))
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--caso", choices=["r", "a-sim", "a-real", "b", "c-sim"], required=True)
    ap.add_argument("--ip")
    ap.add_argument("--sensor", default="hab1")
    ap.add_argument("--puerto", help="caso r: probar tambien el rechazo por USB")
    ap.add_argument("--segundos", type=int, help="duracion de la simulacion (a-sim 300, c-sim 600)")
    ap.add_argument("--reintento-min", type=float, default=15, help="CONFIG_AURA_REINTENTO_PRINCIPAL_MIN")
    a = ap.parse_args()
    ip = ip_placa(a.ip)
    if a.caso == "r":
        ok = caso_r(ip, a.puerto)
    elif a.caso == "a-sim":
        ok = caso_a_sim(ip, a.segundos or 300)
    elif a.caso == "a-real":
        ok = caso_a_real(ip)
    elif a.caso == "b":
        ok = caso_b(ip, a.sensor)
    else:
        ok = caso_c_sim(ip, a.sensor, a.segundos or 600, a.reintento_min)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
