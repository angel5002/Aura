# Guía de placas: instalar, conectar, identificar y grabar

Para quien nunca ha grabado un ESP32 con ESP-IDF. Placas: DFRobot FireBeetle 2 ESP32-C5 (DFR1222).
Todas las rutas son absolutas bajo `C:\aura`. **No muevas el proyecto:** ESP-IDF falla con rutas que
tienen espacios.

| Rótulo | MAC esperada        |
|--------|---------------------|
| A      | `D0:CF:13:E8:FF:88` |
| B      | `3C:DC:75:8A:6F:CC` |
| C      | `3C:DC:75:8A:6D:24` |

Datos de la placa (wiki DFR1222): USB-C de 5 V, LED de usuario en **GPIO 15**, botón **BOOT = GPIO 28**,
botón **RST**, conector de batería de litio **BAT (3,7–4,2 V)** con carga de hasta 0,5 A y pin **VIN**
(5 V o panel solar de 4,5–6 V).

---

## 0. Instalar ESP-IDF v5.5 con EIM (una sola vez)

EIM 0.20.1 ya está instalado (lo instalé con `winget install --id Espressif.eim -e`).

1. Libera espacio si hace falta: ESP-IDF con sus herramientas ocupa varios GB y en `C:` quedan
   ~19,7 GB libres.
2. Abre el menú Inicio, busca **eim** y ábrelo. Si Windows pregunta por el Firewall o pide permisos,
   acéptalo.
3. En la pantalla inicial **no elijas la instalación simplificada**: la documentación de EIM no dice qué
   versión instala, y probablemente sea la más reciente (v6.x), que esp-csi no compila para el C5.
   Elige la **instalación experta** ("Expert Installation").
4. **Prerequisites Check:** el asistente revisa Git y Python (acepta Python 3.10–3.14; tienes 3.12).
   Si marca algo en rojo, haz una captura y envíamela antes de seguir.
5. **Destinos (targets):** si aparece la lista de chips, marca **esp32c5** (puedes dejar los demás, pero
   ocupan más espacio).
6. **Versión de ESP-IDF:** elige la **v5.5.x más alta que ofrezca la lista** (por ejemplo, v5.5.6 o
   v5.5.5). **No elijas v6.x ni "master".** La documentación de EIM no muestra esta pantalla; si no la
   ves o tiene otro nombre, detente y envíame una captura.
7. **Mirror (servidor de descarga):** deja GitHub. Si la descarga es muy lenta, prueba el mirror de
   Espressif.
8. **Select Installation Path:** deja **`C:\esp`**. Debe tener menos de 90 caracteres, sin espacios ni
   paréntesis; `C:\esp` cumple. No cambies las carpetas avanzadas (`dist`, `tools`). No pongas la
   instalación dentro de `C:\aura` ni en `E:\...\Proyectos Borrables\...`, que tiene espacios.
9. **Instalación:** pasará por Check, Prerequisites, Download, Submodules, Tools, Python, Configure y
   Complete. Puede tardar entre 15 y 40 minutos. Si falla, copia el texto completo del error.
10. **Installation Complete:** confirma la versión (v5.5.x) y la ruta, y pulsa **Complete Installation**.
11. EIM crea un **acceso directo de PowerShell de ESP-IDF** (en el escritorio o en el menú Inicio) y un
    perfil `Microsoft.v5.5.x.PowerShell_profile.ps1`. **Todos los comandos `idf.py` y `esptool.py` de
    esta guía se ejecutan en esa ventana**, no en una PowerShell normal.
