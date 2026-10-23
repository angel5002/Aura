"""D6 - Reglas reales: la matriz de T5 por REST contra el proyecto aura-csi.

Usa el sensor de prueba "prueba" (no toca hab1). Pide SIN ECO las credenciales de tu cuenta y de la cuenta
del dispositivo (no se guardan). Al final limpia /sensores/prueba, /crudo/prueba y /comandos/prueba.
Criterio: todos los casos con el resultado esperado (PERMITIDO = HTTP 2xx; DENEGADO = cualquier otro).
"""

import sys
import time
from pathlib import Path

from registrar import registrar

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fb_rest import Sesion, cargar_config, peticion  # noqa: E402

S = "prueba"
SV = {".sv": "timestamp"}
ESTADO = {"estado": "VACIA", "mov": False, "presencia": "vacia", "entrenada": True, "alerta": False, "desde": 1761100000000, "t": SV}
LATIDO = {"t": SV, "up": 10, "heap": 100000, "heap_min": 80000, "red": "principal", "rssi": -50, "ver": "0.1.0",
          "renov": 0, "hms_s": 16.0, "ts_p95": 61.0, "reinicio": "encendido"}
COMANDO_RES = {"id": "-Nabc123", "cmd": "RESET_BASELINE", "ok": True, "detalle": "ESP_OK", "origen": "nube", "t": SV}
BLOQUE = {"t0": 1761100000000, "t1": 1761100010000, "n": 160, "mov": 0, "pres": 0, "ncsi": 1000, "nsub": 52,
          "jit": "12,13,14", "am": "1.0,2.0", "ad": "0.1,0.2"}
CMD = {"cmd": "RESET_BASELINE", "t": SV}
K = "1761100000000"


