"""K002 - Prueba de cruces del enlace placa B - Huawei (docs/ensayos/k002_cruces.md).

Lee la captura del celular (<id>_local.csv, ya pasada a datos/crudos) y evalua el detector de MOVIMIENTO (campo
motion_status de las muestras, sin la retencion de 10 s del estado de la placa) contra el horario de cruces fijado
antes. t = 0 es el primer datagrama de la captura (t_pc_unix del celular).

Horario: 10 cruces de ida y vuelta en t = 30, 55, 80, ..., 255 s (cada 25 s): del Punto 1 (a 0,80 m de la linea
Huawei-B) a la marca de vuelta (a 0,20 m del otro lado) y de regreso; antes, entre y despues, la persona de pie y
quieta en el Punto 1 (montaje definido por Deisy el 27/10/2026). Criterios (fijados antes de ejecutar; montaje y nombre del criterio de falsas alarmas: Deisy, 27/10/2026):
  validez:   captura >= 290 s, 0 huecos > 5 s, sin reinicios de la placa (si no: NO EJECUTADA);
  deteccion: >= 8 de 10 cruces con algun motion_status = true en [t_k - 3 s, t_k + 8 s];
  persona quieta a 0,80 m del enlace: tiempo en MOVIMIENTO <= 5 % (umbral de prototipo) en las ventanas tranquilas ([5, 27] s, [t_k + 10, t_k+1 - 3] s y
             [265, 290] s).

  python pruebas\\k002_cruces.py C:\\aura\\datos\\crudos\\K002_local.csv
"""

import argparse
import csv
import json
import sys
from pathlib import Path

from registrar import registrar

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aura_proto import parsear_datagrama  # noqa: E402
from receptor_local import ContadorSecuencia, ts_muestra  # noqa: E402

CRUCES_S = [30 + 25 * k for k in range(10)]       # 30, 55, ..., 255
ANTES_S, DESPUES_S = 3.0, 8.0                      # ventana de deteccion alrededor de cada cruce
TRANQUILO_TRAS_S, TRANQUILO_ANTES_S = 10.0, 3.0    # ventanas tranquilas entre cruces
INICIO_TRANQUILO, FIN_TRANQUILO = (5.0, 27.0), (265.0, 290.0)
MIN_DURACION_S, HUECO_MAX_S = 290.0, 5.0
MIN_DETECTADOS, MAX_FALSAS_PCT = 8, 5.0
MAX_TRAMO_S = 1.0                                  # una muestra no rige mas de 1 s


def leer(ruta: Path):
    muestras, t0, t_prev, huecos, t_fin = [], None, None, 0, None
    cont = ContadorSecuencia()
    with open(ruta, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        next(r, None)
        for fila in r:
            d = parsear_datagrama(fila[1]) if len(fila) > 1 else None
            if d is None:
                continue
            t = float(fila[0])
            t0 = t if t0 is None else t0
            huecos += t_prev is not None and t - t_prev > HUECO_MAX_S
            t_prev = t_fin = t
            cont.agregar(d.seq, ts_muestra(d))
            if d.tipo == "hms" and '"type":"sample"' in d.cuerpo:
                m = json.loads(d.cuerpo)
                if "motion_status" in m:
                    muestras.append((t - t0, bool(m["motion_status"])))
    res = cont.resumen(final=True)
    return muestras, (t_fin - t0) if t0 is not None else 0.0, huecos, res["epocas"] - 1


def pct_movimiento(muestras, a: float, b: float) -> tuple[float, float]:
    """(segundos en movimiento, segundos cubiertos) dentro de [a, b]."""
    mov = tot = 0.0
    for (t, m), (t1, _) in zip(muestras, muestras[1:]):
        ini, fin = max(t, a), min(t + min(t1 - t, MAX_TRAMO_S), b)
        if fin > ini:
            tot += fin - ini
            mov += (fin - ini) if m else 0.0
    return mov, tot


def main() -> int:
    ap = argparse.ArgumentParser(description="K002: cruces del enlace (criterios fijados antes).")
    ap.add_argument("archivo", type=Path)
    ap.add_argument("--no-registrar", action="store_true", help="solo imprime (pruebas del script)")
    a = ap.parse_args()
    muestras, dur, huecos, reinicios = leer(a.archivo)
    print(f"{a.archivo.name}: {dur:.1f} s, {len(muestras)} muestras, huecos > {HUECO_MAX_S:g} s: {huecos}, "
          f"reinicios: {reinicios}")
    detectados, latencias = 0, []
    for k, tc in enumerate(CRUCES_S, 1):
        positivos = [t for t, m in muestras if m and tc - ANTES_S <= t <= tc + DESPUES_S]
        ok = bool(positivos)
        detectados += ok
        if ok:
            latencias.append(positivos[0] - tc)
        print(f"  cruce {k:2d} en {tc:3d} s: {'DETECTADO' if ok else 'no detectado'}"
              + (f" (primer positivo a {positivos[0] - tc:+.1f} s)" if ok else ""))
    ventanas = [INICIO_TRANQUILO] + [(tc + TRANQUILO_TRAS_S, tn - TRANQUILO_ANTES_S)
                                     for tc, tn in zip(CRUCES_S, CRUCES_S[1:])] + [FIN_TRANQUILO]
    mov = tot = 0.0
    for v in ventanas:
        m, t = pct_movimiento(muestras, *v)
        mov, tot = mov + m, tot + t
    falsas = 100 * mov / tot if tot else float("nan")
    print(f"  persona quieta a 0,80 m del enlace (ventanas tranquilas): {tot:.1f} s cubiertos, {falsas:.2f} % en MOVIMIENTO")
    valido = dur >= MIN_DURACION_S and huecos == 0 and reinicios == 0
    ok_det, ok_fal = detectados >= MIN_DETECTADOS, falsas <= MAX_FALSAS_PCT
    estado = "NO EJECUTADA" if not valido else ("APROBADA" if ok_det and ok_fal else "FALLIDA")
    lat = (f"; latencia mediana {sorted(latencias)[len(latencias) // 2]:+.1f} s" if latencias else "")
    valor = f"{detectados}/10 cruces detectados; {falsas:.2f} % en MOVIMIENTO con la persona quieta a 0,80 m del enlace" + lat
    criterio = (f">= {MIN_DETECTADOS}/10 detectados en [-{ANTES_S:g}, +{DESPUES_S:g}] s y <= {MAX_FALSAS_PCT:g} % "
                f"en MOVIMIENTO con la persona quieta a 0,80 m del enlace")
    notas = f"{a.archivo.name}; {dur:.0f} s; huecos {huecos}; reinicios {reinicios}"
    if not valido:
        notas += f"; invalida (requiere >= {MIN_DURACION_S:g} s, 0 huecos y 0 reinicios)"
    print(f"Resultado: {estado} ({valor})")
    if not a.no_registrar:
        registrar("K002 cruces del enlace", valor, criterio, estado, notas)
    return 0 if estado == "APROBADA" else 1


if __name__ == "__main__":
    sys.exit(main())
