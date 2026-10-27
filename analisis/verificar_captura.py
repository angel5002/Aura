"""Revisa uno o varios <id>_local.csv de receptor_local.py contra los criterios de la prueba del kit movil.

Los umbrales NO estan en este script: se leen del bloque ```criterios de docs/ensayos/kit_movil_criterios.md
(fuente unica; --criterios para otra ruta). Criterios, por placa (un archivo = una placa, porque receptor_local.py
se suscribe a una sola IP):
  1. perdida < perdida_menor_que_pct (estricto), por numero de secuencia (mismo contador que receptor_local.py);
  2. 0 huecos mayores de hueco_max_s: tiempo entre dos datagramas A1 consecutivos segun t_pc_unix;
  3. mediana de CSI/s en ventanas completas de ventana_tasa_s >= tasa_csi_factor_min x tasa_csi_ref_s002;
  4. reinicios <= reinicios_max: por ts_ms (receptor) y retrocesos de encendido_s (telemetria);
  5. Termux sin cierres: existe <id>_local_resumen.json, "fin" = "duracion" y hay archivos_por_sesion archivo(s)
     <id>*_local.csv en la carpeta.
Informa ademas (sin criterio): t_us = 0 (placa sin hora valida), reinicios (por ts_ms y por secuencia) y, de los
mensajes 'telemetria', motivo_reinicio y encendido_s por arranque (encendido = alimentacion, brownout = caida de
tension, panico/wdt = fallo de software), la memoria minima por intervalo de 10 s (heap_min_intervalo) y el % de
tiempo en MOVIMIENTO (motion_status de las muestras). Solo lee: no cambia nada ni registra en
docs/resultados_pruebas.md.

Ejemplo:
    python verificar_captura.py ../datos/crudos/K001_local.csv
"""

import argparse
import csv
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

from aura_proto import parsear_datagrama
from receptor_local import ContadorSecuencia, ts_muestra

RAIZ = Path(__file__).resolve().parent.parent
CRITERIOS = RAIZ / "docs" / "ensayos" / "kit_movil_criterios.md"
CLAVES = ("perdida_menor_que_pct", "hueco_max_s", "ventana_tasa_s", "tasa_csi_factor_min", "tasa_csi_ref_s002",
          "reinicios_max", "archivos_por_sesion")
SUFIJO = "_local.csv"
MAX_TRAMO_MOV_S = 1.0           # % en MOVIMIENTO: una muestra no rige mas de 1 s (las muestras van a ~18/s)


def leer_criterios(ruta: Path) -> dict:
    """Bloque ```criterios con lineas 'clave = valor'. 'PENDIENTE' -> None."""
    m = re.search(r"```criterios\n(.*?)```", ruta.read_text(encoding="utf-8"), re.S)
    if not m:
        raise ValueError(f"{ruta}: no hay bloque ```criterios")
    crit = {}
    for linea in m.group(1).splitlines():
        if "=" in linea:
            k, v = (x.strip() for x in linea.split("=", 1))
            crit[k] = None if v.upper() == "PENDIENTE" else float(v.replace(",", "."))
    faltan = [k for k in CLAVES if k not in crit]
    if faltan:
        raise ValueError(f"{ruta}: faltan {faltan}")
    return crit


def leer_telemetria(cuerpo: str) -> dict | None:
    if '"type":"telemetria"' not in cuerpo:
        return None
    try:
        m = json.loads(cuerpo)
    except json.JSONDecodeError:
        return None
    return m if m.get("type") == "telemetria" else None


