# Evaluación de `wifi_sensing_demo` (componente `esp_wifi_sensing`)

Fuente revisada: `C:\aura\esp-csi\examples\esp-radar\wifi_sensing_demo\` (commit `8633d67` de esp-csi,
22/04/2026), `.gitlab-ci.yml` de esp-csi, la ficha del componente en el registro de Espressif
(`components.espressif.com`, consultada el 22/10/2026), el Kconfig de ESP-IDF `release/v5.5` y la wiki
de DFRobot DFR1222.

**Veredicto: compatible.** Propongo copiarlo a `C:\aura\firmware\wifi_sensing\` con dos cambios de
configuración (sección "Propuesta"). Es el camino más corto hacia la prioridad 1 (detectar actividad).

---

## a) ¿Soporta ESP32-C5 con IDF v5.5?

**Sí.** Hay tres evidencias independientes:

| Fuente | Qué dice |
|---|---|
| `main\idf_component.yml` | `idf: '>=5.4'`, `esp_wifi_sensing: '>=0.1.1'`, `espressif/led_strip: "^3.0.0"` |
| `.gitlab-ci.yml` de esp-csi | `esp-radar/wifi_sensing_demo: esp32 esp32s3 esp32s2 esp32c3 esp32c6 esp32c5 esp32c61`. El trabajo `build_idf_v5.5` incluye `esp32c5`; el de v5.4 no. **Para el C5 solo se compila con v5.5.** |
| Registro de componentes (`espressif/esp_wifi_sensing`, versión 0.1.1~3 del 07/09/2026) | `targets`: esp32, esp32s3, esp32s2, esp32c3, **esp32c5**, esp32c6, esp32c61. Depende de `idf >=5.4`, `espressif/esp-radar >=0.3.3` y `cmake_utilities 0.*` |
| `sdkconfig.defaults` | Generado con ESP-IDF 5.5.0 |

Advertencias:
- El componente no viene en el repo: **se descarga del registro en la primera compilación** (necesita
  internet). Licencia: ver la sección "Licencia" al final.
- El CI solo comprueba que el ejemplo **compila**. No garantiza que la detección funcione bien en una
  FireBeetle, con antena integrada, en tu habitación.

## b) ¿Qué necesita?

1. **Un punto de acceso (router o hotspot) con WPA2/WPA3-Personal (contraseña).** La placa receptora se
   conecta como estación mediante `example_connect()` (de `protocol_examples_common` de IDF). El SSID y la
   contraseña se configuran con `idf.py menuconfig` → *Example Connection Configuration*, y quedan en
   `sdkconfig`, que está fuera de git. La WiFi de la universidad, si es WPA2-Enterprise (usuario y
   contraseña), **no sirve** con ese ejemplo.
2. **Un gateway que responda ping.** `esp_wifi_sensing_fsm_ping_router_start()` hace ping al router para
   que siempre haya tráfico del que extraer CSI. El canal principal es el **BSSID del AP**, y es el que
   controla el LED.
3. **Dos pares opcionales, con MAC fijas en el código** (`app_main.c`, líneas 39-40):
   `MAC_1 = 1a:00:00:00:00:00` y `MAC_2 = 1a:00:00:00:00:01`.

**¿Sirven A y C como pares?** Sí, pero no son obligatorios y no conviene usarlos el primer día:
- `csi_send` ya usa la MAC virtual `1a:00:00:00:00:00`, así que la placa A haría de `MAC_1` sin cambios
  de MAC. Para C habría que copiar `csi_send` y poner `0x01` en el último byte.
- **Problema de canal:** `csi_send` transmite fijo en el **canal 11, HT40, 2,4 GHz**, pero el receptor
  conectado al router está en el canal **del router**. Si no coinciden, el receptor no oye a A ni a C.
  Habría que fijar el canal del router (o del hotspot) en 11, o cambiar
  `CONFIG_LESS_INTERFERENCE_CHANNEL` en la copia de `csi_send`.
- Con solo B y el router se tiene el sistema mínimo funcional. A y C suman robustez (más enlaces que
  cruzan la habitación) y quedan para una segunda iteración.

**¿Funciona con el hotspot de un celular?** En principio sí: el hotspot es un AP WPA2-Personal con
gateway. Condiciones:
- **El celular debe quedar fijo**, conectado al cargador y fuera de la zona de paso. Si se mueve, el
  canal cambia y el detector lo interpreta como actividad.
- Algunos celulares apagan el hotspot sin clientes o al ahorrar batería: hay que desactivar ese
  "apagado automático".
- Conviene forzar el hotspot a **2,4 GHz** si después se usan A y C (ellas transmiten en 2,4 GHz).
- La PC del puente puede conectarse al mismo hotspot para tener internet hacia Firebase.
- Hay que comprobar que el hotspot responde al ping. Si no, el log mostrará
  `router ping start failed: ...` (línea 194 o 196 de `app_main.c`).

## c) ¿Qué detecta y qué se ajusta?

**Detecta movimiento, no presencia estática.** Por cada canal (AP, MAC_1, MAC_2) hay una máquina de
estados con salida binaria **ACTIVE / INACTIVE**, notificada por callback (`on_motion_event`). Además:

- Estados internos (`state_name`): `IDLE`, `DEBOUNCE_ACTIVE`, `ACTIVE`, `DEBOUNCE_INACTIVE`. Hay un
  antirrebote en ambos sentidos.
- Etapa de inicialización (`init_stage_name`): `START` → `GOLD_FOUND` → `STABLE`. El detector calcula
  primero una **línea base**; hay que dejar la habitación quieta al arrancar.
  `HMSCMD RESET_BASELINE` la recalcula.
- **Presencia** (aparte del movimiento): `presence_someone_status`, comparando `presence_wander_average`
  con `presence_someone_threshold`, más `presence_ready`. Es el candidato para detectar a alguien
  **sentado y quieto**, que el detector de movimiento probablemente marcará INACTIVE.
- **Entrenamiento** con la habitación vacía: `TRAIN_START <peer>` / `TRAIN_STOP <peer>` calcula umbrales
  propios (`train_wander_threshold`, `train_jitter_threshold`). **Es obligatorio para la presencia**,
  no opcional. Sin muestras de entrenamiento, `esp-radar` devuelve `waveform_wander = 0`
  (`csi_detection_compute_wander` en `esp_radar.c`), y `presence_someone_status` además exige
  `train_thresholds_valid` (`hms_update_presence_state` en `esp_wifi_sensing.c`). Los umbrales viven en
  RAM, así que hay que entrenar tras cada arranque. Lo confirmó la sesión S001: sin entrenar, las 2.892
  muestras del AP tuvieron `wander_value = 0` y presencia en falso.

El algoritmo interno (cómo se calculan `jitter` y `wander`) está dentro del componente descargado, no en
el ejemplo. Lo revisaré cuando IDF lo descargue en la primera compilación.

**Parámetros ajustables:**

| Parámetro | Dónde | Efecto |
|---|---|---|
| `motion_sensitivity` | `HMSCMD SET_CFG <peer> ...` (en ejecución) | Sensibilidad del detector de movimiento |
| `active_jitter_min` | ídem | Variación mínima para considerar actividad |
| `active_filter_ms` | ídem | Tiempo de retención en ACTIVE (en el log aparece como "hold") |
| `presence_sensitivity` | ídem, y `CONFIG_ESP_WIFI_SENSING_DEFAULT_PRESENCE_SENSITIVITY=250` en `sdkconfig.defaults` | Sensibilidad de presencia |
| `CONFIG_ESP_WIFI_SENSING_CONFIRM_COUNT` | menuconfig | Confirmaciones antes de cambiar de estado |
| `cfg.ping_frequency_hz` | `DEFAULT_ESP_WIFI_SENSING_FSM_CONFIG()` | Ritmo del ping al router (más CSI por segundo) |
| `CONFIG_ESP_WIFI_SENSING_WEB_SERIAL_STREAM_PERIOD_MS` | menuconfig, por defecto 50 ms | Frecuencia de las líneas `HMS:` |

Los valores se pueden cambiar sin recompilar, con `HMSCMD ...` por el puerto serie o con
`tools\web_serial_monitor.html` en Chrome o Edge. `web_serial_monitor.c` no guarda nada en NVS, así que es
probable que **los cambios se pierdan al reiniciar**. Si el componente los guarda por su cuenta, lo
veré cuando se descargue. Los valores definitivos se pueden fijar en el código de la copia.

**Formato de salida verificado en el código** (`web_serial_monitor.c`, `send_channel_sample`), que es
lo que leerá `puente.py`:

```
HMS:{"type":"sample","ts_ms":<ms desde arranque>,"peer":"AP","mac":"xx:xx:..","motion_status":true|false,
     "motion_state":<int>,"jitter_value":..,"wander_value":..,"presence_ready":..,
     "presence_wander_average":..,"presence_someone_threshold":..,"presence_someone_status":true|false,
     ...,"state":<int>,"state_name":"ACTIVE","init_stage":<int>,"init_stage_name":"STABLE"}
