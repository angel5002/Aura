"""Receptor de la via local de AURA: descubre la placa, se suscribe y graba TODO lo que llega.

- Descubrimiento: escucha los anuncios "AURA-ANUNCIO" (UDP 45455) o usa --ip.
- Suscripcion: "SUB <nombre>" cada 10 s (la placa da 30 s de concesion).
- Graba cada datagrama en C:\\aura\\datos\\crudos\\<id>_local.csv (t_pc_unix, linea), mismo formato que capturar.py.
- Mide perdidas con el numero de secuencia: maneja desorden y duplicados; si la placa se reinicia abre una "epoca"
  nueva y suma las perdidas de cada una. Reinicio = el ts_ms de una muestra 'sample' (ms desde el arranque de la
  placa) es menor que el de la muestra anterior; respaldo sin muestras: la secuencia cae mas que VENTANA_DESORDEN de
  forma sostenida (LIMITE del respaldo: no ve reinicios antes de ~1000 datagramas desde el arranque anterior).
- Informa cada 5 s la tasa por tipo y el porcentaje de perdida; al final guarda <id>_local_resumen.json.
- Puede alimentar el panel en vivo (visor.py) mediante la funcion 'al_recibir'.

Ejemplo:
    python C:\\aura\\analisis\\receptor_local.py --id-sesion L001 --duracion 1800
"""

import argparse
import csv
import json
import socket
import sys
import time
from collections import Counter
from pathlib import Path

from aura_proto import PUERTO_ANUNCIO, PUERTO_DATOS, parsear_anuncio, parsear_datagrama

RAIZ = Path(__file__).resolve().parent.parent
DIR_CRUDOS = RAIZ / "datos" / "crudos"

# Reinicio de la placa = la secuencia cae mas que esta ventana respecto al maximo visto, de forma sostenida.
# Desorden medido el 26/10/2026 en F1, S002 y PV (110 376 datagramas, receptor en la PC): 0. 1000 datagramas son
# ~8,5 s a la tasa de S002 (117,6/s) y ~15 lotes del firmware (hasta 64 por vuelta, aura_local.c:353).
VENTANA_DESORDEN = 1000
# Un duplicado viejo tambien "cae" mas que la ventana, pero llega aislado; tras un reinicio llega una secuencia
# nueva sostenida (1, 2, 3...). Se confirma el reinicio con CONFIRMAR_REINICIO datagramas seguidos por debajo de
# la ventana y agrupados en un rango menor que ella (~0,17 s a 117,6/s).
# LIMITE (~1000 datagramas): el reinicio solo se ve si la secuencia anterior pasaba de VENTANA_DESORDEN +
# CONFIRMAR_REINICIO (1020). La secuencia de la placa cuenta desde su arranque y solo avanza con receptor suscrito
# (aura_local.c:166-169): un reinicio antes de ~1000 datagramas (~8,5 s a la tasa de S002), p. ej. reinicios en
# bucle, no se detecta y se cuenta como duplicados. Afecta solo al resumen, no al CSV. Para estos casos sirve la
# telemetria de la placa (encendido_s, motivo de reinicio).
# No hay rezagados de la epoca anterior: entre el ultimo datagrama y el primero tras el reinicio pasan segundos.
CONFIRMAR_REINICIO = 20
# Regla principal (aprobada por Deisy el 26/10/2026): reinicio = ts_ms de una muestra menor que el de la anterior.
# ts_ms = esp_timer desde el arranque (web_serial_monitor.c:271), ~17 muestras/s en S002. Se toleran retrocesos de
# hasta TOLERANCIA_TS_MS por desorden (medido: 0; las muestras van cada ~60 ms). Una muestra con la misma secuencia
# y el mismo ts_ms que otra ya vista es un duplicado, no un reinicio (T4 manda duplicados con otro contenido).
# Limites: (a) si la placa muere con menos uptime que el que tiene al enviar su primera muestra tras arrancar (+ la
# tolerancia), el reinicio no se ve por ts_ms; (b) si el arranque nuevo repite exactamente secuencia y milisegundo
# del anterior (la numeracion empieza al llegar el SUB, que va cada 10 s: improbable), tampoco. En ambos casos queda
# el respaldo por secuencia.
TOLERANCIA_TS_MS = 500


