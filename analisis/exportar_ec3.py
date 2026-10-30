"""Exporta K002 y K001 (placa B) a un dataset anonimizado para el curso Introduccion a Data Science (EC3).

Solo anonimiza y cambia el formato: NO limpia ni corrige (la limpieza es parte del trabajo del curso).
Lee en solo lectura datos/crudos/<SESION>_local.csv y escribe en datos/procesados/ec3_dataset/ (fuera de git).

Formatos (derivados del codigo fuente y de lineas reales, no supuestos):
- Crudo: columnas t_pc_unix (hora del receptor) y linea (datagrama 'A1 <seq> <t_us> <tipo> <cuerpo>', aura_proto.py).
- csi (firmware/aura_nodo/main/aura_local.c:134): 'raw' es el buffer del driver; en el C5 son 106 bytes = 53
  palabras de 16 bits con valores de 12 bits con signo. esp-radar copia los bytes 0-104 a 'valid'
  (csi_sub_carrier_table.c, entrada de 106 bytes) y los multiplica por 'comp'. Comprobado en K002:
  valid = round(raw[0:52] * comp). Aqui se exportan raw[0:52] SIN compensar (26 pares) y 'comp' aparte.
- hms 'sample' (web_serial_monitor.c): motion_status del detector; 'telemetria' (aura_telemetria.c:209), cada 10 s.
- Se descartan: MAC (campo 'mac' de 'sample'), IP (solo esta en el *_resumen.json, que no se lee) y 'peer'.

Uso:  python C:\\aura\\analisis\\exportar_ec3.py [K002 K001]
"""

import base64
import csv
import json
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aura_proto import parsear_datagrama  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
CRUDOS = RAIZ / "datos" / "crudos"
SALIDA = RAIZ / "datos" / "procesados" / "ec3_dataset"
PLACA = "B"
N_SUBP = 26
BYTES_IQ = 4 * N_SUBP           # 26 pares de palabras de 16 bits = bytes 0-104 del buffer crudo
LIMITE_GZ = 50 * 1024 * 1024
PERIODO_TEL_S = 10              # PERIODO_MS de aura_telemetria.c

# Guion de K002 (docs/ensayos/k002_cruces.md y kit_movil/scripts/k002.sh): t = 0 es el primer datagrama;
# ROJO (cruzar) desde 1 s antes de cada horario hasta 5 s despues; VERDE (fin) a los 300 s.
CRUCES = [30 + 25 * k for k in range(10)]
ROJO_ANTES_S, ROJO_DESPUES_S, FIN_HORARIO_S = 1, 5, 300