```

Una línea por par cada 50 ms (3 pares → unas 60 líneas por segundo). También hay mensajes `hello`,
`config`, `runtime`, `ack` y `error`, y logs normales `I (...) wifi_sensing_demo: [AP] ACTIVE peer=...`.

## d) ¿El LED es compatible?

**Sí, cambiando un valor.** El ejemplo usa por defecto un **LED simple por GPIO**
(`ESP_WIFI_SENSING_DEMO_LED_TYPE_GPIO`) en **GPIO 2** (`Kconfig.projbuild`), controlado por LEDC
(PWM). LEDC puede sacar la señal por cualquier GPIO de salida mediante la matriz de GPIO, así que basta
con poner `CONFIG_ESP_WIFI_SENSING_DEMO_LED_GPIO=15`. La señal no está invertida
(`output_invert = 0`), de modo que el LED debe encenderse con nivel alto. Esto se verifica al grabar.

Notas de la wiki DFR1222: el GPIO 15 también figura como `LCD_BL` (retroiluminación) en la tabla del
conector de pantalla; sin pantalla no hay conflicto. El GPIO 2 por defecto no hace daño, pero no
encendería nada visible.

Comportamiento del LED (canal AP): parpadea si no hay WiFi, se enciende fijo con ACTIVE y se apaga
gradualmente con INACTIVE. Sirve como prueba visual inmediata durante la demo.

---

## Estado (22/10/2026)

1. **Copiado** a `C:\aura\firmware\wifi_sensing\`. Comparado con el original, solo cambia
   `sdkconfig.defaults`:
   - quité `CONFIG_ESP_CONSOLE_UART_CUSTOM=y` y `CONFIG_ESP_CONSOLE_UART_BAUDRATE=921600`;
   - agregué `CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y`, por la misma razón que en `csi_recv`;
   - agregué `CONFIG_ESP_WIFI_SENSING_DEMO_LED_GPIO=15`.
2. El SSID y la contraseña se cargan con `idf.py -C C:\aura\firmware\wifi_sensing menuconfig` y quedan en
   `sdkconfig` (fuera de git), no en `sdkconfig.defaults`.
3. **Demo: solo la placa B y el hotspot.** A y C no se usan en la demo, porque `csi_send` transmite fijo
   en el canal 11. Quedan para la investigación con `csi_send`/`csi_recv`. El código sigue declarando los
   canales `MAC_1` y `MAC_2`; sin transmisores, esos canales quedan sin datos y `puente.py` los ignora
   (solo usa `peer = "AP"`).
4. **Compilado sin grabar** el 22/10/2026 con ESP-IDF v5.5.6, con un token sin privilegios de
   administrador: `idf.py set-target esp32c5` y `idf.py build` terminaron con éxito.
   `wifi_sensing.bin` pesa 1.008.928 bytes y la partición de la aplicación es de 1.048.576 bytes:
   **solo 4 % libre** (aviso del compilador). La compilación usó `CONFIG_ESPTOOLPY_FLASHSIZE_2MB`, aunque
   la wiki indica un módulo de 4 MB.
5. Pendiente: cargar el WiFi con `menuconfig` (ahora tiene `myssid`, el valor por defecto) y grabar B,
   solo con tu autorización.

Riesgo a vigilar: `web_serial_monitor.c` instala el driver de USB Serial/JTAG para leer comandos
(`configure_usb_serial_jtag_input`). Con la consola principal también en USB Serial/JTAG, la escritura
de `HMS:` no debería verse afectada. Lo único que podría fallar es la recepción de comandos `HMSCMD`
desde la PC, y el puente solo lee. Se comprueba en la primera grabación.

**Alternativa mínima, si el componente fallara** (por ejemplo, porque no compila o no detecta): usar
`csi_recv_router` del mismo repo (CSI del router con ping), y en la PC calcular la varianza móvil de la
amplitud de las subportadoras con un umbral calibrado con la habitación vacía. `leer_csi.py` ya entrega
la amplitud. Calculo 1 o 2 días extra de trabajo y calibración.

---

## Licencia de `esp_wifi_sensing`

Revisada el 22/10/2026 en el registro de componentes de Espressif y **verificada con los archivos
descargados** en la primera compilación (subsección final).

| Versión | Licencia declarada en el registro |
|---|---|
| 0.1.0 | Apache-2.0 |
| 0.1.1~2 | Apache-2.0 |
| **0.1.1~3** (07/09/2026; la que elegirá `>=0.1.1`) | **"Custom"** |
| `espressif/esp-radar` 0.3.4 (dependencia) | Apache-2.0 |

**Hallazgo:** el `license.txt` que el registro publica para la 0.1.1~3 es el **texto estándar de la
Apache License 2.0** (11.358 bytes, secciones 1 a 9 y apéndice), sin cláusulas añadidas. Busqué términos
como "Espressif", "chip", "non-commercial", "academic", "confidential" y "reverse" y no aparecen. La
etiqueta "Custom" no coincide con el texto, y no sé por qué. Posibles motivos: un error de metadatos, o
archivos con otros términos dentro del paquete (por ejemplo, bibliotecas precompiladas `.a`).

**Si se confirma Apache 2.0:**
- **Uso en una competencia o proyecto universitario:** permitido. La licencia no restringe el campo de
  uso: concede una licencia "perpetual, worldwide, non-exclusive, no-charge, royalty-free".
- **Publicar nuestro código:** permitido, incluso modificado. Hay que incluir una copia de la licencia,
  conservar los avisos de copyright y atribución, y marcar los archivos modificados (ya lo hacemos con los
  comentarios `# AURA:`).
