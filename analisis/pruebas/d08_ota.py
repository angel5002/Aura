"""D8 - OTA local.

  --caso a  imagen correcta (build\\aura_nodo.bin): respuesta OK, la placa reaparece con la version nueva y
            la telemetria muestra estado_ota = 2 (ESP_OTA_IMG_VALID) en la particion nueva.
  --caso b  clave incorrecta: respuesta "ERROR autenticacion" y la placa sigue en su particion/version.
  --caso c  imagen corrupta (un byte alterado, SHA-256 declarado de la buena): "ERROR sha256", sin cambios.
  --caso d  imagen de prueba que nunca se valida (build_rollback\\aura_nodo.bin, version 0.1.2-rollback):
            arranca, se reinicia a los 30 s sin validarse y el cargador VUELVE a la version anterior.
Estados OTA de IDF: 0 NEW, 1 PENDING_VERIFY, 2 VALID, 3 INVALID, 4 ABORTED, -1/0xFFFFFFFF UNDEFINED.
"""

import argparse
import sys
import time
from pathlib import Path

from comun import Coleccion, recibir_en_hilo, rl
from registrar import registrar

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aura_proto import leer_clave_local  # noqa: E402
from ota_local import enviar_ota          # noqa: E402

PROY = Path(__file__).resolve().parents[2] / "firmware" / "aura_nodo"


def telemetria(ip, id_sesion, segundos=25):
    col = Coleccion()
    h, _ = recibir_en_hilo(ip, id_sesion, segundos, col)
    h.join()
    return col.telemetria[-1][1] if col.telemetria else {}


def esperar_anuncio(timeout=180):
    t0 = time.time()
    an = rl.descubrir(timeout)
    return an, time.time() - t0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--caso", choices=["a", "b", "c", "d"], required=True)
    ap.add_argument("--ip", required=True)
    a = ap.parse_args()
    antes = telemetria(a.ip, f"D8{a.caso}_antes")
    print(f"Antes: version {antes.get('ver')}, particion {antes.get('particion')}, estado_ota {antes.get('estado_ota')}")
    clave = leer_clave_local()

    if a.caso in ("b", "c"):
        img = (PROY / "build" / "aura_nodo.bin").read_bytes()
        import hashlib
        sha = None
        if a.caso == "b":
            r = enviar_ota(a.ip, img, "clave-incorrecta-de-prueba")
            esperado = "ERROR autenticacion"
        else:
            sha = hashlib.sha256(img).hexdigest()
            img = bytearray(img)
            img[len(img) // 2] ^= 0xFF
            r = enviar_ota(a.ip, bytes(img), clave, sha_declarado=sha)
            esperado = "ERROR sha256"
        time.sleep(3)
        despues = telemetria(a.ip, f"D8{a.caso}_despues")
        sin_cambio = despues.get("particion") == antes.get("particion") and despues.get("ver") == antes.get("ver") \
            and despues.get("encendido_s", 0) > antes.get("encendido_s", 0)
        ok = r.startswith(esperado) and sin_cambio
        registrar(f"D8{a.caso} OTA {'clave incorrecta' if a.caso == 'b' else 'imagen corrupta'}",
                  f"respuesta '{r}'; particion {despues.get('particion')}, sin reinicio {sin_cambio}",
                  f"'{esperado}' y sin cambios", "APROBADA" if ok else "FALLIDA")
        return 0 if ok else 1

    if a.caso == "a":
        img = (PROY / "build" / "aura_nodo.bin").read_bytes()
        r = enviar_ota(a.ip, img, clave)
        an, t = esperar_anuncio()
        time.sleep(40)                         # autoprueba: 30 s tras conectar
        despues = telemetria(an["ip"] if an else a.ip, "D8a_despues", 30)
        ok = r.startswith("OK") and despues.get("particion") not in (None, antes.get("particion")) \
            and despues.get("estado_ota") == 2
        registrar("D8a OTA correcta", f"respuesta '{r}'; reaparece en {t:.0f} s; particion {antes.get('particion')} -> "
                  f"{despues.get('particion')}; estado_ota {despues.get('estado_ota')}",
                  "OK, particion nueva y estado_ota=2 (valida)", "APROBADA" if ok else "FALLIDA")
        return 0 if ok else 1

    # caso d
    img_path = PROY / "build_rollback" / "aura_nodo.bin"
    r = enviar_ota(a.ip, img_path.read_bytes(), clave)
    print("Respuesta:", r, "- esperando a la imagen de prueba (version 0.1.2-rollback)...")
    vio_prueba = False
    t0 = time.time()
    version_final = None
    while time.time() - t0 < 240:
        an = rl.descubrir(10)
        if an:
            if an.get("ver") == "0.1.2-rollback":
                vio_prueba = True
            elif vio_prueba:
                version_final = an.get("ver")
                break
    despues = telemetria(a.ip, "D8d_despues", 30) if version_final else {}
    ok = r.startswith("OK") and vio_prueba and version_final == antes.get("ver") \
        and despues.get("particion") == antes.get("particion")
    registrar("D8d vuelta atras automatica", f"respuesta '{r}'; arranco la de prueba: {vio_prueba}; "
              f"version final {version_final}; particion {despues.get('particion')} (antes {antes.get('particion')})",
              "la imagen no validada se revierte sola a la anterior", "APROBADA" if ok else "FALLIDA")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
