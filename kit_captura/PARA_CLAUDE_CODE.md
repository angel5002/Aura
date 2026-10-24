# Contexto para Claude Code en la laptop de captura (kit portátil de AURA)

Responde en **español**. Este kit sirve para **capturar y visualizar** señales de una placa ESP32-C5. **No** es el
proyecto completo: el firmware, las pruebas y los secretos están en otra PC.

## El proyecto

AURA es un proyecto universitario de investigación (Lima, Perú): detección de **actividad humana** (movimiento) con
WiFi CSI usando una placa **DFRobot FireBeetle 2 ESP32-C5** y el componente `esp_wifi_sensing` de Espressif. La
placa calcula la detección a bordo y la envía por **USB** (líneas `HMS:{...}`) y por la **vía local** (UDP en la
misma red WiFi, con el CSI crudo). La presencia quieta **no es fiable** en estas pruebas y el visor la muestra como
"no disponible".

## La placa B (la única que se usa)

| Dato | Valor |
|---|---|
| MAC | `3c:dc:75:8a:6f:cc` |
| USB | nativo USB Serial/JTAG, VID:PID `303A:1001` (CDC-ACM, sin drivers en Windows 10/11) |
| Firmware | `aura_nodo` **0.1.3** en **modo solo local**: sin credenciales de Firebase (no abre conexiones a la nube) |
| Redes cargadas | `wifi1` (principal) = WiFi de la casa de la investigadora; `wifi2` (respaldo) = hotspot de su celular. **Las contraseñas no están en este kit y no se deben pedir ni mostrar** |
| Sin la red principal | pasa sola al hotspot tras 3 intentos fallidos (estimado 45–70 s, no medido) y busca la principal cada 15 min |
| Vía local | UDP 45454: se envía `SUB <nombre>` a la IP de la placa (se renueva cada 10 s) y la placa responde a ese mismo puerto con datagramas `A1 <seq> <t_us> <tipo> <cuerpo>`; anuncios por broadcast en UDP 45455 |

## Formato del CSI (verificado con datos reales el 24/10/2026)

Paquetes `csi` de la vía local (JSON con `raw` y `valid` en base64): **LLTF de 20 MHz**, `raw` = 106 bytes = 53
palabras de 16 bits con **valores de 12 bits con signo** (modo `lltf_bit_mode` = 0, por defecto); la palabra 53 es
relleno. `valid` = 52 valores = **26 subportadoras complejas (imaginario, real)**, multiplicadas por `comp`.
Coincide con esp-radar y con el parser oficial de esp-csi para el C5. `aura_proto.decodificar_csi()` lo decodifica.
**No inventar otro formato.**

## Estructura del kit

Todo se ejecuta desde la **raíz del kit** (ruta sin espacios, p. ej. `C:\aura_kit`) con `.\.venv\Scripts\python.exe`.
Las capturas quedan en `datos\crudos\`.

| Archivo | Uso |
|---|---|
| `scripts\visor.py` | `--vivo` (mapa de calor + señal y umbrales + estado; teclas **E**/**S**/**M**; graba) y `--reproducir` |
| `scripts\receptor_local.py` | Recibe la vía local: `--ip <IP> --sin-bind` (sin descubrimiento, sin firewall) |
| `scripts\ip_placa_usb.py` | Lee por USB la IP de la placa (`--reiniciar` la reinicia si hace falta) |
| `scripts\capturar.py` | Captura USB a CSV; `--teclas` para marcar E/S/M en consola |
| `scripts\cargar_credenciales.py` | Cambia el WiFi de la placa (`--solo wifi1_ssid`, …); `--listar` solo muestra nombres de claves |
| `scripts\prueba_hotspot.py` | Mide el arranque hasta tener red: usar **solo `--modo reinicio`** (el modo `sim` necesita la clave local, que este kit no trae a propósito) |
| `scripts\marcas_a_etiquetas.py`, `scripts\convertir_log_celular.py` | Marcas de teclado → etiquetas; registro del celular → CSV de captura |
| `scripts\aura_proto.py`, `comando_local.py`, `fb_rest.py` | Módulos usados por los anteriores |
| `GUIA.md`, `GUIA_CAMPO.md`, `docs\guia_salon.md` | Instalación, prueba de 10 min, guía de campo, prueba en el salón (las rutas `C:\aura\analisis\...` de la guía del salón equivalen a `scripts\` aquí) |

## Comandos de uso

```powershell
.\.venv\Scripts\python.exe -m serial.tools.list_ports -v                              # COM de 303A:1001
.\.venv\Scripts\python.exe scripts\cargar_credenciales.py --puerto COMx --listar     # solo nombres de claves
.\.venv\Scripts\python.exe scripts\ip_placa_usb.py --puerto COMx --reiniciar          # IP (reinicia: esperar 1 min)
.\.venv\Scripts\python.exe scripts\visor.py --vivo --ip <IP> --puerto COMx --id-sesion C001   # en vivo + graba
.\.venv\Scripts\python.exe scripts\visor.py --vivo --puerto COMx --id-sesion C001             # plan B solo USB
.\.venv\Scripts\python.exe scripts\capturar.py --puerto COMx --id-sesion C001 --duracion 1800 --teclas
.\.venv\Scripts\python.exe scripts\visor.py --reproducir datos\crudos\C001_local.csv --exportar cuadros_C001 --fps 10
```

El puerto COM solo lo puede abrir un programa a la vez (primero `ip_placa_usb.py`, después el visor o la captura).
Nunca se sobrescriben capturas: si el ID existe, usar otro.

## Reglas (obligatorias)

1. **No grabar firmware** en la placa (nada de `esptool`, `idf.py flash`, OTA ni borrados de flash).
2. **No modificar la configuración de la placa sin permiso explícito** de la investigadora: nada de
   `cargar_credenciales.py` (salvo `--listar`), `AURA SET/DEL`, `RESET_BASELINE`, `TRAIN_*`, `SET_CFG` ni `SIM_*`.
   Reiniciar la placa (`--reiniciar`) se avisa antes.
3. **No subir datos a ninguna nube** ni servicio externo (ni git remoto, ni almacenamiento en línea). Las capturas son
   datos de sesiones con personas: se quedan en `datos\crudos\` y se copian a la memoria de la investigadora.
4. **Nunca pedir, escribir, mostrar ni registrar contraseñas** (WiFi, cuentas). Las escribe ella en los prompts sin eco.
5. Antes de instalar cualquier programa (además de `pip install -r requirements.txt`) o borrar archivos: explicar y
   esperar confirmación. Rutas sin espacios ni tildes.
6. Sesiones guiadas a distancia: no programar horas ni iniciar cuentas regresivas hasta que ella responda **"listo"**;
   empezar al menos 2 min después.
7. Si algo falla, mostrar el error completo y proponer una solución; no reintentar en bucle. No marcar pruebas como
   aprobadas ni ajustar criterios.