- **Restricción a chips Espressif:** el texto de la licencia no tiene ninguna. En la práctica el código
  solo funciona en chips Espressif, porque usa su API de WiFi y CSI.
- **Marcas:** no autoriza a usar el nombre o el logo de Espressif para sugerir respaldo (sección 6).
- **Sin garantía:** se entrega "AS IS" (secciones 7 y 8).

### Verificación con los archivos descargados (22/10/2026, primera compilación)

Archivos en `C:\aura\firmware\wifi_sensing\managed_components\` (versiones fijadas en
`C:\aura\firmware\wifi_sensing\dependencies.lock`):

| Componente | Versión | `LICENSE` | SPDX en los fuentes | Bibliotecas precompiladas |
|---|---|---|---|---|
| `esp_wifi_sensing` | **0.1.1~3** | Apache 2.0, **idéntico byte a byte** al `license.txt` del registro (SHA-256 `cfc7749b…3d30`) | 7× Apache-2.0 | Ninguna: es código fuente (`src/esp_wifi_sensing.c`) |
| `esp-radar` | 0.3.4 | Apache 2.0 | 6× Apache-2.0 | Ninguna |
| `esp_radar_motion_dec` | 0.1.1 | Apache 2.0 | 2× Apache-2.0 | **Sí**: `5.5/esp32c5/libesp_radar_motion_dec.a` (enlazada) |
| `esp_csi_gain_ctrl` | 0.1.5 | Apache 2.0 | 2× Apache-2.0 | **Sí**: `5.5/esp32c5/libesp_csi_gain_ctrl.a` (enlazada) |
| `led_strip` | 3.1.1 | Apache 2.0 | 11× Apache-2.0, 2× Unlicense | Ninguna |
| `cmake_utilities` | 0.5.3 | Apache 2.0 | 1× Apache-2.0 | Ninguna |

**Conclusiones:**
- La licencia descargada de `esp_wifi_sensing` es **Apache 2.0**. **No hace falta fijar la 0.1.1~2.**
  La etiqueta "Custom" del registro sigue sin explicación: el paquete no contiene nada que no sea Apache.
- **Para el informe:** el núcleo de la detección de movimiento (`esp_radar_motion_dec`) y el control de
  ganancia (`esp_csi_gain_ctrl`) se enlazan como **bibliotecas precompiladas `.a`**. Su licencia es Apache
  2.0, pero **su código fuente no se distribuye**, así que el algoritmo es una caja negra: se puede usar y
  redistribuir, pero no inspeccionar ni describir más allá de su API pública. Hay que declararlo como
  limitación metodológica.
- Para publicar el código de AURA: incluir el `LICENSE` de Apache 2.0, conservar los avisos y marcar los
  cambios (comentarios `# AURA:`).

