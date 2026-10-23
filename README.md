# AURA — Detección de actividad humana con WiFi CSI (ESP32-C5)

Proyecto de investigación universitaria (Lima, Perú). Se usa la **información de estado del canal
(CSI)** de placas ESP32-C5 para detectar actividad humana en una habitación sin cámaras, y enviar el
estado y las alertas a una app Android por internet (Firebase, plan Spark).

**Prioridades (entrega 30/10/2026):**
1. Detectar actividad humana en una habitación.
2. App Android que reciba el estado y las alertas por internet.
3. (Secundario) estimar la frecuencia respiratoria.

Después: sensores IoT (BME280, PIR HC-SR501, micrófono INMP441).

**Arquitectura vigente (desde el 22/10/2026): dos vías sin PC.** La placa B corre
`C:\aura\firmware\aura_nodo`:
- detecta siempre en la placa;
- entrega **todos** los datos por la red local (UDP);
- envía resúmenes y recibe comandos por **Firebase** con su propia cuenta;
- se actualiza por **OTA local** autenticada.

Ver `docs\arquitectura_dos_vias.md`. El diseño anterior con `puente.py` en la PC
(`docs\arquitectura_alertas.md`) queda como histórico.

Documentos:
- `C:\aura\docs\arquitectura_dos_vias.md`: diseño e implementación de las dos vías, la amplitud y el CSI
  crudo, el volumen en Firebase y las limitaciones.
- `C:\aura\docs\grabacion_aura_nodo.md`: pasos para grabar `aura_nodo` y cargar las credenciales.
- `C:\aura\docs\plan_pruebas.md` y `C:\aura\docs\resultados_pruebas.md`: pruebas T1–T5 y D1–D10.
- `C:\aura\docs\guia_firebase.md`: proyecto de Firebase, usuarios (tú y la placa), UID y reglas.
- `C:\aura\docs\guia_placas.md`: cómo conectar, identificar y grabar las placas, paso a paso.
- `C:\aura\docs\evaluacion_wifi_sensing.md`: evaluación del detector oficial, su licencia y sus
  limitaciones.
- `C:\aura\docs\arquitectura_alertas.md`: diseño anterior (placa → PC → Firebase), histórico.