def revisar(ruta: Path, crit: dict) -> bool | None:
    """True si cumple todo; False si algun criterio falla; None si alguno no se pudo evaluar."""
    cont = ContadorSecuencia()
    por_tipo = Counter()
    t_us_cero = 0
    t_prev = None
    huecos = []                 # (t_pc_unix al empezar el hueco, duracion s)
    t_csi = []
    arranques = []              # por arranque segun la telemetria: dict motivo, enc_ini, enc_fin, t_ini, t_fin, n
    retrocesos_enc = 0          # veces que encendido_s retrocede (reinicio visto por la telemetria)
    n_tel = 0
    muestras_mov = []           # (t_pc_unix, motion_status) de los mensajes 'sample'
    t_ini = t_fin = None
    with open(ruta, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        next(r, None)           # t_pc_unix,linea
        for fila in r:
            if len(fila) < 2:
                continue
            d = parsear_datagrama(fila[1])
            if d is None:
                continue
            t = float(fila[0])
            t_ini = t if t_ini is None else t_ini
            t_fin = t
            if t_prev is not None and t - t_prev > crit["hueco_max_s"]:
                huecos.append((t_prev, t - t_prev))
            t_prev = t
            cont.agregar(d.seq, ts_muestra(d))
            por_tipo[d.tipo] += 1
            t_us_cero += d.t_us == 0
            if d.tipo == "csi":
                t_csi.append(t)
            elif d.tipo == "hms":
                tel = leer_telemetria(d.cuerpo)
                if tel is not None and isinstance(tel.get("encendido_s"), (int, float)):
                    enc, motivo = tel["encendido_s"], tel.get("motivo_reinicio", "?")
                    a = arranques[-1] if arranques else None
                    n_tel += 1
                    retrocesos_enc += a is not None and enc < a["enc_fin"]
                    if a is None or enc < a["enc_fin"] or motivo != a["motivo"]:
                        a = {"motivo": motivo, "enc_ini": enc, "enc_fin": enc, "t_ini": t, "t_fin": t, "n": 1,
                             "heap_int": []}
                        arranques.append(a)
                    else:
                        a.update(enc_fin=enc, t_fin=t, n=a["n"] + 1)
                    if isinstance(tel.get("heap_min_intervalo"), (int, float)):
                        a["heap_int"].append(tel["heap_min_intervalo"])
                elif '"type":"sample"' in d.cuerpo:
                    try:
                        m = json.loads(d.cuerpo)
                    except json.JSONDecodeError:
                        m = None
                    if isinstance(m, dict) and "motion_status" in m:
                        muestras_mov.append((t, bool(m["motion_status"])))

    print(f"\n== {ruta.name}")
    n = sum(por_tipo.values())
    if n == 0:
        print("  [FALLIDO] no hay datagramas A1")
        return False
    dur = t_fin - t_ini
    res = cont.resumen(final=True)
    tasas = ", ".join(f"{k} {v / dur:.1f}/s" for k, v in sorted(por_tipo.items())) if dur > 0 else "-"
    print(f"  duracion {dur:.1f} s (t_pc_unix), {n} datagramas: {tasas}")
    print(f"  t_us = 0 en {t_us_cero} de {n} ({100 * t_us_cero / n:.1f} %; 100 % = placa sin hora valida; tras un "
          f"reinicio por software puede conservar la anterior)")
    print(f"  secuencia: esperados {res['esperados']}, perdidos {res['perdidos']}, desordenados {res['desordenados']}, "
          f"duplicados {res['duplicados']}, epocas {res['epocas']} (reinicios por ts_ms {res['reinicios_por_ts']}, "
          f"por secuencia {res['reinicios_por_secuencia']})")
    if arranques:
        print(f"  telemetria ({sum(a['n'] for a in arranques)} mensajes), por arranque:")
        for a in arranques:
            print(f"    motivo_reinicio={a['motivo']}, encendido_s {a['enc_ini']} -> {a['enc_fin']}, "
                  f"de {a['t_ini'] - t_ini:.1f} s a {a['t_fin'] - t_ini:.1f} s del archivo")
            if a["heap_int"]:
                h = a["heap_int"]
                print(f"      [INFORMATIVO] memoria minima por intervalo de 10 s (heap_min_intervalo): "
                      f"min {min(h)} B, mediana {statistics.median(h):.0f} B, en {len(h)} intervalos")
    else:
        print("  telemetria: ningun mensaje (llega cada 10 s; sin ella no se sabe el motivo de un reinicio)")
    if len(muestras_mov) >= 2:
        # Cada muestra rige hasta la siguiente, con un tope de MAX_TRAMO_MOV_S para no contar los huecos.
        tot = mov = 0.0
        for (t0, m0), (t1, _) in zip(muestras_mov, muestras_mov[1:]):
            dt = min(t1 - t0, MAX_TRAMO_MOV_S)
            tot += dt
            mov += dt if m0 else 0.0
        n_mov = sum(m for _, m in muestras_mov)
        print(f"  [INFORMATIVO] tiempo en MOVIMIENTO (motion_status de las muestras): {100 * mov / tot:.2f} % "
              f"({n_mov} de {len(muestras_mov)} muestras); con la sala vacia sirve para comparar con S002")

    ok = True
    pend = False
    ok1 = res["perdida_pct"] < crit["perdida_menor_que_pct"]
    print(f"  [{'APROBADO' if ok1 else 'FALLIDO'}] 1. perdida {res['perdida_pct']:.3f} % "
          f"(criterio < {crit['perdida_menor_que_pct']:g} %)")
    ok2 = not huecos
    print(f"  [{'APROBADO' if ok2 else 'FALLIDO'}] 2. huecos > {crit['hueco_max_s']:g} s: {len(huecos)} (criterio 0)")
    for t0, h in huecos[:10]:
        print(f"      hueco de {h:.1f} s desde t_pc_unix {t0:.3f} ({t0 - t_ini:.1f} s tras el primer datagrama)")
    if len(huecos) > 10:
        print(f"      ... y {len(huecos) - 10} mas")
    ok = ok1 and ok2

    v = crit["ventana_tasa_s"]
    n_vent = int(dur // v)
    conteo = Counter(int((t - t_ini) // v) for t in t_csi)
    tasas_vent = [conteo.get(k, 0) / v for k in range(n_vent)]
    if not tasas_vent:
        print(f"  [NO EVALUADO] 3. tasa de CSI: el archivo dura menos de una ventana de {v:g} s")
        pend = True
    else:
        mediana = statistics.median(tasas_vent)
        ref = crit["tasa_csi_ref_s002"]
        if ref is None:
            print(f"  [NO EVALUADO] 3. mediana de CSI/s en {n_vent} ventanas de {v:g} s: {mediana:.2f}/s "
                  f"(falta tasa_csi_ref_s002 en el documento de criterios)")
            pend = True
        else:
            minimo = crit["tasa_csi_factor_min"] * ref
            ok3 = mediana >= minimo
            ok = ok and ok3
            print(f"  [{'APROBADO' if ok3 else 'FALLIDO'}] 3. mediana de CSI/s en {n_vent} ventanas de {v:g} s: "
                  f"{mediana:.2f}/s (criterio >= {crit['tasa_csi_factor_min']:g} x {ref:g} = {minimo:.2f}/s)")

    rmax = crit["reinicios_max"]
    if n_tel == 0:
        print(f"  [NO EVALUADO] 4. reinicios: por ts_ms {res['reinicios_por_ts']}, pero no hay telemetria para ver "
              f"encendido_s")
        pend = True
    else:
        ok4 = res["reinicios_por_ts"] <= rmax and retrocesos_enc <= rmax
        ok = ok and ok4
        print(f"  [{'APROBADO' if ok4 else 'FALLIDO'}] 4. reinicios: por ts_ms {res['reinicios_por_ts']}, retrocesos "
              f"de encendido_s {retrocesos_enc} en {n_tel} telemetrias (criterio <= {rmax:g} en ambos)")

    r5 = termux_sin_cierres(ruta, crit)
    if r5 is None:
        pend = True
    else:
        ok = ok and r5
    return None if (ok and pend) else ok


def termux_sin_cierres(ruta: Path, crit: dict) -> bool | None:
    """Criterio 5. None si no se puede evaluar (nombre sin _local.csv o resumen de una version anterior)."""
    if not ruta.name.endswith(SUFIJO):
        print(f"  [NO EVALUADO] 5. Termux sin cierres: el nombre no termina en {SUFIJO}")
        return None
    sesion = ruta.name[: -len(SUFIJO)]
    resumen = ruta.with_name(f"{sesion}_local_resumen.json")
    archivos = sorted(p.name for p in ruta.parent.glob(f"{sesion}*{SUFIJO}"))
    ok_arch = len(archivos) == int(crit["archivos_por_sesion"])
    if not resumen.exists():
        print(f"  [FALLIDO] 5. Termux sin cierres: no existe {resumen.name} (el receptor no termino normalmente); "
              f"archivos de captura: {archivos}")
        return False
    try:
        fin = json.loads(resumen.read_text(encoding="utf-8")).get("fin")
    except (OSError, json.JSONDecodeError) as e:
        print(f"  [FALLIDO] 5. Termux sin cierres: {resumen.name} ilegible ({e})")
        return False
    if fin is None:
        print(f"  [NO EVALUADO] 5. Termux sin cierres: {resumen.name} no tiene 'fin' (receptor anterior al "
              f"26/10/2026); archivos de captura: {len(archivos)}")
        return None
    ok5 = fin == "duracion" and ok_arch
    print(f"  [{'APROBADO' if ok5 else 'FALLIDO'}] 5. Termux sin cierres: fin={fin!r}, archivos de captura "
          f"{len(archivos)} {archivos if not ok_arch else ''}(criterio: fin='duracion' y "
          f"{int(crit['archivos_por_sesion'])} archivo)")
    return ok5


def main() -> int:
    ap = argparse.ArgumentParser(description="Revisa capturas <id>_local.csv contra los criterios del kit movil.")
    ap.add_argument("archivos", nargs="+", type=Path)
    ap.add_argument("--criterios", type=Path, default=CRITERIOS, help=f"por defecto {CRITERIOS}")
    args = ap.parse_args()
    try:
        crit = leer_criterios(args.criterios)
    except (OSError, ValueError) as e:
        print(f"ERROR al leer los criterios: {e}")
        return 2
    print(f"Criterios de {args.criterios}: " + ", ".join(f"{k}={crit[k]}" for k in CLAVES))
    resultados = []
    for ruta in args.archivos:
        if not ruta.exists():
            print(f"\n== {ruta}: no existe")
            resultados.append(False)
            continue
        resultados.append(revisar(ruta, crit))
    if all(r is True for r in resultados):
        print("\nResultado: todos los archivos cumplen los criterios")
        return 0
    if any(r is False for r in resultados):
        print("\nResultado: hay criterios FALLIDOS")
        return 1
    print("\nResultado: incompleto (hay criterios NO EVALUADOS)")
    return 3


if __name__ == "__main__":
    sys.exit(main())
