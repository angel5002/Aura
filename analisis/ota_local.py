"""Actualiza el firmware de la placa por la red local (OTA autenticada con la clave compartida).

Envia la cabecera "AURAOTA <ctr> <tamano> <sha256> <hmac>" y la imagen .bin por TCP (puerto 45456).
La placa verifica el HMAC, calcula el SHA-256 mientras recibe y solo activa la imagen si coincide.

Ejemplos:
    python C:\\aura\\analisis\\ota_local.py --ip 192.168.0.13 C:\\aura\\firmware\\aura_nodo\\build\\aura_nodo.bin
    python C:\\aura\\analisis\\ota_local.py --ip ... --clave-erronea  build\\aura_nodo.bin      (prueba D8b)
    python C:\\aura\\analisis\\ota_local.py --ip ... --corromper      build\\aura_nodo.bin      (prueba D8c)
"""

import argparse
import hashlib
import socket
import sys
import time
from pathlib import Path

from aura_proto import PUERTO_OTA, cabecera_ota, leer_clave_local


def enviar_ota(ip: str, imagen: bytes, clave: str, sha_declarado: str | None = None, puerto: int = PUERTO_OTA,
               timeout: float = 120) -> str:
    sha = sha_declarado or hashlib.sha256(imagen).hexdigest()
    with socket.create_connection((ip, puerto), timeout=timeout) as s:
        s.sendall(cabecera_ota(clave, len(imagen), sha).encode())
        f = s.makefile("rb")
        primera = f.readline().decode(errors="replace").strip()
        if primera != "LISTO":
            return primera or "sin respuesta"
        enviado = 0
        t0 = time.time()
        while enviado < len(imagen):
            n = s.send(imagen[enviado:enviado + 4096])
            enviado += n
            if enviado % (256 * 1024) < 4096:
                print(f"  {enviado / len(imagen) * 100:5.1f} %  ({enviado / 1024 / (time.time() - t0 + 1e-9):.0f} KB/s)")
        return f.readline().decode(errors="replace").strip() or "sin respuesta final"


def main() -> int:
    ap = argparse.ArgumentParser(description="OTA local autenticada.")
    ap.add_argument("--ip", required=True)
    ap.add_argument("imagen", type=Path)
    ap.add_argument("--clave-erronea", action="store_true", help="firmar con una clave falsa (prueba D8b)")
    ap.add_argument("--corromper", action="store_true",
                    help="declarar el SHA-256 de la imagen buena pero enviar una imagen alterada (prueba D8c)")
    args = ap.parse_args()
    imagen = args.imagen.read_bytes()
    clave = "clave-incorrecta-de-prueba" if args.clave_erronea else leer_clave_local()
    sha = None
    if args.corromper:
        sha = hashlib.sha256(imagen).hexdigest()
        imagen = bytearray(imagen)
        imagen[len(imagen) // 2] ^= 0xFF          # un byte alterado en medio de la imagen
        imagen = bytes(imagen)
    print(f"Imagen: {args.imagen} ({len(imagen)} bytes)")
    r = enviar_ota(args.ip, imagen, clave, sha_declarado=sha)
    print("Respuesta de la placa:", r)
    return 0 if r.startswith("OK") else 2


if __name__ == "__main__":
    sys.exit(main())