Herramientas nuevas (`C:\aura\analisis\`):

| Herramienta | Para qué |
|---|---|
| `cargar_credenciales.py` | Carga las credenciales en la NVS por USB, sin eco |
| `receptor_local.py` | Recibe y graba la vía local, y mide pérdidas |
| `visor.py` | Panel en vivo y reproducción para el video |
| `comando_local.py` | Comandos locales autenticados con HMAC |
| `ota_local.py` | OTA local autenticada |
| `descargar_crudo.py` | Baja `/crudo` de Firebase y lo borra de la nube |
| `fb_rest.py` | Cliente REST de Firebase con tu cuenta |
| `pruebas\` | Scripts T1–T5 y D1–D10 |

La configuración de Firebase está en `C:\aura\firebase\` (reglas, plantilla y prueba del emulador).

## Hardware

3 × DFRobot FireBeetle 2 ESP32-C5 (módulo ESP32-C5-WROOM-1, antena integrada, 2,4/5 GHz).
El USB-C es el **USB nativo del chip (USB Serial/JTAG)**: no hay puente USB-UART, así que en
Windows aparece con **VID 303A** (Espressif) y **los baudios no limitan la velocidad** del puerto.
LED de usuario en **GPIO 15**.

| Rótulo | MAC                 | Demo del 30/10 | Investigación |
|--------|---------------------|----------------|---------------|
| A      | `D0:CF:13:E8:FF:88` | No se usa      | Transmisor (`csi_send`) |
| B      | `3C:DC:75:8A:6F:CC` | **Nodo `aura_nodo` (detector + vía local + nube); red principal y hotspot de respaldo** | Receptor (`csi_recv`) |
| C      | `3C:DC:75:8A:6D:24` | No se usa      | Reserva / segundo transmisor |

A y C quedan fuera de la demo porque `csi_send` transmite fijo en el canal 11, que no tiene por qué
coincidir con el canal del hotspot.

> El firmware de esp-csi le asigna al transmisor una **MAC virtual fija `1a:00:00:00:00:00`**, y el
> receptor solo acepta paquetes de esa MAC. Por eso en los datos aparece esa MAC y no la de la placa A.

## Estructura

```
C:\aura
├── esp-csi\             clon oficial de espressif/esp-csi (NO se modifica)
├── firmware\            copias de los ejemplos; aquí se configura y se compila
├── datos\crudos\        capturas tal cual salen del puerto   (SENSIBLE, fuera de git)
├── datos\procesados\    tablas leídas y figuras              (SENSIBLE, fuera de git)
├── analisis\            scripts de Python y entorno virtual C:\aura\analisis\.venv
├── secretos\            clave de la cuenta de servicio de Firebase (fuera de git)
├── docs\
├── registro_sesiones.csv
└── README.md
```

ESP-IDF **no admite espacios** en la ruta del proyecto: no muevas `C:\aura`.

## Instalación

Ya instalado en esta PC: Git 2.55, Python 3.12.10, EIM 0.20.1 (instalador gráfico de ESP-IDF),
Android Studio 2025.3 y JDK 17/21. El entorno `C:\aura\analisis\.venv` ya está creado con
`C:\aura\analisis\requirements.txt`; las versiones exactas están en
`C:\aura\analisis\requirements-lock.txt`.

### ESP-IDF v5.5 con EIM

esp-csi se compila en su CI con IDF **v5.4 y v5.5**, y para el **ESP32-C5 solo con v5.5**. Sus
`sdkconfig.defaults` se generaron con 5.5.0. Usa **v5.5.x**, no la más reciente. Los pasos del
instalador gráfico están en `C:\aura\docs\guia_placas.md`, sección 0. Ruta de instalación: `C:\esp`.

Comprobación, en la PowerShell de ESP-IDF que crea EIM:

```powershell
idf.py --version
```

### Entorno de Python (si hubiera que recrearlo)

```powershell
python -m venv C:\aura\analisis\.venv
C:\aura\analisis\.venv\Scripts\python.exe -m pip install -r C:\aura\analisis\requirements.txt
```

Para activarlo: `C:\aura\analisis\.venv\Scripts\Activate.ps1`. Si PowerShell lo bloquea, ejecuta una
vez `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## Firmware

Copias en `C:\aura\firmware\`:

| Carpeta | Origen en esp-csi | Cambios (solo en `sdkconfig.defaults`) |
|---|---|---|
| `csi_send` | `examples\get-started\csi_send` | Consola por USB Serial/JTAG |
| `csi_recv` | `examples\get-started\csi_recv` | Consola por USB Serial/JTAG (antes: UART0 a 921600) |
| `wifi_sensing` | `examples\esp-radar\wifi_sensing_demo` | Consola por USB Serial/JTAG; LED en GPIO 15 |

Sin el cambio de consola, el firmware imprimiría por los pines UART0, que en la FireBeetle no llegan al
USB-C. El detalle está en los comentarios `# AURA:` de cada `sdkconfig.defaults`.

### Regla de secretos del WiFi (obligatoria)

- El SSID y la contraseña del WiFi **NUNCA van en `sdkconfig.defaults`**, porque ese archivo se sube a
  git.
- **Solo se cargan con `menuconfig`**:
  `idf.py -C C:\aura\firmware\wifi_sensing menuconfig` → *Example Connection Configuration* →
  *WiFi SSID* / *WiFi Password*. Así quedan en `sdkconfig`, que está excluido de git en todas las
  carpetas de firmware, igual que `build\` (que guarda copias en `build\config\sdkconfig.h` y
  `sdkconfig.json`).
- **No ejecutes `idf.py save-defconfig`** en `wifi_sensing`: regenera `sdkconfig.defaults` a partir de
  `sdkconfig`, con el SSID y la contraseña incluidos. Si alguna vez hace falta, revisa el resultado antes
  de guardarlo.
- Comprobación antes de cualquier `git add` (no debe imprimir nada):

  ```powershell
  Select-String -Path C:\aura\firmware\*\sdkconfig.defaults -Pattern "EXAMPLE_WIFI_SSID|EXAMPLE_WIFI_PASSWORD"
  ```

Configuración de radio de `csi_send`/`csi_recv` (`main\app_main.c`): **2,4 GHz, canal 11, HT40**,
802.11n, ESP-NOW a **100 paquetes/s**. Para cambiar la banda o el canal hay que editar los dos
`app_main.c` dentro de `C:\aura\firmware\`, nunca en `esp-csi\`.

### Grabar (resumen; el detalle y los errores típicos están en `docs\guia_placas.md`)

En la PowerShell de ESP-IDF. Usa `COMx` = placa A y `COMy` = placa B, identificadas por su MAC.

```powershell
idf.py -C C:\aura\firmware\csi_send set-target esp32c5
idf.py -C C:\aura\firmware\csi_send -p COMx flash monitor      # salir: Ctrl+]

idf.py -C C:\aura\firmware\csi_recv set-target esp32c5
idf.py -C C:\aura\firmware\csi_recv -p COMy flash monitor      # deben verse líneas CSI_DATA,...
```

La primera compilación de `csi_recv` descarga el componente `esp_csi_gain_ctrl` del registro de
Espressif, así que necesita internet. **Cierra siempre el monitor antes de capturar**: el puerto solo
puede abrirlo un programa a la vez.

## Capturar y analizar una sesión de CSI

1. Anota la sesión en `C:\aura\registro_sesiones.csv`. Usa códigos, nunca nombres de personas.
2. Separa A y B más de 1 m (ver `docs\guia_placas.md`), enciende A y conecta B a la PC.
3. Captura. `--baudios` es opcional y no tiene efecto con el USB nativo.

   ```powershell
   C:\aura\analisis\.venv\Scripts\python.exe C:\aura\analisis\capturar.py --puerto COMy --id-sesion S001 --duracion 120
   ```

   Guarda `C:\aura\datos\crudos\S001.csv` (columnas `t_pc_unix`, `linea`), informa las líneas de datos
   por segundo y no sobrescribe archivos existentes. También sirve para grabar la salida `HMS:` del
   detector `wifi_sensing`.

4. Lee el CSI:

   ```powershell
   C:\aura\analisis\.venv\Scripts\python.exe C:\aura\analisis\leer_csi.py C:\aura\datos\crudos\S001.csv
   ```

   Genera `C:\aura\datos\procesados\S001_leido.csv` con el tiempo (de la PC y del reloj del ESP32),
   RSSI, canal y la amplitud y fase de cada subportadora. Cada subportadora viene como
   **(imaginario, real)**; lo verifiqué en `csi_recv/main/app_main.c` y en el parser oficial
   `tools/csi_data_read_parse.py`.

5. (Secundario) Estima la respiración en sesiones con metrónomo:

   ```powershell
   C:\aura\analisis\.venv\Scripts\python.exe C:\aura\analisis\estimar_respiracion.py C:\aura\datos\procesados\S001_leido.csv --metronomo-rpm 15
   ```

## Evaluar la detección de actividad

1. **Sesión guiada por tramos** (un solo proceso abre el COM, captura, espera STABLE, avisa con
   pitidos cada cambio, escribe `C:\aura\datos\crudos\<id>_etiquetas.csv` y registra la sesión con
   `condicion_real=tramos`):

   ```powershell
   C:\aura\analisis\.venv\Scripts\python.exe C:\aura\analisis\sesion_guiada.py --puerto COMy --id-sesion S002 --recalibrar --entrenar 20 --tramos vacia=60 caminando=60 sentada_quieta=60 --distancia-persona 1.5
   ```

   `--entrenar 20` entrena la presencia durante 20 s con la habitación vacía. **Sin entrenamiento, la
   presencia queda siempre en falso** (ver `docs\evaluacion_wifi_sensing.md`).

   Pitidos: 1 = vacía (sal de la zona), 2 = caminando, 3 = sentada quieta, uno largo = fin.

2. **Evaluación:** `C:\aura\analisis\evaluar_deteccion.py --sesiones S002` cruza el estado detectado
   (líneas `HMS:`) con las etiquetas o con `condicion_real` (`vacia` / `caminando` / `sentada_quieta`).
   Entrega la matriz de confusión, la sensibilidad, la especificidad, la latencia y una figura por sesión.

Otros scripts:
- `C:\aura\analisis\capturar.py --reiniciar`: reinicia la placa por RTS al empezar, para capturar el
  arranque completo. Se reconecta solo si el USB nativo desaparece un instante, y lo marca con una línea
  `#AURA`.
- `C:\aura\analisis\registro.py`: agrega filas a `registro_sesiones.csv` con Python. **Los CSV no se
  editan con PowerShell.**

## Estado de la validación

- `leer_csi.py` y `estimar_respiracion.py` **solo se probaron con datos sintéticos**. Eso demuestra que
  el código corre y que el orden imaginario/real coincide con una línea de ejemplo oficial. **No es una
  validación**: aún no hay capturas reales con las placas.
- `capturar.py` y `evaluar_deteccion.py` aún no se han probado con hardware.

## Privacidad

`C:\aura\datos\crudos\`, `C:\aura\datos\procesados\`, `C:\aura\secretos\` y `google-services.json`
están en `.gitignore`. No subas capturas de personas a ningún repositorio ni nube sin consentimiento
informado. A Firebase solo se envían el estado (activo/inactivo) y su marca de tiempo, nunca CSI.
