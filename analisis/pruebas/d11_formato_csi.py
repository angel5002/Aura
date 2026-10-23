"""D11 - Formato real del CSI crudo del C5 (LLTF, modo de 16 bits) con datos de la placa.

Captura 2 min por la via local y analiza los mensajes 'csi' (raw = buffer del driver, valid = subportadoras
validas compensadas). Referencias:
  - IDF docs/en/api-guides/wifi.rst (seccion esp32c5): LLTF 20 MHz, subportadoras "0~26, -26~-1",
    total 106 bytes, "each item is stored as two bytes: imaginary part followed by real part".
  - IDF esp_wifi_he_types.h: wifi_csi_acquire_config_t.lltf_bit_mode "0: 12-bit, 1: 8-bit, default 12-bit".
  - esp-radar copy_subcarrier_data(): en modo 16 bits lee palabras uint16 y extiende el signo de 12 bits;
    rangos de la tabla del C5 (bytes): {0,52} y {52,104}.

Criterios:
  a) LONGITUD: para cada formato (rx_format, cwb) todos los paquetes tienen el mismo raw_len y valid_len, y
     raw_len coincide con el total de la tabla de IDF (106/114/228/...) o con su doble (12 bits en 16).
  b) NULOS: el conjunto de posiciones siempre nulas (>= 99 % de los paquetes) es estable; se informan.
  c) TRANSFORMACION: valid == redondeo(raw_extendido[rangos] * comp) con |error| <= 1 en >= 99 % de valores.
  d) GANANCIAS: agc, fft y comp presentes en el 100 % de los paquetes.
  e) ORDEN Re/Im: INFORMATIVO. Con datos de una sola placa no hay referencia para distinguir (Im, Re) de
     (Re, Im) (son conjugados salvo un factor j); se informa lo documentado por IDF. La amplitud no depende.
     Tambien se informa que emparejamiento de valores (desfase 0 o 1) da amplitudes mas suaves.
"""

import argparse
import base64
import json
import sys
from collections import Counter, defaultdict

import numpy as np

from comun import Coleccion, ip_placa, recibir_en_hilo
from registrar import registrar

TOTALES_IDF_C5 = {106, 114, 228, 234, 468, 490}


class ColeccionCSI(Coleccion):
    def __init__(self):
        super().__init__()
        self.csi = []

    def al_recibir(self, t_pc, d):
        if d.tipo == "csi":
            try:
                self.csi.append(json.loads(d.cuerpo))
            except json.JSONDecodeError:
                pass
        else:
            super().al_recibir(t_pc, d)


