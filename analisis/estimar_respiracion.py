"""Prueba de estimación de frecuencia respiratoria con CSI (sesiones con metrónomo).

Pasos:
 1. Carga la tabla (archivo crudo o *_leido.csv) y mide la tasa real de paquetes.
 2. Remuestrea la amplitud de cada subportadora a una frecuencia constante (interpolación lineal),
    porque el ESP32 no entrega paquetes a ritmo fijo.
 3. Elige las subportadoras con mayor variación (coeficiente de variación = desv. / media).
 4. Filtro pasabanda Butterworth de 0,1 a 0,7 Hz (6 a 42 rpm), sin desfase (sosfiltfilt).
 5. Promedia el espectro de las subportadoras elegidas y toma el pico dominante -> rpm.
 6. Guarda una figura en datos/procesados/<id>_respiracion.png.

Ejemplo:
    python estimar_respiracion.py ..\\datos\\procesados\\S001_leido.csv --metronomo-rpm 15
"""

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal

from leer_csi import cargar

RAIZ = Path(__file__).resolve().parent.parent
DIR_PROCESADOS = RAIZ / "datos" / "procesados"


def informe_tasa(t: np.ndarray) -> dict:
    dt = np.diff(t)
    dur = t[-1] - t[0]
    return {
        "paquetes": len(t),
        "duracion_s": dur,
        "tasa_media_hz": (len(t) - 1) / dur,
        "dt_mediana_ms": np.median(dt) * 1e3,
        "dt_desv_ms": np.std(dt) * 1e3,
        "dt_p95_ms": np.percentile(dt, 95) * 1e3,
        "dt_max_ms": dt.max() * 1e3,
        "huecos_mayores_1s": int(np.sum(dt > 1.0)),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Estima respiraciones por minuto a partir de CSI.")
    ap.add_argument("archivo", help="Archivo crudo (datos/crudos) o leído (datos/procesados/*_leido.csv)")
    ap.add_argument("--fs", type=float, default=20.0, help="Frecuencia de remuestreo en Hz (defecto 20)")
    ap.add_argument("--n-sub", type=int, default=10, help="Subportadoras a usar (defecto 10)")
    ap.add_argument("--banda", type=float, nargs=2, default=[0.1, 0.7], metavar=("F_MIN", "F_MAX"),
                    help="Banda del pasabanda en Hz (defecto 0.1 0.7)")
    ap.add_argument("--reloj", choices=["esp", "pc"], default="esp",
                    help="Base de tiempo: reloj del ESP32 (más preciso) o de la PC")
    ap.add_argument("--metronomo-rpm", type=float, help="Ritmo del metrónomo, para calcular el error")
    ap.add_argument("--salida", help="Ruta de la figura (por defecto datos/procesados/<id>_respiracion.png)")
    args = ap.parse_args()

    ruta = Path(args.archivo)
    id_sesion = ruta.stem.removesuffix("_leido")
    tabla = cargar(ruta)

    t = tabla["t_esp" if args.reloj == "esp" else "t_rel"].to_numpy(dtype=float)
    orden = np.argsort(t, kind="stable")
    tabla, t = tabla.iloc[orden].reset_index(drop=True), t[orden]
    unicos = np.concatenate([[True], np.diff(t) > 0])  # descarta marcas de tiempo repetidas
    tabla, t = tabla[unicos].reset_index(drop=True), t[unicos]
    t = t - t[0]

    tasa = informe_tasa(t)
    print("--- Tasa real de paquetes ---")
    print(f"Paquetes: {tasa['paquetes']}  Duración: {tasa['duracion_s']:.1f} s  "
          f"Tasa media: {tasa['tasa_media_hz']:.1f} Hz")
    print(f"Intervalo entre paquetes: mediana {tasa['dt_mediana_ms']:.1f} ms, desv. {tasa['dt_desv_ms']:.1f} ms, "
          f"p95 {tasa['dt_p95_ms']:.1f} ms, máx {tasa['dt_max_ms']:.0f} ms, huecos >1 s: {tasa['huecos_mayores_1s']}")
    if args.fs > tasa["tasa_media_hz"]:
        print(f"Aviso: fs={args.fs} Hz es mayor que la tasa real; se interpolará más de lo medido.")
    if tasa["duracion_s"] < 30:
        print("Aviso: menos de 30 s de datos; la resolución en frecuencia será pobre.")

    # Amplitud por subportadora; se descartan las nulas (guardas/DC) y las que tienen NaN.
    cols = [c for c in tabla.columns if c.startswith("amp_")]
    amp = tabla[cols].to_numpy(dtype=float)
    utiles = ~np.isnan(amp).any(axis=0) & (amp.mean(axis=0) > 1e-6)
    cols = [c for c, u in zip(cols, utiles) if u]
    amp = amp[:, utiles]
    if amp.shape[1] == 0:
        print("ERROR: no hay subportadoras con amplitud válida.")
        return 1

    # Remuestreo a fs constante.
    t_u = np.arange(0, t[-1], 1 / args.fs)
    amp_u = np.column_stack([np.interp(t_u, t, amp[:, k]) for k in range(amp.shape[1])])

    # Selección por coeficiente de variación (normaliza la ganancia de cada subportadora).
    cv = amp_u.std(axis=0) / amp_u.mean(axis=0)
    n_sub = min(args.n_sub, amp_u.shape[1])
    elegidas = np.argsort(cv)[::-1][:n_sub]
    print(f"Subportadoras elegidas ({n_sub}): {[cols[k].removeprefix('amp_') for k in elegidas]}")

    # Pasabanda.
    f_min, f_max = args.banda
    sos = signal.butter(4, [f_min, f_max], btype="bandpass", fs=args.fs, output="sos")
    x = amp_u[:, elegidas]
    x = (x - x.mean(axis=0)) / x.std(axis=0)
    try:
        x_f = signal.sosfiltfilt(sos, x, axis=0)
    except ValueError as e:
        print(f"ERROR al filtrar (¿registro demasiado corto?): {e}")
        return 1

    # Espectro promedio (ventana de Hann, relleno con ceros para afinar la ubicación del pico).
    n = len(x_f)
    nfft = int(2 ** np.ceil(np.log2(n * 8)))
    ventana = signal.windows.hann(n)[:, None]
    espectro = np.abs(np.fft.rfft(x_f * ventana, n=nfft, axis=0)) ** 2
    espectro = espectro.mean(axis=1)
    f = np.fft.rfftfreq(nfft, 1 / args.fs)
    en_banda = (f >= f_min) & (f <= f_max)
    f_pico = f[en_banda][np.argmax(espectro[en_banda])]
    rpm = f_pico * 60
    resolucion_rpm = 60 / t_u[-1]

    print("--- Resultado ---")
    print(f"Frecuencia dominante: {f_pico:.3f} Hz = {rpm:.1f} respiraciones/min "
          f"(resolución nativa ±{resolucion_rpm / 2:.1f} rpm)")
    if args.metronomo_rpm:
        print(f"Metrónomo: {args.metronomo_rpm:.1f} rpm  ->  error {rpm - args.metronomo_rpm:+.1f} rpm")

    # Figura.
    salida = Path(args.salida) if args.salida else DIR_PROCESADOS / f"{id_sesion}_respiracion.png"
    salida.parent.mkdir(parents=True, exist_ok=True)
    fig, ejes = plt.subplots(3, 1, figsize=(11, 10))

    ax = ejes[0]
    ax.plot(t[1:], np.diff(t) * 1e3, ".", ms=1.5)
    ax.set_title(f"Intervalo entre paquetes — tasa media {tasa['tasa_media_hz']:.1f} Hz, "
                 f"desv. {tasa['dt_desv_ms']:.1f} ms (reloj {args.reloj})")
    ax.set_xlabel("Tiempo (s)")
    ax.set_ylabel("Δt (ms)")
    ax.set_yscale("log")

    ax = ejes[1]
    for j in range(x_f.shape[1]):
        ax.plot(t_u, x_f[:, j], lw=0.6, alpha=0.5)
    ax.plot(t_u, x_f.mean(axis=1), color="k", lw=1.5, label="promedio")
    ax.set_title(f"Amplitud filtrada {f_min}–{f_max} Hz ({n_sub} subportadoras, z-score)")
    ax.set_xlabel("Tiempo (s)")
    ax.legend(loc="upper right")

    ax = ejes[2]
    ax.plot(f * 60, espectro, lw=1)
    ax.axvline(rpm, color="C3", ls="--", label=f"pico {rpm:.1f} rpm")
    if args.metronomo_rpm:
        ax.axvline(args.metronomo_rpm, color="C2", ls=":", label=f"metrónomo {args.metronomo_rpm:.1f} rpm")
    ax.set_xlim(0, f_max * 60 * 1.3)
    ax.set_title("Espectro promedio")
    ax.set_xlabel("Respiraciones por minuto")
    ax.set_ylabel("Potencia (u.a.)")
    ax.legend(loc="upper right")

    fig.suptitle(f"Sesión {id_sesion}")
    fig.tight_layout()
    fig.savefig(salida, dpi=120)
    print(f"Figura guardada en: {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