def main() -> int:
    cfg = cargar_config()
    usuario = Sesion(cfg, etiqueta="USUARIO (tu cuenta)")
    placa = Sesion(cfg, etiqueta="DISPOSITIVO (cuenta de la placa)")
    if usuario.uid == placa.uid:
        print("ERROR: las dos cuentas tienen el mismo UID")
        return 1
    casos = [
        (1, "sin auth lee /sensores", None, "GET", f"/sensores/{S}", None, "DENEGADO"),
        (2, "sin auth escribe estado", None, "PUT", f"/sensores/{S}/estado", ESTADO, "DENEGADO"),
        (3, "sin auth lee /crudo", None, "GET", f"/crudo/{S}", None, "DENEGADO"),
        (4, "sin auth escribe /comandos", None, "PUT", f"/comandos/{S}/c0", CMD, "DENEGADO"),
        (5, "sin auth lee /comandos", None, "GET", f"/comandos/{S}", None, "DENEGADO"),
        (6, "sin auth lee la raiz", None, "GET", "", None, "DENEGADO"),
        (7, "placa escribe estado", placa, "PUT", f"/sensores/{S}/estado", ESTADO, "PERMITIDO"),
        (8, "placa escribe latido", placa, "PUT", f"/sensores/{S}/latido", LATIDO, "PERMITIDO"),
        (9, "placa escribe comando", placa, "PUT", f"/sensores/{S}/comando", COMANDO_RES, "PERMITIDO"),
        (10, "placa escribe bloque", placa, "PUT", f"/crudo/{S}/{K}", BLOQUE, "PERMITIDO"),
        (11, "placa lee /comandos", placa, "GET", f"/comandos/{S}", None, "PERMITIDO"),
        (12, "placa escribe /comandos", placa, "PUT", f"/comandos/{S}/c1", CMD, "DENEGADO"),
        (13, "placa lee /sensores", placa, "GET", f"/sensores/{S}", None, "DENEGADO"),
        (14, "usuario lee /sensores", usuario, "GET", f"/sensores/{S}", None, "PERMITIDO"),
        (15, "usuario lee /crudo", usuario, "GET", f"/crudo/{S}", None, "PERMITIDO"),
        (16, "usuario escribe /comandos", usuario, "PUT", f"/comandos/{S}/c2", CMD, "PERMITIDO"),
        (17, "usuario escribe estado", usuario, "PUT", f"/sensores/{S}/estado", ESTADO, "DENEGADO"),
        (18, "usuario escribe datos en /crudo", usuario, "PUT", f"/crudo/{S}/1761100020000", BLOQUE, "DENEGADO"),
        (19, "usuario lee /comandos", usuario, "GET", f"/comandos/{S}", None, "DENEGADO"),
        (20, "usuario borra un bloque", usuario, "DELETE", f"/crudo/{S}/{K}", None, "PERMITIDO"),
        (21, "usuario borra /crudo completo", usuario, "DELETE", f"/crudo/{S}", None, "DENEGADO"),
        (22, "usuario borra un comando", usuario, "DELETE", f"/comandos/{S}/c2", None, "PERMITIDO"),
        (25, "estado con campo extra", placa, "PUT", f"/sensores/{S}/estado", {**ESTADO, "x": 1}, "DENEGADO"),
        (26, "estado con valor no permitido", placa, "PUT", f"/sensores/{S}/estado", {**ESTADO, "estado": "BAILANDO"}, "DENEGADO"),
        (27, "estado sin campo obligatorio", placa, "PUT", f"/sensores/{S}/estado",
         {k: v for k, v in ESTADO.items() if k != "alerta"}, "DENEGADO"),
        (28, "bloque con jit de 5000 caracteres", placa, "PUT", f"/crudo/{S}/{K}", {**BLOQUE, "jit": "1" * 5000}, "DENEGADO"),
        (29, "bloque con clave no numerica", placa, "PUT", f"/crudo/{S}/abc", BLOQUE, "DENEGADO"),
        (30, "comando no permitido", usuario, "PUT", f"/comandos/{S}/c4", {"cmd": "FORMAT_FLASH", "t": SV}, "DENEGADO"),
        (31, "comando con t fijo", usuario, "PUT", f"/comandos/{S}/c5", {"cmd": "RESET_BASELINE", "t": 123}, "DENEGADO"),
        (32, "comando con campo extra", usuario, "PUT", f"/comandos/{S}/c6", {**CMD, "x": 1}, "DENEGADO"),
        (33, "latido con version de 40 caracteres", placa, "PUT", f"/sensores/{S}/latido", {**LATIDO, "ver": "v" * 40}, "DENEGADO"),
        (34, "sensor con id invalido", placa, "PUT", "/sensores/Hab-1!/estado", ESTADO, "DENEGADO"),
        (35, "comando SET_CFG valido", usuario, "PUT", f"/comandos/{S}/c7", {"cmd": "SET_CFG AP motion_sensitivity=0.4", "t": SV}, "PERMITIDO"),
        (36, "presencia 'vacia' sin entrenar", placa, "PUT", f"/sensores/{S}/estado",
         {**ESTADO, "estado": "SIN_MOVIMIENTO", "entrenada": False, "presencia": "vacia"}, "DENEGADO"),
        (37, "presencia 'no_disponible' sin entrenar", placa, "PUT", f"/sensores/{S}/estado",
         {**ESTADO, "estado": "SIN_MOVIMIENTO", "entrenada": False, "presencia": "no_disponible"}, "PERMITIDO"),
        (38, "estado VACIA sin entrenar", placa, "PUT", f"/sensores/{S}/estado",
         {**ESTADO, "estado": "VACIA", "entrenada": False, "presencia": "no_disponible"}, "DENEGADO"),
        (39, "presencia con valor no permitido", placa, "PUT", f"/sensores/{S}/estado", {**ESTADO, "presencia": "quizas"}, "DENEGADO"),
    ]
    malos = []
    for n, desc, ses, metodo, ruta, cuerpo, esperado in casos:
        codigo, _ = peticion(cfg, metodo, ruta, ses, cuerpo=cuerpo)
        obtenido = "PERMITIDO" if 200 <= codigo < 300 else "DENEGADO"
        print(f"{'OK   ' if obtenido == esperado else 'FALLA'} {n:2}. {desc}: esperado {esperado}, obtenido {obtenido} (HTTP {codigo})")
        if obtenido != esperado:
            malos.append(str(n))
        time.sleep(0.2)
    # Limpieza (solo nodos de prueba)
    peticion(cfg, "DELETE", f"/sensores/{S}", placa)
    for c in ("c0", "c1", "c2", "c4", "c5", "c6", "c7"):
        peticion(cfg, "DELETE", f"/comandos/{S}/{c}", usuario)
    peticion(cfg, "DELETE", f"/crudo/{S}/{K}", usuario)
    total = len(casos)
    registrar("D6 reglas reales (REST, sensor 'prueba')", f"{total - len(malos)}/{total} como se espera",
              "todos los casos", "APROBADA" if not malos else "FALLIDA",
              ("casos con otro resultado: " + ", ".join(malos)) if malos else "")
    return 0 if not malos else 1


if __name__ == "__main__":
    sys.exit(main())
