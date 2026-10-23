"""D10 - Diferencia entre el reloj de la placa (SNTP) y el de la PC.

50 intercambios "TIEMPO <t_pc_us>" -> "TIEMPO <t_pc_us> <t_placa_us> <sntp_ok>" por la via local.
Desfase estilo NTP: t_placa - (t_envio + t_recepcion) / 2, con los 10 de menor ida y vuelta.
Criterio: |desfase| < 100 ms. Depende de que el reloj de Windows este sincronizado: el script muestra
el estado de w32tm (solo lectura) para interpretarlo.
"""

import argparse
import socket
import statistics
import subprocess
import sys
import time

from comun import ip_placa
from registrar import registrar
from aura_proto import PUERTO_DATOS


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ip")
    ap.add_argument("--n", type=int, default=50)
    a = ap.parse_args()
    ip = ip_placa(a.ip)
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(1)
    muestras = []
    sntp_ok = None
    for _ in range(a.n):
        t1 = time.time_ns() // 1000
        s.sendto(f"TIEMPO {t1}".encode(), (ip, PUERTO_DATOS))
        try:
            datos, _ = s.recvfrom(256)
        except socket.timeout:
            continue
        t2 = time.time_ns() // 1000
        p = datos.decode().split()
        if len(p) == 4 and p[0] == "TIEMPO" and int(p[1]) == t1:
            tp = int(p[2])
            sntp_ok = p[3] == "1"
            muestras.append(((t2 - t1) / 1000, (tp - (t1 + t2) / 2) / 1000))
        time.sleep(0.1)
    try:
        w32 = subprocess.run(["w32tm", "/query", "/status"], capture_output=True, text=True, timeout=10).stdout
        fuente = next((l.strip() for l in w32.splitlines() if "Source" in l or "Origen" in l), "w32tm sin datos")
    except Exception:
        fuente = "w32tm no disponible"
    if not muestras:
        registrar("D10 SNTP", "sin respuestas", "< 100 ms", "FALLIDA")
        return 1
    mejores = sorted(muestras)[:10]
    desfase = statistics.median(d for _, d in mejores)
    rtt = statistics.median(r for r, _ in mejores)
    ok = bool(sntp_ok) and abs(desfase) < 100
    registrar("D10 sincronia SNTP", f"desfase {desfase:+.1f} ms (ida y vuelta {rtt:.1f} ms, {len(muestras)} respuestas, "
              f"sntp_ok={sntp_ok})", "|desfase| < 100 ms", "APROBADA" if ok else "FALLIDA", f"reloj PC: {fuente}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
