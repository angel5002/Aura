"""Autoprueba del detector PEM de T3 (sin placa): demuestra que la exclusion es minima.

Casos que DEBEN contar como secreto (fallo de T3) y casos que se excluyen.
"""

import sys

from t3_secretos import contar_pem

B64 = b"MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7" * 2

CASOS = [
    ("constante RSA de mbedTLS sin base64", b"\0-----BEGIN RSA PRIVATE KEY-----\0", (0, 1)),
    ("constante EC de mbedTLS sin base64", b"\0-----BEGIN EC PRIVATE KEY-----\0", (0, 1)),
    ("constante PKCS8 de mbedTLS sin base64", b"\0-----BEGIN PRIVATE KEY-----\0", (0, 1)),
    ("RSA seguida de base64", b"-----BEGIN RSA PRIVATE KEY-----\n" + B64, (1, 0)),
    ("PKCS8 seguida de base64", b"-----BEGIN PRIVATE KEY-----\r\n" + B64, (1, 0)),
    ("constante ENCRYPTED de mbedTLS sin base64", b"\0-----BEGIN ENCRYPTED PRIVATE KEY-----\0", (0, 1)),
    ("ENCRYPTED seguida de base64", b"-----BEGIN ENCRYPTED PRIVATE KEY-----\n" + B64, (1, 0)),
    ("encabezado no excluido (DSA)", b"\0-----BEGIN DSA PRIVATE KEY-----\0", (1, 0)),
    ("encabezado no excluido (OPENSSH)", b"-----BEGIN OPENSSH PRIVATE KEY-----\0", (1, 0)),
]


def main() -> int:
    fallas = 0
    for nombre, datos, esperado in CASOS:
        r = contar_pem(datos)
        ok = r == esperado
        fallas += not ok
        print(f"{'OK   ' if ok else 'FALLA'} {nombre}: (cuentan, excluidas) = {r}, esperado {esperado}")
    print(f"{len(CASOS) - fallas}/{len(CASOS)} casos correctos")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
