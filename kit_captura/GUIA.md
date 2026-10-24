# Kit de captura portátil de AURA (modo solo local, captura por USB)

Versión del kit: ver el archivo `VERSION` (cambios en `CAMBIOS.md`). **Solo Windows 10/11** con **Python 3.12 de
64 bits** (probado con 3.12.10; no usar 3.13 ni 3.11: las versiones fijadas de `requirements.txt` son las probadas).

Para usar en cualquier PC o laptop con Windows, también **ajena**. El kit **no trae ningún secreto**: ni la configuración de
Firebase, ni la clave local, ni contraseñas. Las contraseñas del WiFi se escriben en el momento, sin eco, y van
directo a la placa por USB; no quedan guardadas en la laptop.

Contenido:

| Archivo | Para qué |
|---|---|
| `scripts\capturar.py` | Captura cruda del USB a `datos\crudos\<ID>.csv` |
| `scripts\cargar_credenciales.py` | Carga el WiFi del lugar en la placa (`--solo wifi1_ssid`, …) |
| `scripts\visor.py` | Panel EN VIVO (mapa de calor, señal, estado; teclas E/S/M; graba) y reproducción |
| `scripts\marcas_a_etiquetas.py`, `scripts\convertir_log_celular.py` | Marcas de teclado → etiquetas; registro del celular → formato de captura |
| `GUIA_CAMPO.md` | Guía de campo de una página (salón, laptop ajena, plan B) |
| `scripts\ip_placa_usb.py` | Lee por USB la IP que obtuvo la placa (para el paso 4b) |
| `scripts\receptor_local.py` | Recibe por WiFi el CSI crudo (mapa de calor) conectándose a la IP de la placa |
| `scripts\verificar_kit.py` | **Un comando que comprueba todo** (Python, dependencias, placa, USB, IP, red) y dice qué falla y cómo arreglarlo |
| `scripts\aura_proto.py`, `scripts\fb_rest.py` | Módulos que usan los anteriores (sin datos) |
| `requirements.txt` | pyserial, numpy y matplotlib con versiones **fijadas** (`==`) |
| `VERSION`, `CAMBIOS.md` | Versión del kit e historial de cambios |

**El puerto se detecta solo**: todos los scripts buscan la placa por su identificador USB de Espressif (VID `303A`),
así que no hace falta averiguar el COM. Si hubiera **dos placas** conectadas, el script lo dice y hay que indicar
una con `--puerto COMx`. En el visor, `--puerto auto` activa la lectura por USB.

## 1. Instalar Python (una vez, ~10 min, con internet)

1. Descarga **Python 3.12.10 para Windows (64-bit)** desde <https://www.python.org/downloads/windows/>
   (es la misma versión del proyecto; cualquier 3.12.x de 64 bits sirve).
2. En el instalador marca **"Add python.exe to PATH"** y pulsa **Install Now** (incluye Tk, que usa la ventana
   del visor). Si la PC ya tiene otro Python, no pasa nada: `py -3.12` elige el 3.12.
3. Copia la carpeta del kit a una ruta **sin espacios ni tildes**, por ejemplo `C:\aura_kit`.
4. Abre **PowerShell** y ejecuta:

