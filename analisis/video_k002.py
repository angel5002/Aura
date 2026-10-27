"""Clip ilustrativo de K002 (40-60 s, MP4 1080p 30 fps) sincronizado con los datos reales del detector.

- Lee datos/crudos/K002_local.csv (solo lectura; no modifica datos). t = 0 es el primer datagrama, como en
  analisis/pruebas/k002_cruces.py.
- Escena 3D (matplotlib): habitacion, Huawei y placa B a 2 m y a la misma altura (1 m); entre ellos un elipsoide
  estrecho (radio central 0,28 m) cuyo color y brillo siguen la senal REAL del detector: rojo si motion_status es
  true (MOVIMIENTO), azul si no; brillo segun smooth_scaled relativo al umbral de entrada.
- Persona: figura simple cuya posicion sale del PROTOCOLO (no del WiFi): quieta en el Punto 1 (0,80 m de la linea) y
  cruce de ida y vuelta hasta la marca de vuelta (0,20 m del otro lado) en cada horario 30, 55, ..., 255 s.
- Debajo: smooth_scaled real con sus umbrales, bandas de MOVIMIENTO, marcas de cada horario y el contador
  "cruces detectados: n/10" (criterio de K002: algun positivo en [t_k - 3, t_k + 8] s).
- Tiempo: cada cruce en tiempo real (x1) de t_k - 1,5 a t_k + 3 s; el resto acelerado x20 (indicado en pantalla).

    python video_k002.py                                   (MP4 en datos/procesados/video_K002/)
    python video_k002.py --cuadros 28.5 30.5 100           (solo PNG de esos instantes, para revisar)
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.animation import FFMpegWriter  # noqa: E402

from aura_proto import parsear_datagrama  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "datos" / "crudos" / "K002_local.csv"
SALIDA = RAIZ / "datos" / "procesados" / "video_K002"
FFMPEG = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe"

CRUCES = [30 + 25 * k for k in range(10)]          # protocolo K002
FIN_HORARIO = 300.0
ANTES_S, DESPUES_S = 3.0, 8.0                      # ventana de deteccion del criterio de K002
VIVO_ANTES, VIVO_DESPUES = 1.5, 3.0                # tramo en tiempo real alrededor de cada cruce
ACELERADO = 20.0
FPS = 30
ROTULO = ("Animación ilustrativa sincronizada con datos reales de la prueba K002 (27/10/2026). "
          "La posición de la persona proviene del protocolo de la prueba, no del WiFi.")

# Geometria (m): enlace sobre el eje x a 1 m de altura; lado libre y < 0, lado de la cama y > 0
HUAWEI, PLACA = np.array([0.0, 0.0, 1.0]), np.array([2.0, 0.0, 1.0])
PUNTO1_Y, VUELTA_Y, PASO_X = -0.80, 0.20, 1.0      # marcas frente a la mitad de la linea
CELULAR = np.array([1.4, 1.1, 1.0])
SALIDA_CRUCE, LLEGADA_MARCA, REGRESO = -0.5, 1.0, 2.5   # s respecto de t_k (supuesto del protocolo: ~3 s)


def leer_muestras(ruta: Path) -> dict:
    t, mov, suave, entrada, salida = [], [], [], [], []
    t0 = None
    with open(ruta, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        next(r, None)
        for fila in r:
            d = parsear_datagrama(fila[1]) if len(fila) > 1 else None
            if d is None:
                continue
            tt = float(fila[0])
            t0 = tt if t0 is None else t0
            if d.tipo == "hms" and '"type":"sample"' in d.cuerpo:
                m = json.loads(d.cuerpo)
                t.append(tt - t0)
                mov.append(bool(m.get("motion_status")))
                suave.append(m.get("smooth_scaled", 0) / 1e6)
                entrada.append(m.get("enter_level_scaled", 0) / 1e6)
                salida.append(m.get("exit_level_scaled", 0) / 1e6)
    return {k: np.array(v) for k, v in (("t", t), ("mov", mov), ("suave", suave), ("entrada", entrada),
                                         ("salida", salida))}


def primer_positivo(d: dict) -> list:
    """Instante del primer motion_status = true en [t_k - 3, t_k + 8] para cada cruce (None si no hay)."""
    out = []
    for tc in CRUCES:
        sel = (d["t"] >= tc - ANTES_S) & (d["t"] <= tc + DESPUES_S) & d["mov"]
        out.append(float(d["t"][sel][0]) if sel.any() else None)
    return out


def linea_de_tiempo() -> list:
    """Lista de (t_prueba, velocidad) para cada cuadro del video."""
    tramos, t = [], 0.0
    for tc in CRUCES:
        a, b = tc - VIVO_ANTES, tc + VIVO_DESPUES
        tramos.append((t, a, ACELERADO))
        tramos.append((a, b, 1.0))
        t = b
    tramos.append((t, FIN_HORARIO, ACELERADO))
    cuadros = []
    for a, b, v in tramos:
        n = int(round((b - a) / v * FPS))
        cuadros += [(a + i * v / FPS, v) for i in range(n)]
    return cuadros


def posicion_persona(t: float):
    """(x, y, fase_de_paso) de la persona segun el protocolo."""
    for tc in CRUCES:
        s = t - tc
        if SALIDA_CRUCE <= s < LLEGADA_MARCA:
            f = (s - SALIDA_CRUCE) / (LLEGADA_MARCA - SALIDA_CRUCE)
            return PASO_X, PUNTO1_Y + f * (VUELTA_Y - PUNTO1_Y), s
        if LLEGADA_MARCA <= s < REGRESO:
            f = (s - LLEGADA_MARCA) / (REGRESO - LLEGADA_MARCA)
            return PASO_X, VUELTA_Y + f * (PUNTO1_Y - VUELTA_Y), s
    return PASO_X, PUNTO1_Y, None


def figura_humana(x, y, fase):
    """Segmentos 3D de una figura de palitos de 1,65 m (piernas y brazos oscilan al caminar)."""
    ang = 0.45 * np.sin(fase * 2 * np.pi * 1.4) if fase is not None else 0.0
    cadera, hombros, cabeza = 0.90, 1.42, 1.56
    seg = [((x, y, cadera), (x, y, hombros)),                                      # tronco
           ((x, y, cadera), (x, y + 0.45 * np.sin(ang), 0.0)),                     # pierna 1
           ((x, y, cadera), (x, y - 0.45 * np.sin(ang), 0.0)),                     # pierna 2
           ((x, y, hombros), (x - 0.18, y - 0.30 * np.sin(ang), 0.95)),            # brazo 1
           ((x, y, hombros), (x + 0.18, y + 0.30 * np.sin(ang), 0.95))]            # brazo 2
    return seg, (x, y, cabeza)


def main() -> int:
    ap = argparse.ArgumentParser(description="Clip ilustrativo de K002 sincronizado con los datos reales.")
    ap.add_argument("--cuadros", type=float, nargs="*", help="solo PNG de estos instantes de la prueba (s)")
    a = ap.parse_args()
    d = leer_muestras(ENTRADA)
    if len(d["t"]) == 0:
        print(f"ERROR: sin muestras en {ENTRADA}")
        return 1
    primeros = primer_positivo(d)

    fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor="white")
    ax3 = fig.add_axes([0.0, 0.28, 0.72, 0.70], projection="3d")
    axs = fig.add_axes([0.05, 0.08, 0.90, 0.19])
    ax3.set_xlim(-0.6, 2.6); ax3.set_ylim(-1.6, 1.6); ax3.set_zlim(0, 2.4)
    ax3.set_box_aspect((3.2, 3.2, 2.4), zoom=1.0); ax3.view_init(elev=58, azim=-90); ax3.set_axis_off()

    # Habitacion (aristas), suelo y objetos fijos
    xs, ys, zs = (-0.6, 2.6), (-1.6, 1.6), (0.0, 2.4)
    for xa in xs:
        for ya in ys:
            ax3.plot([xa, xa], [ya, ya], zs, color="#bbbbbb", lw=0.8)
    for za in zs:
        ax3.plot([xs[0], xs[1], xs[1], xs[0], xs[0]], [ys[0], ys[0], ys[1], ys[1], ys[0]], [za] * 5,
                 color="#bbbbbb", lw=0.8)
    for xa in np.arange(-0.5, 2.6, 0.5):                                   # cuadricula del suelo (0,5 m)
        ax3.plot([xa, xa], ys, [0, 0], color="#e4e0d8", lw=0.6)
    for ya in np.arange(-1.5, 1.6, 0.5):
        ax3.plot(xs, [ya, ya], [0, 0], color="#e4e0d8", lw=0.6)
    ax3.plot([HUAWEI[0], PLACA[0]], [0, 0], [0, 0], color="#999999", lw=1.2, ls=":")   # proyeccion del enlace
    for p, nombre, color in ((HUAWEI, "Huawei (router)", "#333333"), (PLACA, "placa B", "#1f6f3f")):
        ax3.scatter(*p, s=260, marker="s", color=color, depthshade=False)
        ax3.text(p[0], p[1], p[2] + 0.22, nombre, ha="center", fontsize=15, color=color)
    ax3.plot([HUAWEI[0], PLACA[0]], [0, 0], [1.0, 1.0], color="#555555", lw=1, ls="--")
    ax3.scatter(*CELULAR, s=90, marker="s", color="#7a5c00", depthshade=False)
    ax3.text(CELULAR[0], CELULAR[1], CELULAR[2] + 0.15, "celular (receptor)", ha="center", fontsize=12,
             color="#7a5c00")
    for yy, nombre in ((PUNTO1_Y, "Punto 1 (0,80 m)"), (VUELTA_Y, "marca de vuelta (0,20 m)")):
        ax3.scatter(PASO_X, yy, 0.0, s=70, marker="x", color="#444444", depthshade=False)
        ax3.text(PASO_X + 0.12, yy, 0.02, nombre, fontsize=11, color="#444444")

    # Elipsoide del enlace (semieje 1 m a lo largo de la linea, radio central 0,28 m)
    u, v = np.meshgrid(np.linspace(0, 2 * np.pi, 40), np.linspace(0, np.pi, 20))
    ex = 1.0 + 1.0 * np.cos(u) * np.sin(v)
    ey = 0.28 * np.sin(u) * np.sin(v)
    ez = 1.0 + 0.28 * np.cos(v)
    elipsoide = ax3.plot_surface(ex, ey, ez, color="#2060d0", alpha=0.3, linewidth=0, shade=False)

    # Persona (palitos + cabeza)
    lineas = [ax3.plot([], [], [], color="#222222", lw=4)[0] for _ in range(5)]
    cabeza = ax3.plot([], [], [], "o", color="#222222", ms=18)[0]

    # Panel de la senal real
    axs.plot(d["t"], d["suave"], color="black", lw=0.8, label="señal del detector (smooth, real)")
    axs.plot(d["t"], d["entrada"], color="#d62728", lw=0.8, ls="--", label="umbral de entrada")
    axs.plot(d["t"], d["salida"], color="#2ca02c", lw=0.8, ls=":", label="umbral de salida")
    techo = float(d["suave"].max()) * 1.08
    axs.fill_between(d["t"], 0, techo, where=d["mov"], color="#d62728", alpha=0.35, step="post", lw=0,
                     label="MOVIMIENTO (motion_status)")
    for k, tc in enumerate(CRUCES, 1):
        axs.axvline(tc, color="#555555", lw=0.8, ls="--")
        axs.text(tc, techo * 0.97, f"{k}", ha="center", va="top", fontsize=10, color="#555555")
    axs.set_xlim(0, FIN_HORARIO); axs.set_ylim(0, techo)
    axs.set_xlabel("tiempo de la prueba (s); líneas discontinuas = horario de cada cruce (protocolo)", fontsize=12)
    axs.set_yticks([])
    axs.legend(loc="lower left", bbox_to_anchor=(0.0, 1.0), fontsize=11, ncol=4, frameon=False)
    cursor = axs.axvline(0, color="#1f77b4", lw=2)

    fig.text(0.5, 0.012, ROTULO, ha="center", va="bottom", fontsize=14, style="italic", color="#333333")
    titulo = fig.text(0.74, 0.90, "", fontsize=30, weight="bold", va="top")
    contador = fig.text(0.74, 0.80, "", fontsize=26, va="top", color="#222222")
    reloj = fig.text(0.74, 0.72, "", fontsize=20, va="top", color="#333333")
    velocidad = fig.text(0.74, 0.665, "", fontsize=20, va="top", weight="bold")
    fig.text(0.74, 0.58, "Color del elipsoide (dato real del detector):\nrojo = MOVIMIENTO   azul = quieto\n"
             "brillo = señal / umbral de entrada", fontsize=14, va="top", color="#333333")
    fig.text(0.74, 0.46, "K002: 10 cruces de ida y vuelta (30, 55, …, 255 s);\n"
             "entre cruces, persona quieta en el Punto 1.\nFirmware 0.1.3.", fontsize=13, va="top",
             color="#555555")

    def dibujar(t: float, v: float):
        i = max(0, int(np.searchsorted(d["t"], t, side="right")) - 1)
        mov = bool(d["mov"][i])
        brillo = float(np.clip(d["suave"][i] / max(d["entrada"][i], 1e-9), 0.0, 1.4) / 1.4)
        if mov:
            elipsoide.set_facecolor((0.85, 0.10, 0.10, 0.30 + 0.55 * brillo))
        else:
            elipsoide.set_facecolor((0.13, 0.38, 0.82, 0.12 + 0.35 * brillo))
        x, y, fase = posicion_persona(t)
        seg, c = figura_humana(x, y, fase)
        for ln, ((x1, y1, z1), (x2, y2, z2)) in zip(lineas, seg):
            ln.set_data_3d([x1, x2], [y1, y2], [z1, z2])
        cabeza.set_data_3d([c[0]], [c[1]], [c[2]])
        cursor.set_xdata([t, t])
        n = sum(1 for p in primeros if p is not None and p <= t)
        titulo.set_text("MOVIMIENTO" if mov else "quieto")
        titulo.set_color("#c0151a" if mov else "#1f4fa8")
        contador.set_text(f"cruces detectados: {n}/10")
        reloj.set_text(f"t = {t:6.1f} s de la prueba")
        velocidad.set_text("tiempo real (×1)" if v == 1.0 else f"tramo tranquilo acelerado ×{v:g}")
        velocidad.set_color("#2a7a2a" if v == 1.0 else "#a05a00")

    SALIDA.mkdir(parents=True, exist_ok=True)
    if a.cuadros:
        for t in a.cuadros:
            dibujar(t, 1.0)
            ruta = SALIDA / f"cuadro_{t:06.1f}.png"
            fig.savefig(ruta, dpi=100)
            print(f"PNG: {ruta}")
        return 0

    cuadros = linea_de_tiempo()
    print(f"{len(cuadros)} cuadros = {len(cuadros) / FPS:.1f} s de video; detectados "
          f"{sum(p is not None for p in primeros)}/10")
    plt.rcParams["animation.ffmpeg_path"] = str(FFMPEG)
    destino = SALIDA / "K002_animacion_1080p30.mp4"
    escritor = FFMpegWriter(fps=FPS, codec="libx264", bitrate=8000,
                            extra_args=["-pix_fmt", "yuv420p", "-preset", "medium"])
    with escritor.saving(fig, str(destino), dpi=100):
        for j, (t, v) in enumerate(cuadros):
            dibujar(t, v)
            escritor.grab_frame()
            if j % 150 == 0:
                print(f"  cuadro {j}/{len(cuadros)} (t = {t:.1f} s)", flush=True)
    print(f"MP4: {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