12. Comprueba en esa ventana:

    ```powershell
    idf.py --version
    ```

    Debe responder `ESP-IDF v5.5.x`. Si dice "running scripts is disabled", ejecuta una vez
    `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

---

## 1. El cable

1. Necesitas un cable **USB-C de datos**. Muchos cables de carga solo traen los hilos de alimentación.
2. Prueba rápida: si con ese cable tu celular aparece como dispositivo en la PC (transferencia de
   archivos), es de datos.
3. Prueba con la placa: al conectarla, Windows debe hacer el **sonido de conexión** y aparecer un puerto
   COM nuevo (paso 2). Si la placa enciende su LED de alimentación pero **no aparece ningún dispositivo**,
   el cable es solo de carga. Cámbialo.
4. Conecta la placa **directamente a la PC**, sin hub USB, al menos en la primera prueba.

## 2. Una placa a la vez: COM, VID y MAC

Conecta **solo una placa**. Así sabrás con certeza a qué placa corresponde el puerto nuevo.

1. Abre el Administrador de dispositivos: clic derecho en Inicio → **Administrador de dispositivos**.
2. Despliega **Puertos (COM y LPT)**. Debe aparecer algo como **"Dispositivo serie USB (COM5)"**; el
   número puede ser otro. Ese es el puerto de la placa. Ignora `COM1` (puerto de la PC) y
   `Intel(R) Active Management Technology - SOL (COM3)`, que ya existían antes de conectar placas.
3. Comprueba el VID: doble clic en el puerto → pestaña **Detalles** → propiedad **Id. de hardware**.
   Debe empezar con **`USB\VID_303A&PID_1001`**. `303A` es Espressif, y confirma que es el USB nativo
   (USB Serial/JTAG) del ESP32-C5.
   - Si ves `VID_1A86` (CH340) o `VID_10C4` (CP210x), no es el USB nativo: avísame, porque cambia la
     configuración de consola.
4. Es normal que aparezca además un dispositivo **"USB JTAG/serial debug unit"**, a veces con un signo
   amarillo en "Otros dispositivos". Es la interfaz de depuración JTAG; no se usa para grabar ni capturar.
5. Alternativa por PowerShell (cualquier ventana):

   ```powershell
   Get-CimInstance Win32_PnPEntity | Where-Object { $_.Name -match '\(COM\d+\)' } | Select-Object Name, DeviceID
   ```

   La línea con `VID_303A` es la placa.
6. Confirma qué placa es leyendo su MAC (solo lectura, no graba nada). En la **PowerShell de ESP-IDF**:

   ```powershell
   esptool.py --port COM5 read_mac
   ```

   En la salida busca estas líneas (el texto exacto puede variar con la versión de esptool):
   - `Detecting chip type... ESP32-C5` (o `Chip is ESP32-C5 ...`)
   - `MAC: xx:xx:xx:xx:xx:xx`
7. Compara la MAC con la tabla de arriba. Ejemplo: si sale `MAC: d0:cf:13:e8:ff:88`, es la **placa A**.
   Las mayúsculas y minúsculas no importan.
8. Anota en un papel: `A = COM?`, `B = COM?`, `C = COM?`. **Windows suele recordar el número de COM de
   cada placa**, pero si cambias de puerto USB físico puede asignar otro: repite los pasos 2 a 7 ante la
   duda.
9. Desconecta y repite con la siguiente placa.

## 3. Si la placa no entra en modo de grabación

Con el USB nativo, `idf.py flash` normalmente reinicia la placa en modo de grabación solo. Si falla
(ver errores en la sección 5), hazlo a mano:

1. Mantén presionado **BOOT**.
2. Presiona y suelta **RST** sin soltar BOOT.
3. Suelta **BOOT**.
4. La placa queda en modo de descarga. Windows puede desconectar y reconectar el puerto (suena otra vez);
   comprueba en el Administrador de dispositivos que el número de COM siga igual.
5. Vuelve a ejecutar el comando de grabación.
6. Al terminar, si el programa no arranca solo, presiona **RST** una vez.

Esto es necesario sobre todo cuando el programa grabado antes se cuelga, se reinicia en bucle o deja de
atender el USB (por ejemplo, uno de Arduino que usaba los pines del USB).

## 4. Grabar el firmware

Siempre en la **PowerShell de ESP-IDF**. Reemplaza `COMx` por el puerto de la **placa A** y `COMy` por el
de la **placa B**. `-C` le indica a `idf.py` la carpeta del proyecto, así no hace falta `cd`. La primera
compilación de cada proyecto tarda varios minutos.

```powershell
# Placa A -> transmisor
idf.py -C C:\aura\firmware\csi_send set-target esp32c5
idf.py -C C:\aura\firmware\csi_send -p COMx flash monitor
```

```powershell
# Placa B -> receptor (necesita internet la primera vez: descarga esp_csi_gain_ctrl)
idf.py -C C:\aura\firmware\csi_recv set-target esp32c5
idf.py -C C:\aura\firmware\csi_recv -p COMy flash monitor
```

- `set-target` solo se ejecuta **la primera vez** (o si borras `build\`). Crea `sdkconfig` a partir de
  `sdkconfig.defaults`, que ya trae la consola por USB Serial/JTAG.
- Para salir del monitor: **Ctrl+]**.
- **Cierra el monitor antes de usar `capturar.py`**: un puerto COM solo lo puede abrir un programa.

### 4b. `wifi_sensing` (placa B, demo): el WiFi solo se configura por `menuconfig`

**Regla de secretos:** el SSID y la contraseña **NUNCA** se escriben en `sdkconfig.defaults`, porque ese
archivo se sube a git. Solo se cargan con `menuconfig` y quedan en `sdkconfig`, que está excluido de git.

1. En la PowerShell de ESP-IDF (solo la primera vez):

   ```powershell
   idf.py -C C:\aura\firmware\wifi_sensing set-target esp32c5
   ```

2. Abre la configuración:

   ```powershell
   idf.py -C C:\aura\firmware\wifi_sensing menuconfig
   ```

3. Con las flechas y Enter, entra a **Example Connection Configuration**. Verifica que
   **connect using WiFi interface** esté marcado, entra a **WiFi SSID** y escribe el nombre del hotspot,
   y luego a **WiFi Password** y escribe la contraseña. Los nombres están verificados en
   `C:\esp\v5.5.6\esp-idf\examples\common_components\protocol_examples_common\Kconfig.projbuild`.
4. Pulsa **S** (guardar) → Enter, y luego **Q** (salir).
5. **No ejecutes `idf.py save-defconfig`**: copiaría el SSID y la contraseña a `sdkconfig.defaults`.
6. Comprueba que no se filtraron (no debe imprimir nada):

   ```powershell
   Select-String -Path C:\aura\firmware\*\sdkconfig.defaults -Pattern "EXAMPLE_WIFI_SSID|EXAMPLE_WIFI_PASSWORD"
   ```

7. Compila y graba **solo la placa B** (con autorización):

   ```powershell
   idf.py -C C:\aura\firmware\wifi_sensing -p COMy flash monitor
   ```

   Si cambias de hotspot, repite los pasos 2 a 4 y vuelve a grabar.

## 5. Qué debes ver y errores típicos

**Grabación correcta.** Al final de `flash` aparecen, por cada región grabada, líneas como:

```
Wrote 123456 bytes (78901 compressed) at 0x00010000 in 2.3 seconds (...)...
Hash of data verified.
```

y luego:

```
Leaving...
Hard resetting via RTS pin...
Done
```

La palabra clave es **`Hash of data verified.`**: confirma que lo grabado coincide con lo compilado.

**Monitor de la placa A (`csi_send`).** Entre los mensajes de arranque deben aparecer (están en el
código, `csi_send/main/app_main.c`, líneas 158-160):

```
I (...) csi_send: ================ CSI SEND ================
I (...) csi_send: wifi_channel: 11, send_frequency: 100, mac: 1a:00:00:00:00:00
```

**Monitor de la placa B (`csi_recv`)**, con la placa A encendida (líneas 173-208 de
`csi_recv/main/app_main.c`):

```
I (...) csi_recv: ================ CSI RECV ================
type,seq,mac,rssi,rate,noise_floor,fft_gain,agc_gain,channel,local_timestamp,sig_len,rx_format,len,first_word,data
CSI_DATA,0,1a:00:00:00:00:00,-45,...,"[0,0,...]"
I (...) csi_recv: compensate_gain 1.000000, agc_gain ..., fft_gain ...
```

Las líneas `CSI_DATA` deben pasar muy rápido (hasta ~100 por segundo). Si B no muestra ninguna, revisa
que A esté encendida y a más de 1 m.

**Errores típicos:**

| Mensaje | Causa probable | Qué hacer |
|---|---|---|
| `could not open port 'COM5': PermissionError(13, 'Acceso denegado.'...)` | El puerto está abierto en otro programa (monitor, Arduino IDE, `capturar.py`, Chrome con Web Serial) | Cierra el otro programa y reintenta |
| `could not open port 'COM5': FileNotFoundError` | COM equivocado o placa desconectada | Repite la sección 2 |
| `Failed to connect to ESP32-C5: No serial data received.` | La placa no entró en modo de descarga | Sección 3 (BOOT + RST) |
| `This chip is ESP32-C6, not ESP32-C5` (o similar) | Falta `set-target esp32c5`, o se compiló para otro chip | `idf.py -C <proyecto> set-target esp32c5` |
| `idf.py : El término 'idf.py' no se reconoce...` | Estás en una PowerShell normal | Abre la PowerShell de ESP-IDF (sección 0, paso 11) |
| `... contains spaces ...` / errores de CMake con rutas | Proyecto o IDF en una ruta con espacios | Usa solo `C:\aura\...` y `C:\esp` |
| Fallo al descargar `esp_csi_gain_ctrl` / `esp_wifi_sensing` | Sin internet o proxy | Conéctate a internet y repite |
| Monitor con caracteres raros o en blanco | Consola mal configurada | Avísame: no debería pasar con los `sdkconfig.defaults` de `C:\aura\firmware` |
| La placa se reinicia en bucle (`rst:0x...`, `Guru Meditation Error`) | Error del programa | Copia las 30 líneas anteriores al reinicio y envíamelas |

Ante cualquier error, **copia el texto completo** (desde el comando hasta el final) en lugar de
reintentar varias veces.

## 6. Alimentar una placa sin PC

El transmisor (A) no necesita PC, solo energía:

1. **Cargador de celular USB-C de 5 V** (1 A o más) con un cable USB-C. Es la opción más estable.
2. **Power bank:** funciona, pero muchos se **apagan solos** cuando el consumo es bajo. Si la placa se
   apaga a los pocos segundos o minutos, usa otro power bank o el cargador de pared.
3. **Batería de litio de 3,7 V** en el conector **BAT** (3,7–4,2 V según la wiki). **Revisa la polaridad
   antes de conectar.** La placa la carga cuando está conectada por USB (LED de carga encendido).
4. No alimentes a la vez por VIN y por USB.

El receptor (B) va **conectado por USB a la PC**, porque la PC lee sus datos.

## 7. Dónde poner las placas en la primera prueba

**Prueba con `csi_send` (A) y `csi_recv` (B):**

1. **Distancia A–B: entre 2 y 3 m** (esp-csi recomienda más de 1 m).
2. **Misma altura, entre 0,8 y 1,2 m** (mesa, caja o trípode), no en el suelo.
3. **Línea de vista directa** entre ambas: nada en medio cuando la habitación está vacía.
4. Antena libre: el extremo del módulo con la antena no debe quedar tapado por la mano, cables o metal.
   Sepáralas al menos 30 cm de paredes metálicas, del monitor y del router.
5. **No las muevas** durante la sesión. Pégalas con cinta y anota posiciones y distancias en
   `C:\aura\registro_sesiones.csv`.
6. La zona más sensible es la franja entre A y B. Para la prueba de actividad, la persona camina
   **cruzando** esa línea.

**Prueba con `wifi_sensing` (solo B + router o hotspot).** Las placas A y C **no** participan: `csi_send`
transmite fijo en el canal 11 y queda para la investigación con `csi_send`/`csi_recv`.

1. El "transmisor" es el **router o el celular con hotspot**: déjalo **fijo y enchufado**, a 2–4 m de B y a
   la misma altura.
2. Desactiva el apagado automático del hotspot y el ahorro de batería del celular.
3. Al arrancar B, deja la habitación **vacía y quieta 1–2 minutos** para que calcule la línea base (pasa
   de `START` a `STABLE`).

**Protocolo sugerido para la primera sesión de evaluación (unos 6 minutos):** 2 min vacía → 1 min
caminando → 1 min sentada y quieta → 2 min vacía. Anota con cronómetro el segundo exacto de cada cambio
desde que lanzas `capturar.py` (archivo de etiquetas: ver `C:\aura\analisis\evaluar_deteccion.py`).

---

## 8. Demo en el local

> **23/10/2026: para el video se sigue `guion_grabacion.md`** (aura_nodo 0.1.3, modo solo local, captura por
> USB con el kit portátil `C:\aura\kit_captura`). Esta sección describe la demo anterior con `puente.py`.

Para la demo solo se necesitan la **placa B con `wifi_sensing`**, la PC con `puente.py` y un **celular con
hotspot**. Las placas A y C no se llevan a la demo, o se llevan apagadas.

### Antes de ir (en el laboratorio)

1. **Graba un video de respaldo** de la demo completa funcionando: la habitación vacía, alguien que
   entra y camina, se sienta y se queda quieto hasta que llega la alerta al celular, y la desconexión del
   cable USB (alerta "sensor sin datos"). Que se vean en el mismo plano el LED de la placa, la pantalla de
   la app y la persona. Si en el local falla el WiFi o el detector, se presenta el video.
2. Prueba el hotspot que usarás en el local con la misma placa, la misma PC y el mismo celular.
3. Lleva un cable USB-C de datos de repuesto (sección 1) y un cargador para el celular del hotspot.

### Hotspot

4. Configura el hotspot en **WPA2-Personal** (o "WPA2/WPA3 de transición"), no solo WPA3, y en la banda de
   **2,4 GHz** si el celular lo permite. Algunos celulares no dejan elegir banda; en ese caso, usa la
   que haya y pruébala antes.
5. **Desactiva el apagado automático del hotspot** y el ahorro de batería. Deja el celular **fijo y
   enchufado**, porque si se mueve el detector lo interpreta como actividad.
6. El SSID y la contraseña del hotspot deben ser los que grabaste con `menuconfig`. Si cambian, hay que
   volver a compilar y grabar B (con autorización).
7. Conecta también la PC a ese hotspot, para que `puente.py` tenga internet hacia Firebase.

### Ubicación en el local

8. **Distancia corta entre la placa y la persona:** pon la placa B a **1–2 m de donde estará la
   persona**, y el celular del hotspot del otro lado, de modo que la persona quede **entre la placa y el
   celular**, a unos 2–3 m entre sí.
9. **Lejos del pasillo y de la puerta:** la gente que pasa cerca también cambia el canal. Busca un
   rincón donde nadie más circule a menos de 2–3 m del enlace placa–celular.
10. Placa y celular a la misma altura (0,8–1,2 m), con línea de vista, lejos de metal y del monitor
    (sección 7).

### Recalibrar en el sitio (RESET_BASELINE)

La línea base que el detector calculó en el laboratorio no sirve en otro ambiente. **Recalibra siempre en
el local, con la zona vacía y quieta**:

11. Coloca todo en su posición final, sal de la zona y espera unos 30 s sin que nadie se mueva cerca.
12. Envía `RESET_BASELINE`. **Solo un programa puede tener abierto el COM**: mientras `puente.py` corre,
    el monitor web no puede conectarse, así que en la demo se recalibra **desde el puente**:
    - **Con `puente.py` ya en marcha (forma normal en la demo):** haz clic en su ventana y pulsa la tecla
      **R**. El puente envía `HMSCMD RESET_BASELINE`, muestra la confirmación de la placa (o el aviso
      "La placa no confirmó RESET_BASELINE" si no llega en 3 s) y publica CALIBRANDO en la app.
    - **Al arrancar `puente.py`:** opción `--recalibrar`, que hace lo mismo una vez.
    - **Sin el puente (solo en el laboratorio, para diagnosticar):** la página oficial del ejemplo. Cierra
      antes `puente.py`, `capturar.py` y el monitor. Luego, en una PowerShell:

      ```powershell
      C:\aura\analisis\.venv\Scripts\python.exe -m http.server 8000 --bind 127.0.0.1 --directory C:\aura\firmware\wifi_sensing\tools
      ```

      Abre `http://127.0.0.1:8000/web_serial_monitor.html` en **Chrome o Edge** → **Connect Serial** →
      elige el COM de B → botón **Reset Baseline**. Cierra con **Disconnect** y detén el servidor con
      Ctrl+C antes de arrancar `puente.py`.
    - Para salir del puente sin cortar el cable: tecla **Q**.
13. Espera a que el estado vuelva a **STABLE** (en la página, `init_stage`; en la app, deja de decir
    CALIBRANDO) antes de que entre la persona.
14. Prueba rápida antes de presentar: entra y camina, y debe pasar a MOVIMIENTO. Siéntate quieto, y debe
    pasar a PRESENCIA_QUIETA. Sal, y debe pasar a VACÍA. Si no responde bien, recalibra o acerca la
    placa a la persona.

Nota: la recepción de comandos `HMSCMD` por el USB nativo todavía no está verificada (ver
`evaluacion_wifi_sensing.md`). Compruébala en el laboratorio antes del día de la demo.