```powershell
cd C:\aura_kit
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Si PowerShell bloquea scripts, no hace falta activarlos: siempre se usa `.\.venv\Scripts\python.exe` directo.

## 2. Conectar la placa y verificar el kit (un solo comando)

1. Conecta la placa B con un cable USB-C **de datos** (no solo de carga). Windows 10/11 la reconoce sin
   instalar drivers (USB Serial/JTAG).
2. Con la laptop en el **mismo WiFi** que la placa, ejecuta:

```powershell
.\.venv\Scripts\python.exe scripts\verificar_kit.py
```

   En ~1 minuto revisa, en este orden: Windows y Python 3.12 de 64 bits; las dependencias y sus versiones; Tk;
   la placa por USB (VID 303A); recepción USB durante 10 s (versión del firmware, red, muestras/s); la IP de la
   placa; si la laptop está en la misma red; y recepción por la red durante 10 s (CSI/s y pérdida).
   - La IP solo la informa la placa al conectarse al WiFi: si no la ve, **pregunta** si puede reiniciar la placa
     (`AURA REBOOT`, ~1 min). Para no preguntar: `--reiniciar`; para no reiniciar nunca: `--sin-reiniciar`.
   - No cambia la configuración de la placa ni graba nada en ella.
   - Al final imprime cada prueba como **OK**, **AVISO** o **FALLA**, con la **solución sugerida**, y guarda el
     informe en `verificacion_<fecha>.txt` (en la raíz del kit). Termina con `RESULTADO: TODO FUNCIONA` si está todo bien.
   - Si solo falla la red (misma red, recepción por red), el plan B solo USB sigue sirviendo.
3. (Opcional) Ver el COM a mano: `.\.venv\Scripts\python.exe -m serial.tools.list_ports -v` (busca `303A:1001`).

## 2b. Prueba de 10 minutos en casa (laptop nueva, por ejemplo la HP)

Hazla en casa antes de salir, con la placa conectada por USB y la laptop en el **mismo WiFi** que la placa.

| Min | Paso | Éxito |
|---|---|---|
| 0–2 | `.\.venv\Scripts\python.exe scripts\verificar_kit.py --reiniciar` | `RESULTADO: TODO FUNCIONA`; anota la IP de la placa del informe; espera 1 min |
| 2–4 | `.\.venv\Scripts\python.exe scripts\cargar_credenciales.py --listar` | muestra los nombres de las claves |
| 4–8 | `.\.venv\Scripts\python.exe scripts\visor.py --vivo --ip <IP> --puerto auto --id-sesion PRUEBA_HP` | mapa de calor que se mueve, señal y umbrales; al caminar cerca, la señal sube. Pulsa **E**, **S** y **M**: aparecen arriba a la izquierda |
| 8–9 | Cierra la ventana; revisa `datos\crudos\` | están `PRUEBA_HP.csv`, `PRUEBA_HP_local.csv` y `PRUEBA_HP_marcas.csv` |
| 9–10 | `.\.venv\Scripts\python.exe scripts\visor.py --reproducir datos\crudos\PRUEBA_HP_local.csv` | el panel se reconstruye |

Si falla el paso de la IP o el mapa de calor, el plan B (solo USB) sigue sirviendo: `visor.py --vivo --puerto auto`.

## 3. Cargar el WiFi del lugar (red principal)

```powershell
.\.venv\Scripts\python.exe scripts\cargar_credenciales.py --solo wifi1_ssid
.\.venv\Scripts\python.exe scripts\cargar_credenciales.py --solo wifi1_pass --reiniciar
```

- Cada valor se pide **dos veces y sin eco**; si no coinciden, se vuelve a preguntar y no se envía nada.
- No necesita `firebase_web.json` (no está en el kit y no hace falta para el WiFi).
- La red de respaldo (`wifi2_*`, tu hotspot) ya está cargada desde casa; si hay que cambiarla:
  `--solo wifi2_ssid` y `--solo wifi2_pass`.
- **Al volver a casa**, vuelve a cargar `wifi1_ssid` y `wifi1_pass` de la casa (esto reemplazó a la red de casa).

## 4. Capturar durante la grabación

1. Inicia la captura **antes** de empezar a grabar (ejemplo: 40 min = 2400 s):

```powershell
.\.venv\Scripts\python.exe scripts\capturar.py --id-sesion V001 --duracion 2400
```

2. Espera a que la placa lleve ~1 min encendida (calibración) antes de la primera escena.
3. **Palmada de sincronización**: al empezar, frente a la cámara y a ~1 m de la placa, da **una palmada fuerte
   con un movimiento amplio de brazos** y quédate quieto 5 s. En el video se ve y se oye; en la captura aparece
   como un pico de la señal. Repite una palmada al final.
4. No cierres la ventana de PowerShell ni desconectes el USB durante la grabación. Si se desconecta, el script
   se reconecta solo y lo anota en el archivo.
5. El archivo queda en `C:\aura_kit\datos\crudos\V001.csv`. Si `V001` ya existe, usa otro ID (no se sobrescribe).

## 4b. (Opcional) Recibir también el CSI crudo por WiFi, para el mapa de calor

Por USB no llega el CSI crudo. Para tener el mapa de calor, la laptop recibe además la vía local de la placa
**conectándose directamente a su IP**: no usa el descubrimiento por broadcast, **no necesita ninguna regla de
firewall ni permisos de administrador** (probado el 24/10/2026 con la regla desactivada: 5 min, 0 % de pérdida,
~100 paquetes CSI/s).

**Condición: la laptop debe estar conectada a la MISMA red WiFi que la placa** (la del departamento, o tu hotspot
si la placa está en el respaldo). En redes de invitados que aíslan a los clientes entre sí no funciona: en ese
caso graba solo con USB (paso 4).

Orden (el puerto COM no se puede abrir desde dos programas a la vez):

1. Con la placa ya conectada al WiFi, lee su IP por USB (si no la ve en 5 s, reinicia la placa y espera ~15 s):

```powershell
.\.venv\Scripts\python.exe scripts\ip_placa_usb.py --reiniciar
```

   Muestra algo como `192.168.1.23`. Si se reinició la placa, espera **1 minuto** (calibración).
2. En una **primera** ventana de PowerShell, la captura USB (paso 4).
3. En una **segunda** ventana, el receptor por WiFi con la misma duración:

```powershell
.\.venv\Scripts\python.exe scripts\receptor_local.py --id-sesion V001 --duracion 2400 --ip 192.168.1.23 --sin-bind
```

   Cada 5 s muestra `csi ~100/s, hms ~17/s | perdida 0.00%`. Si `csi` no aparece en 15 s, revisa que la laptop
   esté en la misma red; si no se puede, sigue solo con USB.
4. El archivo queda en `datos\crudos\V001_local.csv`.

En la prueba del 24/10 Windows no mostró ningún aviso. Si aparece una ventana de **Seguridad de Windows**, no hace
falta permitir nada: ciérrala y comprueba que el receptor siga mostrando `csi ~100/s`.

## 5. Reconstruir el panel (modo reproducción)

Para ver el panel en pantalla:

```powershell
.\.venv\Scripts\python.exe scripts\visor.py --reproducir datos\crudos\V001.csv
```

Para exportar un PNG por cuadro (10 por segundo) y montarlo sobre el video:

```powershell
.\.venv\Scripts\python.exe scripts\visor.py --reproducir datos\crudos\V001.csv --exportar cuadros_V001 --fps 10
```

- Cada PNG lleva en el nombre la hora de la laptop en milisegundos (`cuadro_<ms>.png`) y al pie el rótulo
  **"Reproducción de datos registrados durante la grabación"**.
- Por USB no llega el CSI crudo: el mapa de calor queda vacío y el panel muestra la señal del detector, sus
  umbrales y el estado.
- **Si hiciste el paso 4b**, reproduce el archivo de la vía local, que trae el CSI crudo y las muestras del
  detector (panel completo, con mapa de calor):
  `.\.venv\Scripts\python.exe scripts\visor.py --reproducir datos\crudos\V001_local.csv --exportar cuadros_V001 --fps 10`.
  Su hora es la de la placa (SNTP); alinéalo igual con la palmada. Guarda también `V001.csv` (USB) como respaldo.
- Para alinear: busca el pico de la palmada en el panel y hazlo coincidir con la palmada del video.

## 6. Al terminar (datos sensibles)

- Las capturas son datos de una sesión con personas: copia `datos\crudos\` a una memoria propia o a la PC del
  proyecto (`C:\aura\datos\crudos\`) y **bórralos de la laptop prestada**. No los subas a ningún servicio.
- Borra también la carpeta del kit si la laptop no es tuya (no contiene secretos, pero tampoco hace falta dejarla).