---

## Limitaciones

1. **Detector de caja negra.** El núcleo de la detección de movimiento (`esp_radar_motion_dec`) y el
   control de ganancia (`esp_csi_gain_ctrl`) se distribuyen como bibliotecas precompiladas (`.a`), sin
   código fuente. Se pueden usar y redistribuir (Apache 2.0), pero **su algoritmo no se puede describir
   metodológicamente**: solo su API y sus salidas (`jitter_value`, `wander_value`, estados).
2. **Consecuencia para la investigación (no para la demo):** en la parte de investigación, la detección
   deberá hacerse con **procesamiento propio sobre CSI crudo** (`csi_send`/`csi_recv` con las placas A, B
   y C, y `C:\aura\analisis\leer_csi.py`), con un método documentado y reproducible (por ejemplo,
   varianza móvil de la amplitud por subportadora con un umbral calibrado con la habitación vacía).
   `wifi_sensing` queda como **sistema de demostración** y como referencia de comparación, no como método
   del estudio.
3. **La alerta de quietud no distingue entre reposo y caída** (ver `arquitectura_alertas.md`).
4. **La calidad de la detección con la antena integrada de la FireBeetle** está por medir con
   `evaluar_deteccion.py`. El CI de Espressif solo garantiza que el ejemplo compila.