def ts_muestra(d) -> int | None:
    """ts_ms de un datagrama 'hms' con una muestra {"type":"sample","ts_ms":...}; None en otro caso."""
    if d.tipo != "hms" or '"type":"sample"' not in d.cuerpo:
        return None
    try:
        v = json.loads(d.cuerpo).get("ts_ms")
    except json.JSONDecodeError:
        return None
    return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


class ContadorSecuencia:
    """Cuenta recibidos, perdidos, desordenados y duplicados a partir de numeros de secuencia."""

    def __init__(self, ventana_dup: int = 100000, ventana_desorden: int = VENTANA_DESORDEN,
                 confirmar_reinicio: int = CONFIRMAR_REINICIO):
        self.epocas = []          # (min, max, unicos) de epocas cerradas
        self.min = self.max = None
        self.vistos = set()
        self.desordenados = 0
        self.duplicados = 0
        self.ventana_dup = ventana_dup
        self.ventana_desorden = ventana_desorden
        self.confirmar_reinicio = confirmar_reinicio
        self.candidatos = []      # caidas mayores que la ventana aun sin clasificar (reinicio o duplicados viejos)
        self.ultimo_ts = None     # mayor ts_ms visto en la epoca actual
        self.muestras = {}        # seq -> ts_ms de las muestras de la epoca actual (para reconocer duplicados)
        self.reinicios_ts = 0
        self.reinicios_secuencia = 0

    def agregar(self, seq: int, ts_ms: int | None = None):
        """ts_ms: el de la muestra si el datagrama es un 'sample' (ver ts_muestra); None para el resto."""
        duplicada = ts_ms is not None and self.muestras.get(seq) == ts_ms
        if ts_ms is not None and not duplicada and self.ultimo_ts is not None \
                and ts_ms < self.ultimo_ts - TOLERANCIA_TS_MS:
            pendientes, self.candidatos = self.candidatos, []
            self._cerrar_epoca()          # la placa se reinicio (regla principal: ts_ms retrocede)
            self.reinicios_ts += 1
            for s in pendientes:          # datagramas del arranque nuevo que llegaron antes de esta muestra
                self._contar(s)
            self._contar(seq)
            self._anotar_ts(seq, ts_ms)
            return
        if self.max is not None and seq < self.max - self.ventana_desorden:
            self.candidatos.append(seq)
            if len(self.candidatos) >= self.confirmar_reinicio and \
                    max(self.candidatos) - min(self.candidatos) < self.ventana_desorden:
                pendientes, self.candidatos = self.candidatos, []
                self._cerrar_epoca()      # la placa se reinicio (respaldo: la secuencia cae de forma sostenida)
                self.reinicios_secuencia += 1
                for s in pendientes:
                    self._contar(s)
            return
        self._vaciar_candidatos()
        self._contar(seq)
        if ts_ms is not None and not duplicada:
            self._anotar_ts(seq, ts_ms)

    def _anotar_ts(self, seq: int, ts_ms: int):
        self.muestras[seq] = ts_ms
        self.ultimo_ts = ts_ms if self.ultimo_ts is None else max(self.ultimo_ts, ts_ms)

    def _vaciar_candidatos(self):
        """Las caidas no confirmadas como reinicio se cuentan en la epoca actual (duplicados o desorden)."""
        pendientes, self.candidatos = self.candidatos, []
        for s in pendientes:
            self._contar(s)

    def _contar(self, seq: int):
        if seq in self.vistos:
            self.duplicados += 1
            return
        if self.max is not None and seq < self.max:
            self.desordenados += 1
        self.vistos.add(seq)
        self.min = seq if self.min is None else min(self.min, seq)
        self.max = seq if self.max is None else max(self.max, seq)
        if len(self.vistos) > 2 * self.ventana_dup:   # acotar memoria en sesiones largas
            limite = self.max - self.ventana_dup
            self._podar(limite)

    def _podar(self, limite):
        viejos = [s for s in self.vistos if s < limite]
        self._unicos_podados = getattr(self, "_unicos_podados", 0) + len(viejos)
        self.vistos.difference_update(viejos)
        self.muestras = {s: t for s, t in self.muestras.items() if s >= limite}

    def _cerrar_epoca(self):
        if self.min is not None:
            self.epocas.append((self.min, self.max, len(self.vistos) + getattr(self, "_unicos_podados", 0)))
        self.min = self.max = None
        self.vistos = set()
        self._unicos_podados = 0
        self.ultimo_ts = None
        self.muestras = {}

    def resumen(self, final: bool = False) -> dict:
        """final=True: al terminar, las caidas aun sin clasificar se cuentan en la epoca actual."""
        if final:
            self._vaciar_candidatos()
        epocas = list(self.epocas)
        if self.min is not None:
            epocas.append((self.min, self.max, len(self.vistos) + getattr(self, "_unicos_podados", 0)))
        esperados = sum(mx - mn + 1 for mn, mx, _ in epocas)
        recibidos = sum(u for _, _, u in epocas)
        perdidos = esperados - recibidos
        return {
            "esperados": esperados, "recibidos_unicos": recibidos, "perdidos": perdidos,
            "perdida_pct": 100.0 * perdidos / esperados if esperados else 0.0,
            "desordenados": self.desordenados, "duplicados": self.duplicados, "epocas": len(epocas),
            "reinicios_por_ts": self.reinicios_ts, "reinicios_por_secuencia": self.reinicios_secuencia,
        }


