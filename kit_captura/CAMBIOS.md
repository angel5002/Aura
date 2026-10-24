# Cambios del kit de captura de AURA

Solo Windows 10/11 con Python 3.12 de 64 bits. La versión está en el archivo `VERSION` y en el nombre del zip
(`kit_captura_aura_v<versión>.zip`).

## 1.1.0 — 24/10/2026

- **Dependencias fijadas** en `requirements.txt` con las versiones probadas en la PC del proyecto (Python 3.12.10):
  pyserial 3.5, numpy 2.5.4, matplotlib 3.11.2 y sus dependencias, todas con `==`.
- **`--puerto auto`** (por defecto) en todos los scripts que usan la placa: la detectan por el VID USB de
  Espressif (`303A`). Ya no hace falta averiguar el COM. Si hay más de una placa conectada, el script se detiene
  y pide `--puerto COMx`.
- **`scripts\verificar_kit.py`**: un comando que revisa Python, las dependencias, Tk (ventana del visor), la placa
  por USB, la recepción USB (10 s), la IP de la placa, si la PC está en la misma red y la recepción por la red
  (10 s). Imprime un informe con OK / AVISO / FALLA y la solución sugerida, y lo guarda en
  `verificacion_<fecha>.txt`. No cambia la configuración de la placa; para leer la IP puede reiniciarla, y antes lo
  pregunta (`--reiniciar` para no preguntar, `--sin-reiniciar` para no reiniciarla nunca).
- **Estado de la prueba: verificar_kit.py probado sin placa; la verificación con placa se hará en la laptop
  prestada.** En la PC del proyecto se comprobó solo la parte sin placa (Python, dependencias, Tk, aviso de "no
  hay placa" con su solución). La recepción USB, la lectura de la IP y la recepción por red **no están verificadas
  con placa** en esta versión.
- Archivos `VERSION` y `CAMBIOS.md`.
- `GUIA.md` y `PARA_CLAUDE_CODE.md` actualizados (instalación, verificación, puerto automático).
- Corregido: `LectorSerie` buscaba el puerto dos veces al abrirlo.

## 1.0.0 — 24/10/2026 (commit dd3a3c4)

- Primera versión del kit portátil: captura USB, visor en vivo (mapa de calor, teclas E/S/M) y reproducción,
  receptor de la vía local por IP directa (sin regla de firewall), carga de credenciales WiFi, guías y
  `PARA_CLAUDE_CODE.md`.
