"""D9 - Buffers de recepcion WiFi bajo carga.

Mientras corre, genera trafico en la red desde OTRO equipo (video en streaming o iperf). Registra el heap
minimo y el intervalo de ts_ms de la telemetria y agrega una fila a salida\\d9_comparacion.csv con la
etiqueta de la configuracion (rx_buf de la telemetria). Criterio: heap minimo >= 50 KB con 128 buffers.
Si queda por debajo, se graba la variante build_rx64 por OTA, se repite y se decide con la tabla.
"""

import argparse
import csv
import sys

from comun import SALIDA, Coleccion, ip_placa, mediana, percentil, recibir_en_hilo
from registrar import registrar


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ip")
    ap.add_argument("--minutos", type=float, default=10)
    ap.add_argument("--id-sesion", default="D9")
    a = ap.parse_args()
    ip = ip_placa(a.ip)
    input("Inicia el trafico en otro equipo (video o iperf) y pulsa Enter...")
    col = Coleccion()
    h, res = recibir_en_hilo(ip, a.id_sesion, a.minutos * 60, col)
    h.join()
    tel = [t for _, t in col.telemetria]
    if not tel:
        registrar("D9 buffers WiFi", "sin telemetria", ">= 50 KB", "FALLIDA")
        return 1
    heap_min = min(t["heap_minimo"] for t in tel)
    rx = tel[-1].get("rx_buf")
    med = mediana([t["ts_mediana_ms"] for t in tel if t.get("n_intervalos")])
    p95 = percentil([t["ts_p95_ms"] for t in tel if t.get("n_intervalos")], 95)
    SALIDA.mkdir(exist_ok=True)
    tabla = SALIDA / "d9_comparacion.csv"
    nuevo = not tabla.exists()
    with open(tabla, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        if nuevo:
            w.writerow(["sesion", "rx_buf", "heap_min_B", "ts_mediana_ms", "ts_p95_ms", "perdida_local_pct"])
        w.writerow([a.id_sesion, rx, heap_min, f"{med:.1f}", f"{p95:.1f}", f"{res['perdida_pct']:.2f}"])
    ok = heap_min >= 50 * 1024
    registrar(f"D9 buffers WiFi (rx_buf={rx})", f"heap minimo {heap_min} B; ts mediana {med:.1f} ms, p95 {p95:.1f} ms",
              ">= 51200 B con carga", "APROBADA" if ok else "FALLIDA",
              "" if ok else "repetir con build_rx64 por OTA y comparar en salida\\d9_comparacion.csv")
    print(open(tabla, encoding="utf-8").read())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