def descubrir(timeout: float) -> dict | None:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("", PUERTO_ANUNCIO))
    s.settimeout(0.5)
    fin = time.time() + timeout
    try:
        while time.time() < fin:
            try:
                datos, de = s.recvfrom(2048)
            except socket.timeout:
                continue
            an = parsear_anuncio(datos.decode("utf-8", errors="replace"))
            if an:
                an.setdefault("ip", de[0])
                return an
    finally:
        s.close()
    return None


def recibir(ip: str, puerto: int, destino: Path, duracion: float, nombre: str = "pc",
            al_recibir=None, informar_cada: float = 5.0, silencioso: bool = False,
            bind_explicito: bool = True) -> dict:
    """bind_explicito=False: no se llama a bind(); el primer sendto(SUB) asigna el puerto local. Los datos de la
    placa llegan como respuesta a ese envio (misma IP y puerto), sin abrir un puerto de escucha."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    if bind_explicito:
        sock.bind(("", 0))
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
    sock.settimeout(0.5)
    cont = ContadorSecuencia()
    por_tipo = Counter()
    otros = 0
    t_inicio = time.time()
    t_fin = t_inicio + duracion
    prox_sub = 0.0
    prox_info = t_inicio + informar_cada
    ultimo_dato = None
    fin = "duracion"            # por que termino: duracion | usuario (Ctrl+C) | error: ... (lo usa verificar_captura)
    with open(destino, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_pc_unix", "linea"])
        try:
            while time.time() < t_fin:
                ahora = time.time()
                if ahora >= prox_sub:
                    try:
                        sock.sendto(f"SUB {nombre}".encode(), (ip, puerto))
                    except OSError:
                        pass            # sin red por un momento: se reintenta en 10 s
                    prox_sub = ahora + 10
                try:
                    datos, _ = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                except ConnectionResetError:
                    # Windows: un envio previo a un puerto cerrado (placa reiniciandose) devuelve
                    # WSAECONNRESET en el siguiente recvfrom; no es un error de datos.
                    continue
                t = time.time()
                linea = datos.decode("utf-8", errors="replace")
                w.writerow([f"{t:.6f}", linea])
                d = parsear_datagrama(linea)
                if d is None:
                    otros += 1
                    continue
                ultimo_dato = t
                cont.agregar(d.seq, ts_muestra(d))
                por_tipo[d.tipo] += 1
                if al_recibir:
                    al_recibir(t, d)
                if t >= prox_info and not silencioso:
                    r = cont.resumen()
                    dt = t - t_inicio
                    tasas = ", ".join(f"{k} {v / dt:.1f}/s" for k, v in sorted(por_tipo.items()))
                    print(f"  {dt:7.1f} s | {tasas} | perdida {r['perdida_pct']:.2f}% "
                          f"({r['perdidos']}/{r['esperados']}) | desorden {r['desordenados']} | dup {r['duplicados']}")
                    prox_info += informar_cada
        except KeyboardInterrupt:
            fin = "usuario"
            print("\nDetenido por el usuario.")
        except OSError as e:
            fin = f"error: {type(e).__name__}: {e}"
            print(f"\nERROR de red, se detiene la captura: {e}")
        finally:
            try:
                sock.sendto(b"UNSUB", (ip, puerto))
            except OSError:
                pass
            sock.close()
    dur = time.time() - t_inicio
    resumen = cont.resumen(final=True)
    resumen.update({
        "archivo": str(destino), "duracion_s": dur, "duracion_pedida_s": duracion, "fin": fin,
        "por_tipo": dict(por_tipo), "otros": otros,
        "tasa_total_por_s": sum(por_tipo.values()) / dur if dur else 0, "ip": ip,
        "segundos_sin_datos_al_final": (time.time() - ultimo_dato) if ultimo_dato else None,
    })
    return resumen


def main() -> int:
    ap = argparse.ArgumentParser(description="Receptor de la via local de AURA.")
    ap.add_argument("--id-sesion", required=True)
    ap.add_argument("--duracion", type=float, required=True, help="segundos")
    ap.add_argument("--ip", help="IP de la placa (si no, se descubre por anuncio)")
    ap.add_argument("--puerto", type=int, default=PUERTO_DATOS)
    ap.add_argument("--espera-anuncio", type=float, default=15)
    ap.add_argument("--sin-bind", action="store_true",
                    help="con --ip: sin bind() explicito (el primer SUB asigna el puerto local)")
    args = ap.parse_args()

    DIR_CRUDOS.mkdir(parents=True, exist_ok=True)
    destino = DIR_CRUDOS / f"{args.id_sesion}_local.csv"
    if destino.exists():
        print(f"ERROR: {destino} ya existe (no se sobrescriben datos).")
        return 1
    ip = args.ip
    if not ip:
        print(f"Buscando la placa (anuncios en UDP {PUERTO_ANUNCIO}, {args.espera_anuncio:.0f} s)...")
        an = descubrir(args.espera_anuncio)
        if not an:
            print("ERROR: no llego ningun anuncio. ¿La placa y la PC estan en la misma red? ¿Firewall de Windows?")
            return 1
        ip = an["ip"]
        print(f"Placa encontrada: {an.get('id')} en {ip} (version {an.get('ver')})")
    print(f"Recibiendo {args.duracion:.0f} s -> {destino}")
    r = recibir(ip, args.puerto, destino, args.duracion, bind_explicito=not args.sin_bind)
    (DIR_CRUDOS / f"{args.id_sesion}_local_resumen.json").write_text(json.dumps(r, indent=2), encoding="utf-8")
    print("\n--- Resumen ---")
    for k in ("fin", "duracion_s", "por_tipo", "tasa_total_por_s", "esperados", "recibidos_unicos", "perdidos",
              "perdida_pct", "desordenados", "duplicados", "epocas",
              "reinicios_por_ts", "reinicios_por_secuencia"):
        print(f"{k:>18}: {r[k]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
