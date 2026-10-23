"""Convierte un archivo crudo de capturar.py en una tabla de CSI.

Formato de entrada (verificado en esp-csi/examples/get-started/csi_recv/main/app_main.c,
rama CONFIG_IDF_TARGET_ESP32C5, y en tools/csi_data_read_parse.py):

    CSI_DATA,seq,mac,rssi,rate,noise_floor,fft_gain,agc_gain,channel,
    local_timestamp,sig_len,rx_format,len,first_word,"[v0,v1,v2,...]"

- `len` = cantidad de valores en el arreglo (2 por subportadora).
- Cada subportadora k viene como (imaginario, real): v[2k] = Im, v[2k+1] = Re.
  El parser oficial lo arma igual: complex(raw[2k+1], raw[2k]).
- `first_word` = 1 indica que los primeros 4 bytes (2 subportadoras) no son válidos.
- `local_timestamp` = rx_ctrl->timestamp del ESP32 en microsegundos (uint32 impreso con %d).

Salida: tabla con t_pc, t_esp, metadatos, amp_000..amp_N y fase_000..fase_N (rad, sin desenrollar).

Ejemplo:
    python leer_csi.py ..\\datos\\crudos\\S001.csv
"""

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
DIR_PROCESADOS = RAIZ / "datos" / "procesados"

# Nombres de campos tal como los imprime csi_recv (mismos que DATA_COLUMNS_NAMES* del parser oficial).
COLUMNAS_C5C6 = ["type", "seq", "mac", "rssi", "rate", "noise_floor", "fft_gain", "agc_gain",
                 "channel", "local_timestamp", "sig_len", "rx_format", "len", "first_word", "data"]
COLUMNAS_OTROS = ["type", "seq", "mac", "rssi", "rate", "sig_mode", "mcs", "bandwidth", "smoothing",
                  "not_sounding", "aggregation", "stbc", "fec_coding", "sgi", "noise_floor", "ampdu_cnt",
                  "channel", "secondary_channel", "local_timestamp", "ant", "sig_len", "rx_format",
                  "len", "first_word", "data"]
CAMPOS_ENTEROS = ["seq", "rssi", "rate", "noise_floor", "fft_gain", "agc_gain", "channel",
                  "local_timestamp", "sig_len", "rx_format", "len", "first_word"]


def _parsear_linea(linea: str):
    """Devuelve (dict de metadatos, lista de valores) o lanza ValueError con el motivo."""
    i = linea.find("CSI_DATA")
    if i == -1:
        raise ValueError("sin CSI_DATA")
    campos = next(csv.reader([linea[i:]]))
    if len(campos) == len(COLUMNAS_C5C6):
        nombres = COLUMNAS_C5C6
    elif len(campos) == len(COLUMNAS_OTROS):
        nombres = COLUMNAS_OTROS
    else:
        raise ValueError(f"número de campos inesperado ({len(campos)})")
    reg = dict(zip(nombres, campos))
    try:
        valores = json.loads(reg.pop("data"))
    except json.JSONDecodeError:
        raise ValueError("arreglo de datos incompleto")
    meta = {"mac": reg["mac"]}
    for c in CAMPOS_ENTEROS:
        if c in reg:
            meta[c] = int(reg[c])
    if meta["len"] != len(valores):
        raise ValueError(f"len={meta['len']} pero llegaron {len(valores)} valores")
    if len(valores) % 2:
        raise ValueError("cantidad impar de valores")
    return meta, valores