def leer_sesion(sesion: str) -> dict:
    """Recorre el crudo en el orden de llegada: una fila por csi, detector y telemetria aparte."""
    t, seq, seq_dg, ts, rssi, comp, det, raw_len = [], [], [], [], [], [], [], []
    iq = bytearray()
    tel = []
    t0 = None
    detector = ""                    # ultimo motion_status recibido ("" antes de la primera muestra)
    with open(CRUDOS / f"{sesion}_local.csv", newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        next(r, None)
        for fila in r:
            d = parsear_datagrama(fila[1]) if len(fila) > 1 else None
            if d is None:
                continue
            tt = float(fila[0])
            t0 = tt if t0 is None else t0
            m = json.loads(d.cuerpo)
            if d.tipo == "csi":
                crudo = base64.b64decode(m.get("raw", ""))
                t.append(tt - t0)
                seq.append(m["seq_id"])
                seq_dg.append(d.seq)
                ts.append(m["rx_ts_us"])
                rssi.append(m["rssi"])
                comp.append(m["comp"])
                det.append(detector)
                raw_len.append(len(crudo))
                iq += crudo[:BYTES_IQ].ljust(BYTES_IQ, b"\0")
            elif m.get("type") == "sample":
                detector = "true" if m.get("motion_status") else "false"
            elif m.get("type") == "telemetria":
                tel.append({"t_s": tt - t0, **{k: v for k, v in m.items() if k != "type"}})
    palabras = np.frombuffer(bytes(iq), dtype="<u2").reshape(-1, 2 * N_SUBP)
    vals = ((palabras << 4).astype(np.uint16).view(np.int16) >> 4).astype(np.int16)
    raw_len = np.array(raw_len)
    return {"t_s": np.array(t), "seq": np.array(seq, dtype=np.int64), "seq_datagrama": np.array(seq_dg, dtype=np.int64),
            "ts_us_placa": np.array(ts, dtype=np.int64), "rssi": np.array(rssi), "comp": np.array(comp),
            "detector_placa": np.array(det, dtype=object), "vals": vals, "raw_len": raw_len, "telemetria": tel}


def tabla_lecturas(sesion: str, d: dict) -> pd.DataFrame:
    cols = {"sesion": sesion, "placa": PLACA, "t_s": np.round(d["t_s"], 6), "seq": d["seq"],
            "seq_datagrama": d["seq_datagrama"], "ts_us_placa": d["ts_us_placa"], "rssi": d["rssi"],
            "comp": d["comp"]}
    corto = d["raw_len"] < BYTES_IQ          # buffer mas corto que 26 pares: esos valores no existen
    for k in range(N_SUBP):
        # orden del par segun ESP-IDF: parte imaginaria primero, luego la real
        for nombre, j in ((f"i_{k:02d}", 2 * k + 1), (f"q_{k:02d}", 2 * k)):
            col = pd.array(d["vals"][:, j], dtype="Int16")
            col[corto & (d["raw_len"] < 2 * (j + 1))] = pd.NA
            cols[nombre] = col
    cols["detector_placa"] = pd.array(np.where(d["detector_placa"] == "", None, d["detector_placa"]), dtype="string")
    return pd.DataFrame(cols)


def tabla_telemetria(tel: list) -> pd.DataFrame:
    """Una fila por telemetria recibida; las que faltan (salto > 1,5 periodos en encendido_s) van vacias."""
    filas = []
    for i, m in enumerate(tel):
        if i > 0:
            salto = m["encendido_s"] - tel[i - 1]["encendido_s"]
            if salto > 1.5 * PERIODO_TEL_S:
                for j in range(1, round(salto / PERIODO_TEL_S)):
                    filas.append({"recibida": 0, "encendido_s": tel[i - 1]["encendido_s"] + j * PERIODO_TEL_S})
        filas.append({"recibida": 1, **m})
    df = pd.DataFrame(filas)
    df["t_s"] = df["t_s"].round(6)
    orden = ["t_s", "recibida", "encendido_s"] + [c for c in df.columns if c not in ("t_s", "recibida", "encendido_s")]
    df = df[orden]
    for c in df.columns:
        if c != "t_s" and df[c].dtype == float and df[c].dropna().apply(float.is_integer).all():
            df[c] = df[c].astype("Int64")
    return df


def tabla_protocolo() -> pd.DataFrame:
    filas, ini = [], 0
    for k, tc in enumerate(CRUCES, 1):
        filas.append((ini, tc - ROJO_ANTES_S, "quieto", None))
        filas.append((tc - ROJO_ANTES_S, tc + ROJO_DESPUES_S, "cruce", k))
        ini = tc + ROJO_DESPUES_S
    filas.append((ini, FIN_HORARIO_S, "quieto", None))
    df = pd.DataFrame(filas, columns=["inicio_s", "fin_s", "etiqueta", "n_cruce"])
    df["n_cruce"] = df["n_cruce"].astype("Int64")
    return df


def guardar(df: pd.DataFrame, ruta: Path) -> list:
    df.to_csv(ruta, index=False, encoding="utf-8", lineterminator="\n")
    if ruta.stat().st_size <= LIMITE_GZ:
        return [ruta]
    gz = ruta.with_suffix(".csv.gz")
    df.to_csv(gz, index=False, encoding="utf-8", lineterminator="\n", compression={"method": "gzip", "mtime": 0})
    return [ruta, gz]


def estadisticas(df: pd.DataFrame, d: dict) -> dict:
    seq, seq_dg, ts = d["seq"], d["seq_datagrama"], d["ts_us_placa"]
    # tramos sin reinicio de la placa: se cortan donde seq_datagrama retrocede
    cortes = np.flatnonzero(np.diff(seq_dg) < 0) + 1
    esperados = perdidos = duplicados = 0
    for tramo in np.split(seq, cortes):
        unicos = np.unique(tramo)
        esperados += int(unicos[-1] - unicos[0] + 1)
        perdidos += int(unicos[-1] - unicos[0] + 1 - len(unicos))
        duplicados += len(tramo) - len(unicos)
    t = d["t_s"]
    por_s = np.bincount(np.floor(t).astype(int))[: int(np.floor(t[-1]))]   # segundos completos
    I = d["vals"][:, 1::2]
    Q = d["vals"][:, 0::2]
    ceros = [k for k in range(N_SUBP) if not I[:, k].any() and not Q[:, k].any()]
    cols_cero = [c for c in df.columns if (c.startswith("i_") or c.startswith("q_")) and not df[c].fillna(0).any()]
    return {
        "filas": len(df), "duracion_s": float(t[-1]), "pps_mediana": float(np.median(por_s)),
        "esperados": esperados, "perdidos": perdidos, "huecos_pct": 100 * perdidos / esperados,
        "duplicados": duplicados, "retroceso_seq": int((np.diff(seq) < 0).sum()),
        "retroceso_seq_dg": int(len(cortes)), "retroceso_ts": int((np.diff(ts) < 0).sum()),
        "max_intervalo_s": float(np.diff(t).max()), "raw_len": dict(zip(*map(list, np.unique(d["raw_len"], return_counts=True)))),
        "subp_cero": ceros, "cols_cero": cols_cero,
        "i_min": int(I.min()), "i_max": int(I.max()), "q_min": int(Q.min()), "q_max": int(Q.max()),
        "nulos": {c: int(n) for c, n in df.isna().sum().items() if n > 0}, "ncols": df.shape[1],
    }


def fmt(x: float, dec: int = 2) -> str:
    return f"{x:,.{dec}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def resumen_md(est: dict, prot: pd.DataFrame | None, tel: pd.DataFrame | None, archivos: list) -> str:
    out = ["# Resumen numérico del dataset EC3 (placa B)", "",
           "Solo números, sin conclusiones. Calculado por `analisis/exportar_ec3.py` sobre los archivos exportados.",
           "t_s se mide con la hora del receptor desde el primer datagrama de la captura.", ""]
    for sesion, e in est.items():
        out += [f"## {sesion}", "",
                "| Medida | Valor |", "|---|---|",
                f"| Filas (paquetes CSI) | {fmt(e['filas'], 0)} |",
                f"| Duración (t_s de la última fila) | {fmt(e['duracion_s'], 3)} s |",
                f"| Paquetes por segundo (mediana por segundo completo) | {fmt(e['pps_mediana'], 1)} |",
                f"| Intervalo máximo entre paquetes consecutivos | {fmt(e['max_intervalo_s'], 3)} s |",
                f"| Huecos según `seq` | {fmt(e['perdidos'], 0)} de {fmt(e['esperados'], 0)} esperados "
                f"({fmt(e['huecos_pct'], 3)} %) |",
                f"| Filas duplicadas (mismo `seq` en el mismo tramo sin reinicio) | {e['duplicados']} |",
                f"| Retrocesos de `seq_datagrama` (reinicios de la placa detectados) | {e['retroceso_seq_dg']} |",
                f"| Retrocesos de `seq` | {e['retroceso_seq']} |",
                f"| Retrocesos de `ts_us_placa` | {e['retroceso_ts']} |",
                f"| Longitud del buffer crudo (bytes: filas) | "
                + ", ".join(f"{k}: {fmt(v, 0)}" for k, v in e["raw_len"].items()) + " |",
                f"| Subportadoras con I y Q siempre en cero | "
                + (", ".join(f"{k:02d}" for k in e["subp_cero"]) or "ninguna") + " |",
                f"| Columnas I/Q siempre en cero | " + (", ".join(e["cols_cero"]) or "ninguna") + " |",
                f"| Rango de I (todas las subportadoras) | {e['i_min']} a {e['i_max']} |",
                f"| Rango de Q (todas las subportadoras) | {e['q_min']} a {e['q_max']} |",
                ""]
        out += ["Nulos por columna (de " + str(e["ncols"]) + " columnas; las no listadas tienen 0):", ""]
        out += ([f"- `{c}`: {fmt(n, 0)}" for c, n in e["nulos"].items()] or ["- ninguna columna tiene nulos"]) + [""]
        if sesion == "K002" and prot is not None:
            out += ["Tramos del protocolo (`K002_protocolo.csv`):", "", "| Etiqueta | Tramos | Segundos |", "|---|---|---|"]
            for et, g in prot.groupby("etiqueta"):
                out.append(f"| {et} | {len(g)} | {fmt((g['fin_s'] - g['inicio_s']).sum(), 0)} |")
            out += [f"| sin etiqueta (de {FIN_HORARIO_S} s al final de la captura) | — | "
                    f"{fmt(e['duracion_s'] - FIN_HORARIO_S, 3)} |", "",
                    "Origen de los tiempos: el guion del protocolo, no el detector: `docs/ensayos/k002_cruces.md` "
                    "(tablas *Semáforo* y *Horario*) y `kit_movil/scripts/k002.sh` (`CRUCES = 30 + 25·k`, ROJO desde "
                    f"{ROJO_ANTES_S} s antes hasta {ROJO_DESPUES_S} s después de cada horario, VERDE a los "
                    f"{FIN_HORARIO_S} s). El cero del semáforo es el primer datagrama de la captura, el mismo de t_s.", ""]
        if sesion == "K001" and tel is not None:
            out += [f"Telemetría (`K001_telemetria.csv`): {len(tel)} filas, {int(tel['recibida'].sum())} recibidas y "
                    f"{int((tel['recibida'] == 0).sum())} faltantes (vacías); periodo nominal {PERIODO_TEL_S} s.", ""]
    out += ["## Archivos", "", "| Archivo | Tamaño |", "|---|---|"]
    out += [f"| `{p.name}` | " + (f"{fmt(p.stat().st_size / 1e6, 1)} MB" if p.stat().st_size >= 1e6
                                   else f"{fmt(p.stat().st_size / 1e3, 1)} kB") + " |" for p in archivos]
    return "\n".join(out) + "\n"


DICCIONARIO = """# Diccionario de datos — dataset EC3 (placa B, proyecto AURA)

Datos de sensado WiFi (CSI) de una placa ESP32-C5 (placa "B", firmware AURA 0.1.3) que escucha las tramas de un
router. Se exportan **sin limpiar ni corregir**: duplicados, huecos, reinicios y valores raros quedan tal cual.
Anonimizado: sin direcciones MAC, sin IP y sin nombres; las sesiones se identifican por código.

- **K002** (27/10/2026, ~330 s): una persona de pie y quieta junto al enlace, con 10 cruces de ida y vuelta.
- **K001** (27/10/2026, ~30 min): prueba de estabilidad.

Archivos CSV en UTF-8, separador coma, punto decimal, primera fila con los nombres. Celda vacía = dato faltante.

## `K002_lecturas.csv` y `K001_lecturas.csv` (una fila por paquete CSI, en orden de llegada)

| Columna | Tipo | Unidad | Significado |
|---|---|---|---|
| `sesion` | texto | — | Código de la sesión (`K002` o `K001`). |
| `placa` | texto | — | Placa que capturó (`B`). |
| `t_s` | real | s | Segundos desde el primer datagrama de la captura, medidos con el reloj del **receptor** (no es la hora real ni el reloj de la placa). |
| `seq` | entero | — | Número de secuencia del paquete CSI asignado en la placa (contador de esp-radar, +1 por paquete). Un salto mayor que 1 indica paquetes que no llegaron (perdidos en la red o descartados en la cola de la placa); un retroceso, un reinicio. |
| `seq_datagrama` | entero | — | Número de secuencia del datagrama UDP. Es común a todos los mensajes de la placa (CSI y mensajes del detector y telemetría, que no están en este archivo), así que entre dos filas consecutivas puede saltar más de 1 sin que falte nada. Vuelve a empezar si la placa se reinicia. |
| `ts_us_placa` | entero | µs | Marca de tiempo del radio de la placa al recibir la trama, tal cual. Es un entero sin signo de 32 bits: vuelve a 0 cada 2³² µs (≈ 71,6 min) y también al reiniciarse la placa. (Se entrega en µs, que es la unidad original del paquete.) |
| `rssi` | entero | dBm | Potencia de la señal recibida. |
| `comp` | real | — | Factor de compensación de ganancia que el firmware calcula para ese paquete (`esp_csi_gain_ctrl`). Los I/Q de este archivo **no** lo tienen aplicado; el detector de la placa trabaja con `I·comp`, `Q·comp`. |
| `i_00` … `i_25` | entero | unidades del ADC (sin unidad física) | Parte real (en fase, I) de la subportadora k = 00…25, cruda (entero de 12 bits con signo, −2048 a 2047). |
| `q_00` … `q_25` | entero | unidades del ADC | Parte imaginaria (cuadratura, Q) de la subportadora k. |
| `detector_placa` | booleano (`true`/`false`) | — | `motion_status` del detector de movimiento del firmware: el último valor recibido **antes** de esa fila (el detector envía ~18 muestras/s, menos que el CSI). Vacío antes de la primera muestra del detector. |

## `K002_protocolo.csv` (tramos del guion de K002)

| Columna | Tipo | Unidad | Significado |
|---|---|---|---|
| `inicio_s` | entero | s | Inicio del tramo, en la misma escala que `t_s`. |
| `fin_s` | entero | s | Fin del tramo (intervalo [inicio_s, fin_s)). |
| `etiqueta` | texto | — | `quieto` (de pie y quieta en el punto de espera) o `cruce` (semáforo en rojo: cruzar la línea placa–router de ida y vuelta). |
| `n_cruce` | entero | — | Número de cruce (1–10); vacío en los tramos `quieto`. |

Los tiempos salen del **guion** (semáforo con avisos y pitidos), no del detector: el semáforo se pone rojo 1 s antes
de cada horario (30, 55, …, 255 s) y vuelve a azul 5 s después. El cruce real dura unos 3 s dentro de ese tramo.
Después de los 300 s el guion permite moverse: ese final de la captura no tiene etiqueta.

## `K001_telemetria.csv` (estado interno de la placa, cada 10 s)

| Columna | Tipo | Unidad | Significado |
|---|---|---|---|
| `t_s` | real | s | Igual que en lecturas; vacío en filas faltantes. |
| `recibida` | entero (0/1) | — | 1 = mensaje recibido; 0 = fila faltante (no llegó el mensaje esperado). |
| `encendido_s` | entero | s | Tiempo desde que se encendió la placa. En filas faltantes es el valor **esperado** (anterior + 10 s). |
| `heap_libre` | entero | bytes | Memoria dinámica libre. |
| `heap_minimo` | entero | bytes | Mínimo de memoria libre desde el arranque. |
| `heap_min_intervalo` | entero | bytes | Mínimo de memoria libre en los últimos 10 s. |
| `bloque_max` | entero | bytes | Mayor bloque contiguo libre. |
| `malloc_fallidos` | entero | — | Pedidos de memoria fallidos acumulados desde el arranque. |
| `malloc_fallido_max` | entero | bytes | Tamaño del mayor pedido de memoria que falló. |
| `malloc_fallido_caps` | texto (hex) | — | Tipo de memoria pedido en ese fallo (banderas de ESP-IDF). |
| `tls_handshakes` | entero | — | Conexiones seguras abiertas (nube; 0 en modo local). |
| `hms_por_s` | real | 1/s | Muestras del detector por segundo en los últimos 10 s. |
| `ts_mediana_ms`, `ts_p95_ms` | real | ms | Mediana y percentil 95 del intervalo entre muestras del detector. |
| `n_intervalos` | entero | — | Intervalos usados para esa mediana. |
| `motivo_reinicio` | texto | — | Causa del último arranque. |
| `ver` | texto | — | Versión del firmware. |
| `red` | texto | — | Red WiFi activa (`principal`/`respaldo`). |
| `rssi` | entero | dBm | Potencia de la señal del router según la conexión WiFi. |
| `cambios_red` | entero | — | Cambios de red acumulados. |
| `sntp` | entero (0/1) | — | 1 si la placa tiene la hora de internet. |
| `usb` | entero (0/1) | — | 1 si hay un monitor USB conectado. |
| `usb_descartes` | entero | — | Mensajes descartados en la salida USB (acumulado). |
| `local_subs` | entero | — | Receptores suscritos en la red local. |
| `local_seq` | entero | — | Último número de datagrama enviado (`seq_datagrama`). |
| `local_descartes` | entero | — | Mensajes descartados por cola llena en la placa (acumulado desde el arranque). |
| `local_errores` | entero | — | Errores de envío UDP (acumulado). |
| `csi_total` | entero | — | Paquetes CSI capturados desde el arranque (enviados o no). |
| `detector_recreado` | entero | — | Veces que se recreó el detector. |
| `estado` | texto | — | Estado de AURA (p. ej. `SIN_MOVIMIENTO`). |
| `nube`, `nube_tokens`, `nube_renovaciones`, `nube_errores`, `nube_escrituras`, `nube_espera_s`, `nube_http` | texto/entero | —, s | Estado y contadores de la vía a la nube (inactiva en estas sesiones). |
| `particion`, `estado_ota` | texto/entero | — | Partición de firmware en uso y su estado de actualización. |
| `rx_buf` | entero | — | Búferes de recepción WiFi configurados. |
| `reintentos_principal` | entero | — | Reintentos de volver a la red principal. |
| `sim_sin_internet_s`, `sim_pierde_principal_s` | entero | s | Simulaciones de fallo de red activas (0 = ninguna). |
| `cmd_rechazados` | entero | — | Comandos rechazados (firma inválida). |

## Nota sobre la CSI

- Cada subportadora k es un número complejo H_k = I_k + j·Q_k. **Amplitud** = √(I_k² + Q_k²); fase = atan2(Q_k, I_k).
- Orden del par: el buffer trae cada subportadora como (parte imaginaria, parte real), según la documentación de
  ESP-IDF; aquí ya están separadas en `q_k` e `i_k`. La amplitud no depende de ese orden; la fase sí (no verificado en esta placa).
- El buffer del driver trae 53 palabras de 16 bits; esp-radar usa las 52 primeras (26 pares) y descarta la última,
  que no se incluye aquí.
- Índices: no hay documentación de qué frecuencia física corresponde a cada índice 00–25 en este modo del C5
  (el comentario de esp-radar para este buffer dice "LLTF: 0~26, −26~−1", que no cuadra con 26 pares), así que
  no se asignan frecuencias. Las subportadoras nulas o de guarda no se conocen por documentación: el `resumen.md`
  indica cuáles valen siempre cero en estos datos ({ceros}).
- Para comparar paquetes entre sí puede hacer falta la compensación de ganancia (`comp`): es una decisión de la limpieza.
"""


def main(sesiones: list) -> int:
    SALIDA.mkdir(parents=True, exist_ok=True)
    archivos, est, prot, tel_k001 = [], {}, None, None
    for sesion in sesiones:
        print(f"{sesion}: leyendo...", flush=True)
        d = leer_sesion(sesion)
        df = tabla_lecturas(sesion, d)
        est[sesion] = estadisticas(df, d)
        archivos += guardar(df, SALIDA / f"{sesion}_lecturas.csv")
        print(f"{sesion}: {len(df)} filas", flush=True)
        if sesion == "K002":
            prot = tabla_protocolo()
            archivos += guardar(prot, SALIDA / "K002_protocolo.csv")
        if sesion == "K001":
            tel_k001 = tabla_telemetria(d["telemetria"])
            archivos += guardar(tel_k001, SALIDA / "K001_telemetria.csv")
        del d, df
    ceros = "; ".join(f"{s}: " + (", ".join(f"{k:02d}" for k in e["subp_cero"]) or "ninguna") for s, e in est.items())
    (SALIDA / "diccionario_datos.md").write_text(DICCIONARIO.replace("{ceros}", ceros), encoding="utf-8", newline="\n")
    archivos.append(SALIDA / "diccionario_datos.md")
    (SALIDA / "resumen.md").write_text(resumen_md(est, prot, tel_k001, archivos), encoding="utf-8", newline="\n")
    archivos.append(SALIDA / "resumen.md")
    # al .zip va el .csv.gz en lugar del .csv grande, para no duplicar los datos
    con_gz = {p.with_suffix("").with_suffix(".csv") for p in archivos if p.name.endswith(".csv.gz")}
    zip_ruta = SALIDA / "ec3_dataset.zip"
    with zipfile.ZipFile(zip_ruta, "w") as z:
        for p in archivos:
            if p in con_gz:
                continue
            z.write(p, f"ec3_dataset/{p.name}",
                    compress_type=zipfile.ZIP_STORED if p.suffix == ".gz" else zipfile.ZIP_DEFLATED)
    print(f"ZIP: {zip_ruta} ({zip_ruta.stat().st_size / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or ["K002", "K001"]))