5. **El entrenamiento de presencia no se puede guardar en NVS con la API pública** (evidencia abajo):
   hay que volver a entrenar en cada arranque y tras cada cambio de red. Mientras tanto, `presencia` se
   publica como `no_disponible`.
6. **Sin notificaciones push sin una PC o un servidor** (opciones abajo).

---

## ¿Se pueden guardar y recargar los umbrales de presencia? (23/10/2026)

**Respuesta: se pueden LEER, pero no CARGAR, y aunque se pudieran cargar no bastarían.** No quedó
implementado.

Evidencia, en las versiones fijadas (`esp_wifi_sensing` 0.1.1~3, `esp-radar` 0.3.4):

1. **API pública de esp-radar** (`managed_components/espressif__esp-radar/include/esp_radar.h`): para el
   entrenamiento solo existen `esp_radar_train_start(_ex)` (línea 526/740), `esp_radar_train_stop(_ex)`
   (555/769, que **devuelve** los umbrales), `esp_radar_train_remove(_ex)` (536/752) y
   `esp_radar_train_get_diag(_ex)` (569/781, solo lectura). **No hay función para cargar umbrales ni datos
   de entrenamiento.**
2. **API pública de esp_wifi_sensing** (`include/esp_wifi_sensing.h`): `esp_wifi_sensing_fsm_train_start`
   (321), `..._train_stop` (339) y `..._train_remove` (352). Los umbrales solo se pueden **leer** en el
   diagnóstico del canal (`train_wander_threshold`, `train_jitter_threshold`, `train_thresholds_valid`,
   líneas 108–110). **No hay setter.** Internamente, `ch->train_wander_thr` y `ch->train_thresholds_valid`
   solo se asignan en `esp_wifi_sensing_fsm_train_stop` (`src/esp_wifi_sensing.c`, ~1700–1708).
3. **Además, la presencia necesita las muestras plantilla, no solo los umbrales:**
   `csi_detection_compute_wander` (`src/esp_radar.c`, 1271–1289) calcula `waveform_wander` comparando el
   CSI actual con `peer->cal->data[i]`, hasta `CSI_WANDER_NUM` = 10 vectores (línea 140) guardados durante
   el entrenamiento. Si `data_num == 0`, devuelve 0. Esas plantillas están en la estructura **privada**
   `radar_calibrate_t` (líneas 159–171, `float *data[CSI_WANDER_NUM]`) dentro de `s_ctx`, que es `static`
   (línea 173).