def leer_crudo(ruta):
    """Lee un archivo de capturar.py. Devuelve (meta: DataFrame, csi: ndarray complejo [paquetes, subport.], informe)."""
    filas, vectores = [], []
    motivos = Counter()
    n_total = n_no_csi = 0
    with open(ruta, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        next(r)  # encabezado t_pc_unix,linea
        for fila in r:
            n_total += 1
            if len(fila) < 2 or "CSI_DATA" not in fila[1]:
                n_no_csi += 1
                continue
            try:
                meta, valores = _parsear_linea(fila[1])
            except (ValueError, StopIteration) as e:
                motivos[str(e)] += 1
                continue
            meta["t_pc"] = float(fila[0])
            filas.append(meta)
            vectores.append(valores)

    if not filas:
        raise RuntimeError(f"{ruta}: no hay líneas CSI_DATA válidas (descartadas: {dict(motivos)})")

    # Si hay paquetes de distinto largo (p. ej. HT20 y HT40 mezclados), se queda con el más frecuente.
    largos = Counter(len(v) for v in vectores)
    largo = largos.most_common(1)[0][0]
    if len(largos) > 1:
        motivos[f"largo distinto de {largo}"] += sum(n for l, n in largos.items() if l != largo)
    sel = [i for i, v in enumerate(vectores) if len(v) == largo]

    meta = pd.DataFrame([filas[i] for i in sel])
    v = np.asarray([vectores[i] for i in sel], dtype=np.float64)
    csi = v[:, 1::2] + 1j * v[:, 0::2]  # real = impar, imaginario = par

    # first_word = 1 -> las 2 primeras subportadoras no son válidas.
    invalidas = meta["first_word"].to_numpy() == 1
    csi[invalidas, :2] = np.nan

    # Tiempo del ESP32: uint32 en µs impreso como entero con signo. Un salto atrás de más de 2^31 µs
    # es el desborde del contador (~71 min); uno menor es un reinicio de la placa, que se empalma
    # usando el intervalo típico para no inventar un hueco.
    ts = meta["local_timestamp"].to_numpy(dtype=np.int64) & 0xFFFFFFFF
    d = np.diff(ts)
    d[d < -2**31] += 2**32
    reinicios = d < 0
    if reinicios.any():
        d[reinicios] = np.median(d[d > 0]) if (d > 0).any() else 0
    meta["t_esp"] = np.concatenate([[0], np.cumsum(d)]) / 1e6
    meta["t_rel"] = meta["t_pc"] - meta["t_pc"].iloc[0]

    informe = {
        "lineas_totales": n_total,
        "lineas_no_csi": n_no_csi,
        "paquetes_validos": len(sel),
        "descartados": dict(motivos),
        "valores_por_paquete": largo,
        "subportadoras": largo // 2,
        "canales": sorted(meta["channel"].unique().tolist()),
        "reinicios_esp": int(reinicios.sum()),
    }
    return meta, csi, informe


def a_tabla(meta: pd.DataFrame, csi: np.ndarray) -> pd.DataFrame:
    n = csi.shape[1]
    amp = pd.DataFrame(np.abs(csi).round(4), columns=[f"amp_{k:03d}" for k in range(n)])
    fase = pd.DataFrame(np.angle(csi).round(4), columns=[f"fase_{k:03d}" for k in range(n)])
    cols = ["t_pc", "t_rel", "t_esp", "seq", "rssi", "channel", "noise_floor", "agc_gain", "fft_gain",
            "rate", "sig_len", "rx_format", "len", "first_word", "mac"]
    cols = [c for c in cols if c in meta.columns]
    return pd.concat([meta[cols].reset_index(drop=True), amp, fase], axis=1)


def cargar(ruta) -> pd.DataFrame:
    """Acepta un archivo crudo (t_pc_unix,linea) o una tabla ya leída (*_leido.csv)."""
    with open(ruta, encoding="utf-8") as f:
        encabezado = f.readline().strip()
    if encabezado == "t_pc_unix,linea":
        meta, csi, _ = leer_crudo(ruta)
        return a_tabla(meta, csi)
    return pd.read_csv(ruta)


def main() -> int:
    ap = argparse.ArgumentParser(description="Convierte un archivo crudo de CSI en tabla.")
    ap.add_argument("crudo", help="Archivo en datos/crudos/<id_sesion>.csv")
    ap.add_argument("--salida", help="CSV de salida (por defecto datos/procesados/<id>_leido.csv)")
    args = ap.parse_args()

    ruta = Path(args.crudo)
    meta, csi, inf = leer_crudo(ruta)
    tabla = a_tabla(meta, csi)
    salida = Path(args.salida) if args.salida else DIR_PROCESADOS / f"{ruta.stem}_leido.csv"
    salida.parent.mkdir(parents=True, exist_ok=True)
    tabla.to_csv(salida, index=False)

    dur = tabla["t_rel"].iloc[-1] if len(tabla) > 1 else 0
    print(f"Líneas totales:        {inf['lineas_totales']} (no CSI: {inf['lineas_no_csi']})")
    print(f"Paquetes CSI válidos:  {inf['paquetes_validos']}")
    print(f"Descartados:           {inf['descartados'] or 'ninguno'}")
    print(f"Subportadoras:         {inf['subportadoras']} ({inf['valores_por_paquete']} valores/paquete)")
    print(f"Canal(es):             {inf['canales']}")
    if inf["reinicios_esp"]:
        print(f"Aviso: el reloj del ESP32 se reinició {inf['reinicios_esp']} vez/veces (¿se reseteó la placa?).")
    print(f"RSSI medio:            {tabla['rssi'].mean():.1f} dBm")
    if dur > 0:
        print(f"Duración / tasa:       {dur:.1f} s / {len(tabla) / dur:.1f} paq/s")
    print(f"Tabla guardada en:     {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