def extender12(raw: bytes) -> np.ndarray:
    w = np.frombuffer(raw[: len(raw) // 2 * 2], dtype="<u2").astype(np.int32)
    return (((w << 4) & 0xFFFF).astype(np.uint16).view(np.int16) >> 4).astype(np.int32)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ip")
    ap.add_argument("--segundos", type=float, default=120)
    a = ap.parse_args()
    ip = ip_placa(a.ip)
    col = ColeccionCSI()
    h, res = recibir_en_hilo(ip, "D11", a.segundos, col)
    h.join()
    pk = col.csi
    if not pk:
        registrar("D11 formato CSI", "sin paquetes csi", "ver plan", "FALLIDA", "¿hay receptor suscrito y AP activo?")
        return 1

    # d) ganancias
    con_gan = sum(1 for p in pk if all(p.get(k) is not None for k in ("agc", "fft", "comp")))
    ok_d = con_gan == len(pk)

    # a) longitudes por formato
    por_fmt = defaultdict(Counter)
    for p in pk:
        por_fmt[(p.get("rx_format"), p.get("cwb"), p.get("tipo_dato"))][(p["raw_len"], p["valid_len"])] += 1
    ok_a = True
    txt_a = []
    for fmt, c in por_fmt.items():
        (raw_len, valid_len), n = c.most_common(1)[0]
        constante = n == sum(c.values())
        en_tabla = raw_len in TOTALES_IDF_C5 or raw_len // 2 in TOTALES_IDF_C5
        ok_a &= constante and en_tabla
        txt_a.append(f"fmt{fmt}: raw {raw_len} B, valid {valid_len} B, {n}/{sum(c.values())} paquetes"
                     f"{'' if en_tabla else ' (NO coincide con la tabla de IDF)'}")

    # Formato dominante para b), c), e)
    fmt0 = max(por_fmt, key=lambda f: sum(por_fmt[f].values()))
    sel = [p for p in pk if (p.get("rx_format"), p.get("cwb"), p.get("tipo_dato")) == fmt0]
    es16 = fmt0[2] == 1
    raws = [base64.b64decode(p["raw"]) for p in sel]
    valids = [base64.b64decode(p["valid"]) for p in sel]
    if es16:
        R = np.array([extender12(r) for r in raws if len(r) == len(raws[0])])
        V = np.array([np.frombuffer(v, dtype="<i2").astype(np.int32) for v in valids if len(v) == len(valids[0])])
    else:
        R = np.array([np.frombuffer(r, dtype=np.int8).astype(np.int32) for r in raws if len(r) == len(raws[0])])
        V = np.array([np.frombuffer(v, dtype=np.int8).astype(np.int32) for v in valids if len(v) == len(valids[0])])
    comp = np.array([p["comp"] for p in sel][: len(V)], dtype=float)

    # b) posiciones siempre nulas en raw
    nulos = np.where((R == 0).mean(axis=0) >= 0.99)[0].tolist()
    estable = bool(len(R)) and float(((R[:, nulos] == 0).all(axis=1)).mean()) >= 0.95 if nulos else True
    ok_b = estable

    # c) valid vs raw: rangos de esp-radar en BYTES {0,52},{52,104} -> indices de valor segun ancho
    paso = 2 if es16 else 1
    idx = list(range(0 // paso, 52 // paso)) + list(range(52 // paso, 104 // paso))
    ok_c = False
    txt_c = "no comparable (longitudes distintas a la tabla)"
    if R.shape[1] >= max(idx) + 1 and V.shape[1] == len(idx):
        esperado = np.rint(R[:, idx] * comp[:, None])
        err = np.abs(esperado - V)
        frac = float((err <= 1).mean())
        frac_sin_comp = float((np.abs(R[:, idx] - V) <= 1).mean())
        ok_c = frac >= 0.99
        txt_c = (f"{100 * frac:.2f} % de valores con |valid - raw*comp| <= 1 "
                 f"(sin aplicar comp: {100 * frac_sin_comp:.2f} %); comp medio {comp.mean():.3f}")

    # e) emparejamiento (informativo)
    def rugosidad(Vm, desfase):
        x = Vm[:, desfase: desfase + (Vm.shape[1] - desfase) // 2 * 2].reshape(len(Vm), -1, 2)
        amp = np.hypot(x[..., 0], x[..., 1]).astype(float)
        rel = np.abs(np.diff(amp, axis=1)) / np.where(amp[:, 1:] > 0, amp[:, 1:], np.nan)
        return float(np.nanmedian(rel))
    r0, r1 = rugosidad(V.astype(float), 0), rugosidad(V.astype(float), 1)

    registrar("D11a longitud por paquete", "; ".join(txt_a), "constante por formato y coincide con la tabla de IDF",
              "APROBADA" if ok_a else "FALLIDA", f"{len(pk)} paquetes csi")
    registrar("D11b subportadoras nulas", f"posiciones siempre nulas en raw ({'16' if es16 else '8'} bits): {nulos}",
              "conjunto estable (>= 95 % de paquetes)", "APROBADA" if ok_b else "FALLIDA")
    registrar("D11c transformacion raw -> valid", txt_c, ">= 99 % con |error| <= 1",
              "APROBADA" if ok_c else "FALLIDA")
    registrar("D11d ganancias por paquete", f"{con_gan}/{len(pk)} con agc, fft y comp", "100 %",
              "APROBADA" if ok_d else "FALLIDA")
    registrar("D11e orden Re/Im (informativo)", f"rugosidad de amplitud emparejando desde 0: {r0:.3f}, desde 1: {r1:.3f}",
              "no verificable con una sola placa; IDF documenta (Im, Re)", "NO EJECUTADA",
              "el orden Im/Re no se puede distinguir sin referencia externa; la amplitud no depende de el")
    return 0 if (ok_a and ok_b and ok_c and ok_d) else 1


if __name__ == "__main__":
    sys.exit(main())
