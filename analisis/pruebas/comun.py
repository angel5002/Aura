"""Utilidades comunes de las pruebas con placa (D1-D10)."""

import json
import statistics
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import receptor_local as rl                                    # noqa: E402
from aura_proto import PUERTO_DATOS, parsear_datagrama          # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
DIR_CRUDOS = RAIZ / "datos" / "crudos"
SALIDA = Path(__file__).resolve().parent / "salida"


def ip_placa(ip: str | None, espera: float = 20) -> str:
    if ip:
        return ip
    an = rl.descubrir(espera)
    if not an:
        raise SystemExit("No llego ningun anuncio de la placa (¿misma red? ¿firewall de Windows?).")
    print(f"Placa {an.get('id')} en {an['ip']} (version {an.get('ver')})")
    return an["ip"]


class Coleccion:
    """Acumula telemetria, muestras y eventos recibidos por la via local."""

    def __init__(self):
        self.telemetria = []     # (t_pc, dict)
        self.muestras = []       # (t_pc, ts_ms, dict)
        self.eventos = []        # (t_pc, dict) ack/ota/arranque/...
        self.lock = threading.Lock()

    def al_recibir(self, t_pc: float, d):
        if d.tipo != "hms":
            return
        try:
            m = json.loads(d.cuerpo)
        except json.JSONDecodeError:
            return
        with self.lock:
            tipo = m.get("type")
            if tipo == "telemetria":
                self.telemetria.append((t_pc, m))
            elif tipo == "sample":
                self.muestras.append((t_pc, m.get("ts_ms"), m))
            else:
                self.eventos.append((t_pc, m))


def recibir_en_hilo(ip: str, id_sesion: str, duracion: float, col: Coleccion) -> tuple[threading.Thread, dict]:
    DIR_CRUDOS.mkdir(parents=True, exist_ok=True)
    destino = DIR_CRUDOS / f"{id_sesion}_local.csv"
    if destino.exists():
        raise SystemExit(f"{destino} ya existe (no se sobrescriben datos); usa otro id de sesion.")
    resultado = {}

    def _correr():
        resultado.update(rl.recibir(ip, PUERTO_DATOS, destino, duracion, al_recibir=col.al_recibir, silencioso=True))

    h = threading.Thread(target=_correr, daemon=True)
    h.start()
    return h, resultado


def intervalos_ts(muestras: list) -> list[float]:
    ts = sorted(t for _, t, _ in muestras if t)
    return [b - a for a, b in zip(ts, ts[1:]) if b > a]


def percentil(v: list[float], p: float) -> float:
    if not v:
        return float("nan")
    s = sorted(v)
    return s[min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))]


def mediana(v):
    return statistics.median(v) if v else float("nan")


def reinicios(telemetria: list) -> int:
    """Cuenta reinicios por saltos hacia atras de 'encendido_s' en la telemetria."""
    n = 0
    prev = None
    for _, t in telemetria:
        e = t.get("encendido_s")
        if prev is not None and e is not None and e < prev:
            n += 1
        prev = e
    return n
