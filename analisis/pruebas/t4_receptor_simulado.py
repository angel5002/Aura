"""T4 - Receptor local con flujo simulado (sin placa).

Un simulador imita la via local de la placa (mismo formato "A1 <seq> <t_us> <tipo> <cuerpo>", con mensajes
'sample' y 'csi' realistas) en 127.0.0.1, espera la suscripcion "SUB" y envia N datagramas con:
  - exactamente 1 % de numeros de secuencia sin enviar (perdidos),
  - ~2 % de pares intercambiados (desorden) y algunos duplicados.
Criterios:
  a) receptor_local.py informa una perdida entre 0,8 % y 1,2 %;
  b) maneja el desorden (lo cuenta) y no cuenta los duplicados como recibidos;
  c) guarda TODO lo que llego (filas del archivo = datagramas enviados que no se perdieron, duplicados incluidos);
  d) el modo de reproduccion de visor.py reconstruye el panel desde el archivo (genera cuadros PNG).
"""

import base64
import json
import random
import socket
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import receptor_local as rl          # noqa: E402
import visor                         # noqa: E402
from registrar import registrar      # noqa: E402

SALIDA = Path(__file__).resolve().parent / "salida"
PUERTO = 46454
N = 5000
TASA = 500.0       # datagramas por segundo


def cuerpo_sample(k: int, t_s: float) -> str:
    mov = (k // 300) % 2 == 1
    return json.dumps({"type": "sample", "ts_ms": int(t_s * 1000), "peer": "AP", "motion_status": mov,
                       "presence_someone_status": False, "train_thresholds_valid": False,
                       "smooth_scaled": 1500000 + (400000 if mov else 0) + random.randint(-50000, 50000),
                       "enter_level_scaled": 1700000, "exit_level_scaled": 1400000, "init_stage_name": "STABLE"},
                      separators=(",", ":"))


def cuerpo_csi(k: int, t_us: int) -> str:
    vals = [int(30 * (1 + 0.2 * random.random())) for _ in range(104)]
    valid = b"".join(v.to_bytes(2, "little", signed=True) for v in vals)
    raw = bytes(2) + valid + bytes(4)
    return json.dumps({"seq_id": k, "t_us": t_us, "rx_ts_us": k * 10000, "rssi": -40, "nf": -95, "canal": 6,
                       "agc": 30, "fft": -10, "rate": 11, "rx_format": 0, "cwb": 0, "tipo_dato": 1, "comp": 1.0,
                       "raw_len": len(raw), "valid_len": len(valid), "raw": base64.b64encode(raw).decode(),
                       "valid": base64.b64encode(valid).decode()}, separators=(",", ":"))


def simulador(listo: threading.Event, plan: dict):
    random.seed(7)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", PUERTO))
    s.settimeout(10)
    datos, sub = s.recvfrom(1024)                   # espera "SUB ..."
    while not datos.startswith(b"SUB"):
        datos, sub = s.recvfrom(1024)
    perdidos = set(random.sample(range(2, N), N // 100))          # 1 % exacto, nunca el primero ni el ultimo
    orden = [q for q in range(1, N + 1) if q not in perdidos]
    intercambios = 0
    for i in range(0, len(orden) - 1, 50):                          # ~2 % de pares intercambiados
        orden[i], orden[i + 1] = orden[i + 1], orden[i]
        intercambios += 1
    duplicados = random.sample(orden, 10)
    envio = orden + duplicados
    t0 = time.time()
    for i, q in enumerate(envio):
        t_us = int((t0 + q / TASA) * 1e6)
        tipo, cuerpo = ("hms", cuerpo_sample(q, q / TASA)) if q % 3 == 0 else ("csi", cuerpo_csi(q, t_us))
        s.sendto(f"A1 {q} {t_us} {tipo} {cuerpo}".encode(), sub)
        if i % 25 == 0:
            espera = t0 + i / TASA - time.time()
            if espera > 0:
                time.sleep(espera)
    plan.update(perdidos=len(perdidos), enviados=len(envio), intercambios=intercambios, duplicados=len(duplicados))
    s.close()
    listo.set()


def main() -> int:
    SALIDA.mkdir(parents=True, exist_ok=True)
    destino = SALIDA / "T4_local.csv"
    if destino.exists():
        destino.unlink()            # archivo de prueba sintetico generado por este mismo script
    plan = {}
    listo = threading.Event()
    hilo = threading.Thread(target=simulador, args=(listo, plan), daemon=True)
    hilo.start()
    time.sleep(0.3)
    r = rl.recibir("127.0.0.1", PUERTO, destino, duracion=N / TASA + 4, silencioso=True)
    listo.wait(5)

    filas = sum(1 for _ in open(destino, encoding="utf-8")) - 1
    esperado_pct = 100 * plan["perdidos"] / N
    a = 0.8 <= r["perdida_pct"] <= 1.2
    b = r["desordenados"] >= plan["intercambios"] and r["duplicados"] == plan["duplicados"] \
        and r["recibidos_unicos"] == N - plan["perdidos"]
    c = filas == plan["enviados"]
    cuadros = SALIDA / "T4_cuadros"
    for p in cuadros.glob("cuadro_*.png"):
        p.unlink()                  # cuadros de una ejecucion anterior de esta prueba
    rc = visor.reproducir(destino, cuadros, fps=2, desde=None, hasta=None)
    n_png = len(list(cuadros.glob("cuadro_*.png")))
    d = rc == 0 and n_png >= 5

    registrar("T4a perdida informada", f"{r['perdida_pct']:.3f} % (real {esperado_pct:.1f} %: {plan['perdidos']} de {N})",
              "entre 0,8 % y 1,2 %", "APROBADA" if a else "FALLIDA")
    registrar("T4b desorden y duplicados", f"desordenados {r['desordenados']} (intercambios {plan['intercambios']}), "
              f"duplicados {r['duplicados']} de {plan['duplicados']}, unicos {r['recibidos_unicos']}",
              "desorden detectado; duplicados no cuentan como recibidos", "APROBADA" if b else "FALLIDA")
    registrar("T4c todo guardado", f"{filas} filas de {plan['enviados']} datagramas enviados",
              "filas = datagramas que llegaron", "APROBADA" if c else "FALLIDA", str(destino))
    registrar("T4d reproduccion", f"{n_png} cuadros PNG reconstruidos", ">= 5 cuadros desde el archivo",
              "APROBADA" if d else "FALLIDA", str(cuadros))
    return 0 if (a and b and c and d) else 1


if __name__ == "__main__":
    sys.exit(main())