4. **Conclusión:** guardar en NVS los dos umbrales no restauraría la presencia, porque `wander` seguiría en
   0 sin las plantillas.
   - **Posible a futuro:** copiar `esp-radar` y `esp_wifi_sensing` a `firmware\aura_nodo\components\` (es
     código fuente Apache-2.0; solo `esp_radar_motion_dec` es precompilado) y agregar funciones de
     exportar e importar para `cal->data[0..data_num)`, `static_wander` y los umbrales del canal.
   - Ocuparía ≤ 10 × columnas × 4 B (≤ 2,5 KB) en NVS.
   - Esfuerzo: 0,5–1 día. Riesgo medio: las plantillas dependen del AP, del ambiente y de la posición, así
     que hay que invalidarlas si cambia el BSSID.

---

## Notificaciones push sin PC (hoja de ruta)

**Limitación actual:** la placa escribe la alerta en `/sensores/hab1/estado.alerta`, pero **no puede enviar
un push (FCM)**. La API FCM HTTP v1 exige un token OAuth de una **cuenta de servicio**, y su clave privada
no debe estar en un dispositivo físico, que no tiene ni secure boot ni cifrado de flash. Hoy la app solo ve
la alerta si está abierta.

| Opción | Cómo funciona | A favor | En contra |
|---|---|---|---|
| **1. Relé en una PC** | Un script en la PC (como el antiguo `puente.py`) escucha `/sensores/hab1/estado` con tu cuenta o con el SDK de administrador y envía el push con la clave de servicio guardada en la PC | Sin costo; el código es casi el del diseño anterior; la clave queda fuera de la placa | Exige una PC **encendida y conectada siempre**: es justo lo que no tenemos (PC de escritorio, la demo es sin PC). Si se apaga o pierde internet, no hay push y nadie se entera |
| **2. Raspberry Pi** (u otro mini-PC siempre encendido) | El mismo relé, en un equipo pequeño junto al router | Bajo consumo y siempre encendido; la clave queda en un equipo que controlas; sin costo recurrente; también podría ser receptor local y vigilante del latido de la placa | Hardware extra (~USD 50–80); otro equipo que mantener (energía, actualizaciones, tarjeta SD); sigue siendo un punto único de falla en el mismo lugar que la placa (si se corta la luz o internet, cae junto con ella) |
| **3. Cloud Functions (plan Blaze) con alerta de presupuesto** | Una función con disparador de RTDB (`onValueWritten` en `/sensores/{id}/estado`) envía el push con su cuenta de servicio administrada por Google; una función programada vigila el latido y avisa si la placa deja de reportar | No hay equipo extra ni clave en tu poder; la función corre en Google aunque se caiga tu red, así que **detecta la desconexión de la placa**; escala a varios sensores | Exige tarjeta de crédito (Blaze). El uso de este proyecto cabría en el nivel gratuito de Functions, pero un error (por ejemplo, un bucle de escrituras) puede generar costos. **Mitigación:** alerta de presupuesto en Google Cloud Billing (p. ej., USD 1 y USD 5), límite de instancias en la función, reglas que acoten las escrituras. Además: despliegue con `firebase-tools` y Node, y depende de un servicio de terceros |

**Aclaraciones sobre la opción 3 (23/10/2026):**
- **Blaze exige una tarjeta de crédito o débito** asociada a una cuenta de facturación de Google Cloud.
  Sin ella no se pueden desplegar Cloud Functions.
- **Una alerta de presupuesto de Google Cloud solo AVISA** (correo al llegar al 50 %, 90 % o 100 % del
  monto, por ejemplo): **no detiene el gasto ni apaga nada**. Además, los datos de facturación llegan con
  retraso, así que el aviso puede llegar después del gasto.
- Para **cortar** el gasto haría falta, por ejemplo, una función que reciba la notificación de presupuesto
  (Pub/Sub) y deshabilite la facturación del proyecto, lo que **apaga todo el proyecto**. También ayudan
  límites preventivos: máximo de instancias en la función, reglas que acoten las escrituras, cuotas.
- **La decisión queda pendiente** del responsable del proyecto.

**Recomendación para la hoja de ruta:** la opción 3, con alerta de presupuesto y límites de instancias, si
se acepta poner una tarjeta. Es la única que también detecta la caída de la placa y de la red sin depender
de un equipo en el mismo lugar. Si no se acepta la tarjeta, la opción 2. La opción 1 no sirve para el caso
de uso sin PC.
