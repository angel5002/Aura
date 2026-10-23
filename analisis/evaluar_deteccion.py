"""Evalúa la detección de wifi_sensing contra la condición real de cada sesión.

Entrada: capturas de capturar.py (o de puente.py --guardar-crudo) con la salida del firmware wifi_sensing.
Se usan las líneas  HMS:{"type":"sample","peer":"AP","motion_status":..,"presence_someone_status":..,
"init_stage_name":..,...}  tal como las imprime send_channel_sample() en
esp-csi/examples/esp-radar/wifi_sensing_demo/main/web_serial_monitor.c.

Verdad de terreno (condicion_real: vacia / caminando / sentada_quieta), por orden de prioridad:
  1. C:\\aura\\datos\\crudos\\<id>_etiquetas.csv con columnas  t_rel_s,condicion
     (la condición rige desde ese segundo hasta la siguiente fila; t_rel_s se cuenta desde la primera
     línea de la captura, es decir, desde que capturar.py empieza a escribir). Permite medir latencias.
  2. La columna condicion_real de C:\\aura\\registro_sesiones.csv (una condición para toda la sesión).

Detectores evaluados:
  movimiento: motion_status          positivo = caminando           negativo = vacia, sentada_quieta
  presencia:  presence_someone_status positivo = caminando, sentada_quieta   negativo = vacia

Ejemplo:
    C:\\aura\\analisis\\.venv\\Scripts\\python.exe C:\\aura\\analisis\\evaluar_deteccion.py --sesiones S010 S011
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
REGISTRO = RAIZ / "registro_sesiones.csv"
DIR_CRUDOS = RAIZ / "datos" / "crudos"
DIR_PROCESADOS = RAIZ / "datos" / "procesados"

CONDICIONES = ("vacia", "caminando", "sentada_quieta")
DETECTORES = {
    # nombre: (campo HMS, condiciones que cuentan como positivo)
    "movimiento": ("motion_status", {"caminando"}),
    "presencia": ("presence_someone_status", {"caminando", "sentada_quieta"}),
}


def leer_hms(ruta: Path, peer: str) -> tuple[pd.DataFrame, dict]:
    """Devuelve las muestras 'sample' del par pedido con t_rel (s desde la primera línea de la captura)."""
    filas, n_hms, n_malas, t0 = [], 0, 0, None
    with open(ruta, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        next(r)  # t_pc_unix,linea
        for fila in r:
            if len(fila) < 2:
                continue
            t = float(fila[0])
            t0 = t if t0 is None else t0
            linea = fila[1]
            if not linea.startswith("HMS:"):
                continue
            n_hms += 1
            try:
                msg = json.loads(linea[4:])
            except json.JSONDecodeError:
                n_malas += 1
                continue
            if msg.get("type") != "sample" or msg.get("peer") != peer:
                continue
            filas.append({
                "t_rel": t - t0,
                "ts_ms": msg.get("ts_ms"),
                "motion_status": bool(msg.get("motion_status")),
                "presence_someone_status": bool(msg.get("presence_someone_status")),
                "presence_ready": bool(msg.get("presence_ready")),
                "init_stage_name": msg.get("init_stage_name"),
                "state_name": msg.get("state_name"),
            })
    info = {"lineas_hms": n_hms, "json_invalido": n_malas, "muestras_peer": len(filas)}
    return pd.DataFrame(filas), info


def leer_verdad(id_sesion: str, condicion_registro: str | None) -> pd.DataFrame:
    """Tramos de verdad: columnas t_ini, t_fin (s), condicion."""
    etiquetas = DIR_CRUDOS / f"{id_sesion}_etiquetas.csv"
    if etiquetas.exists():
        e = pd.read_csv(etiquetas).sort_values("t_rel_s").reset_index(drop=True)
        e["condicion"] = e["condicion"].str.strip()
        t_fin = list(e["t_rel_s"].iloc[1:]) + [np.inf]
        tramos = pd.DataFrame({"t_ini": e["t_rel_s"], "t_fin": t_fin, "condicion": e["condicion"]})
    elif condicion_registro:
        tramos = pd.DataFrame({"t_ini": [0.0], "t_fin": [np.inf], "condicion": [condicion_registro.strip()]})
    else:
        raise ValueError(f"{id_sesion}: no hay {etiquetas.name} ni condicion_real en el registro")
    malas = set(tramos["condicion"]) - set(CONDICIONES)
    if malas:
        raise ValueError(f"{id_sesion}: condiciones desconocidas {malas}; use {CONDICIONES}")
    return tramos


def en_rejilla(muestras: pd.DataFrame, tramos: pd.DataFrame, paso: float) -> pd.DataFrame:
    """Lleva las muestras a una rejilla de 'paso' segundos (último valor) y añade la condición real."""
    t = np.arange(muestras["t_rel"].iloc[0], muestras["t_rel"].iloc[-1], paso)
    idx = np.searchsorted(muestras["t_rel"].to_numpy(), t, side="right") - 1
    rej = muestras.iloc[idx].reset_index(drop=True)
    rej["t"] = t
    i_tramo = np.searchsorted(tramos["t_ini"].to_numpy(), t, side="right") - 1
    rej["condicion"] = np.where(i_tramo >= 0, tramos["condicion"].to_numpy()[np.clip(i_tramo, 0, None)], None)
    t_cambio = tramos["t_ini"].to_numpy()[np.clip(i_tramo, 0, None)]
    rej["seg_desde_cambio"] = np.where(i_tramo >= 0, t - t_cambio, np.nan)
    return rej[rej["condicion"].notna()].reset_index(drop=True)


def latencias(rej: pd.DataFrame, tramos: pd.DataFrame, campo: str, positivas: set) -> list[dict]:
    """Para cada cambio de verdad negativo<->positivo, segundos hasta que el detector lo refleja."""
    out = []
    for i in range(1, len(tramos)):
        antes, ahora = tramos["condicion"].iloc[i - 1] in positivas, tramos["condicion"].iloc[i] in positivas
        if antes == ahora:
            continue
        t0, t1 = tramos["t_ini"].iloc[i], tramos["t_fin"].iloc[i]
        tramo = rej[(rej["t"] >= t0) & (rej["t"] < t1)]
        acierto = tramo[tramo[campo] == ahora]
        out.append({
            "tipo": "inicio" if ahora else "fin",
            "t_cambio": t0,
            "latencia_s": float(acierto["t"].iloc[0] - t0) if len(acierto) else np.nan,
        })
    return out


def metricas(rej: pd.DataFrame, campo: str, positivas: set, margen: float) -> dict:
    r = rej[rej["seg_desde_cambio"] >= margen]
    real = r["condicion"].isin(positivas).to_numpy()
    det = r[campo].to_numpy(dtype=bool)
    vp, fn = int(np.sum(real & det)), int(np.sum(real & ~det))
    fp, vn = int(np.sum(~real & det)), int(np.sum(~real & ~det))
    return {
        "VP": vp, "FN": fn, "FP": fp, "VN": vn,
        "sensibilidad": vp / (vp + fn) if vp + fn else np.nan,
        "especificidad": vn / (vn + fp) if vn + fp else np.nan,
        "exactitud": (vp + vn) / len(r) if len(r) else np.nan,
    }


def figura(rej: pd.DataFrame, id_sesion: str, salida: Path):
    fig, ejes = plt.subplots(3, 1, figsize=(11, 4.5), sharex=True, height_ratios=[1.5, 1, 1])
    niveles = {c: i for i, c in enumerate(CONDICIONES)}
    ejes[0].step(rej["t"], rej["condicion"].map(niveles), where="post", color="k", lw=1.5)
    ejes[0].set_yticks(range(len(CONDICIONES)), CONDICIONES)
    ejes[0].set_ylim(-0.4, len(CONDICIONES) - 0.6)
    ejes[0].set_title(f"Sesión {id_sesion}: condición real (arriba) y detección (abajo)")
    for ax, campo, nombre, color in ((ejes[1], "motion_status", "movimiento", "C3"),
                                     (ejes[2], "presence_someone_status", "presencia", "C0")):
        ax.fill_between(rej["t"], rej[campo].astype(int), step="post", color=color, alpha=0.6)
        ax.set_yticks([0, 1], ["no", "sí"])
        ax.set_ylim(-0.1, 1.1)
        ax.set_ylabel(nombre)
    ejes[2].set_xlabel("Tiempo desde el inicio de la captura (s)")
    fig.tight_layout()
    fig.savefig(salida, dpi=120)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description="Evalúa la detección de actividad de wifi_sensing.")
    ap.add_argument("--sesiones", nargs="+", required=True, help="id_sesion del registro, p. ej. S010 S011")
    ap.add_argument("--peer", default="AP", help="Canal a evaluar: AP, MAC_1 o MAC_2 (defecto AP)")
    ap.add_argument("--paso", type=float, default=1.0, help="Rejilla de evaluación en segundos (defecto 1)")
    ap.add_argument("--margen", type=float, default=5.0,
                    help="Segundos tras cada cambio de condición excluidos de la matriz (defecto 5)")
    ap.add_argument("--incluir-calibracion", action="store_true",
                    help="Incluye muestras con init_stage distinto de STABLE (por defecto se excluyen)")
    args = ap.parse_args()

    registro = pd.read_csv(REGISTRO, dtype=str).fillna("")
    resumen, todas_lat, rejillas = [], [], []
    for sid in args.sesiones:
        fila = registro[registro["id_sesion"] == sid]
        archivo = fila["archivo_datos"].iloc[0] if len(fila) and fila["archivo_datos"].iloc[0] else f"{sid}.csv"
        ruta = Path(archivo) if Path(archivo).is_absolute() else DIR_CRUDOS / Path(archivo).name
        cond = fila["condicion_real"].iloc[0] if len(fila) and "condicion_real" in fila else ""
        if not ruta.exists():
            print(f"ERROR {sid}: no existe {ruta}")
            return 1

        muestras, info = leer_hms(ruta, args.peer)
        print(f"\n=== {sid} ({ruta.name}) ===")
        print(f"Líneas HMS: {info['lineas_hms']}  JSON inválido: {info['json_invalido']}  "
              f"muestras de {args.peer}: {info['muestras_peer']}")
        if muestras.empty:
            print("ERROR: sin muestras; ¿es una captura de wifi_sensing y el --peer es correcto?")
            return 1
        estable = muestras["init_stage_name"] == "STABLE"
        if not estable.any():
            print("Aviso: el detector nunca llegó a STABLE en esta captura.")
        else:
            print(f"Primer STABLE a los {muestras.loc[estable, 't_rel'].iloc[0]:.1f} s")
        if not args.incluir_calibracion:
            muestras = muestras[estable].reset_index(drop=True)
            if muestras.empty:
                continue

        tramos = leer_verdad(sid, cond)
        rej = en_rejilla(muestras, tramos, args.paso)
        rej["sesion"] = sid
        rejillas.append(rej)
        DIR_PROCESADOS.mkdir(parents=True, exist_ok=True)
        figura(rej, sid, DIR_PROCESADOS / f"{sid}_deteccion.png")

        for nombre, (campo, positivas) in DETECTORES.items():
            for lat in latencias(rej, tramos, campo, positivas):
                todas_lat.append({"sesion": sid, "detector": nombre, **lat})
            por_cond = rej.groupby("condicion")[campo].mean()
            print(f"  {nombre:<10} % de tiempo detectado por condición: "
                  + ", ".join(f"{c}={100 * v:.0f}%" for c, v in por_cond.items()))

    if not rejillas:
        print("No quedaron muestras para evaluar.")
        return 1
    total = pd.concat(rejillas, ignore_index=True)

    print(f"\n=== Resultado global ({len(rejillas)} sesión/es, rejilla {args.paso} s, margen {args.margen} s) ===")
    for nombre, (campo, positivas) in DETECTORES.items():
        m = metricas(total, campo, positivas, args.margen)
        resumen.append({"detector": nombre, **m})
        print(f"\n{nombre.upper()}  (positivo = {', '.join(sorted(positivas))})")
        print(f"                 detectado+   detectado-")
        print(f"  real positivo  {m['VP']:>10}   {m['FN']:>10}")
        print(f"  real negativo  {m['FP']:>10}   {m['VN']:>10}")
        print(f"  sensibilidad {m['sensibilidad']:.3f}   especificidad {m['especificidad']:.3f}   "
              f"exactitud {m['exactitud']:.3f}")
        lat = pd.DataFrame([l for l in todas_lat if l["detector"] == nombre])
        if lat.empty:
            print("  latencia: sin cambios de condición (use un archivo <id>_etiquetas.csv)")
        else:
            for tipo, g in lat.groupby("tipo"):
                ok = g["latencia_s"].dropna()
                txt = f"mediana {ok.median():.1f} s, máx {ok.max():.1f} s" if len(ok) else "nunca detectado"
                print(f"  latencia de {tipo}: {txt}  ({len(ok)}/{len(g)} cambios detectados)")

    nombre_ids = "_".join(args.sesiones)
    pd.DataFrame(resumen).to_csv(DIR_PROCESADOS / f"evaluacion_{nombre_ids}.csv", index=False)
    if todas_lat:
        pd.DataFrame(todas_lat).to_csv(DIR_PROCESADOS / f"latencias_{nombre_ids}.csv", index=False)
    print(f"\nResultados en {DIR_PROCESADOS} (evaluacion_{nombre_ids}.csv, <id>_deteccion.png)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
