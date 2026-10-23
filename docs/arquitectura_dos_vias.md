# Arquitectura de dos vías — AURA nodo (v0.1.0)

Firmware: `C:\aura\firmware\aura_nodo` (derivado de `wifi_sensing_demo`, Apache-2.0).
Estado: **implementado y compilado el 22/10/2026; sin grabar ni probar con la placa.**

```
                    ┌──────────────────────── placa B (ESP32-C5) ────────────────────────┐
  CSI del AP ──►    │ esp_wifi_sensing (detección SIEMPRE en la placa)                     │
                    │   ├─ muestras HMS (~16/s) ─┐                                         │
                    │   └─ CSI crudo (callback) ─┼─► aura_salida ─► USB (solo con host)    │
                    │                            ├─► VÍA LOCAL: UDP unicast a suscriptores │──► receptor_local.py / visor.py
                    │                            └─► VÍA NUBE: Firebase REST (HTTPS)        │──► /sensores, /crudo ◄── app / visor
                    │  comandos: USB · local (HMAC) · nube (/comandos) ─► cola única FIFO  │
                    │  OTA local autenticada (TCP) · SNTP · telemetría cada 10 s           │
                    └──────────────────────────────────────────────────────────────────────┘
```

**Independencia de las vías:** cada vía tiene su propia tarea (prioridad 3), sus propios sockets y su
propia espera creciente.
- Sin internet, la vía local sigue: la nube queda en `espera_reintento`.
- Sin receptores locales, la placa no gasta CPU ni cola en datos locales (solo emite el anuncio) y la
  nube sigue.
- Sin red no hay CSI del AP, pero la placa no se bloquea y reintenta.

---

## 0. Recursos (medidos)

| Recurso | Valor |
|---|---|
| Flash físico | 4 MB (`esptool flash_id`); sin PSRAM (eFuse `PSRAM_CAP=0`); ESP32-C5 v1.0 |
| Imagen `aura_nodo.bin` (`-Os`) | 1.180.416 B en una ranura de 1.572.864 B → **24,95 % libre** (T1) |
| SRAM estática | 144.444 B de 320.928 B; 176.484 B para el heap **antes** de arrancar tareas y WiFi |
| RAM en ejecución | **no medida todavía** (no hay placa con este firmware). Se mide con la telemetría en D3/D9 |

### Desglose de la RAM nueva en ejecución (revisado el 23/10 contra el código)

| Bloque | Detalle (bytes, del código) | Total |
|---|---|---|
| **Pilas de tareas nuevas** | `aura_wifi` 5120 + `aura_local` 5120 + `aura_cmd` 5120 + `aura_ota` 6144 + `aura_nube` 8192 + `aura_tel` 5120; `web_serial_monitor` +1024 (4096 → 5120); TCB ≈ 6 × 350 | **≈ 38 KB** |
| **Cola y buffers de la vía local** | anillo de 16.384 + datagrama 2048 + entrada 512 | **≈ 18,5 KB** |
| **Buffers de la nube** | token 1600 + refresh 600 + URL 2048 + cuerpo 4096 + respuesta 4096 | **≈ 12,2 KB** |
| **Cliente HTTP persistente con la base** | rx 2048 + tx 2304 (URL con token) + estructura ≈ 1000 | **≈ 5,3 KB** |
| **Driver USB** | tx 4096 + rx 1024 (el ejemplo usaba 256 + 512) | **≈ +4,3 KB** |
| **Cola de comandos y telemetría** | 8 × 228 + copia de 800 | **≈ 2,6 KB** |
| **TLS** (`MBEDTLS_DYNAMIC_BUFFER`) | handshake: entrada de hasta 16 KB + salida + cadena de certificados + ECDHE; en reposo libera casi todo (~3–6 KB) | **20–35 KB (pico)** |
| **Total en el pico** | | **≈ 101–116 KB** |
| Transitorios | OTA: 4 KB + SHA mientras dura la actualización; autenticación: ~3 KB. Desde el 23/10 nunca coincide con la sesión de la base | — |

**¿Por qué la cifra de la fase 1 (30–45 KB) era menor?**
- Esa cifra era **solo el handshake TLS con buffers estáticos**. Con buffers dinámicos ese pico baja a
  20–35 KB.
- La cifra nueva suma todo lo que se agregó después:
  1. la cola de 16 KB para enviar el CSI crudo a velocidad completa (requisito posterior a la fase 1);
  2. cuatro tareas que la fase 1 no contemplaba (comandos, OTA, telemetría y el gestor WiFi propio):
     ~21 KB de pilas;
  3. las pilas subidas a 5 KB al ver que cada mensaje se formatea en un buffer de 1,4 KB;
  4. los buffers del driver USB;
  5. URLs de 2 KB, porque el `idToken` va en la consulta.
- La versión anterior de este documento decía 90–105 KB; subestimaba los buffers USB y el buffer de
  transmisión HTTP.
- Corrección aplicada el 23/10: la sesión con la base se cierra antes de autenticar. Sin eso, al renovar
  el token habría **dos** sesiones TLS a la vez (+20–30 KB).

**Comparación con lo disponible (riesgo ALTO, sin medir):**
- El heap al arrancar es de ~176 KB.
- De ahí salen primero el driver WiFi (10 buffers RX estáticos de 1,6 KB más sus tareas), lwIP, esp-radar
  y esp_wifi_sensing. No se midieron, pero estimo 50–80 KB.
- Además, los **128 buffers RX dinámicos** pueden tomar mucha memoria en ráfagas.
- **Puede no alcanzar.** Lo indica D1 desde el primer minuto (`heap_libre` y `heap_minimo` en la
  telemetría).
- Medidas preparadas, que no requieren cambiar la lógica:
  - cola local y buffers de la nube configurables por `menuconfig` (`AURA_LOCAL_COLA_KB`,
    `AURA_NUBE_BUFFER_KB`), con una variante de poca RAM lista para grabarse por OTA;
  - si la vía local o la nube no pueden reservar memoria al arrancar, la placa **sigue funcionando sin esa
    vía**, en vez de reiniciarse en bucle;
  - la decisión sobre los buffers RX se toma en D9.

## 1. Particiones (4 MB, dos ranuras OTA, vuelta atrás)

`C:\aura\firmware\aura_nodo\partitions.csv` (validada en T2 con `gen_esp32part.py`):

| Partición | Tipo | Offset | Tamaño | Uso |
|---|---|---|---|---|
| (cargador) | — | 0x2000 | 0x55A0 (termina en 0x75A0) | bootloader con `CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE=y` |
| (tabla) | — | 0xA000 | 0x1000 | tabla de particiones |
| `nvs` | data/nvs | 0xB000 | 0x10000 (64 KB) | credenciales, último comando de la nube (antes 24 KB) |
| `otadata` | data/ota | 0x1B000 | 0x2000 | qué ranura arranca y su estado |
| `phy_init` | data/phy | 0x1D000 | 0x1000 | calibración de radio |
| `ota_0` | app | 0x20000 | 0x180000 (1,5 MB) | ranura A |
| `ota_1` | app | 0x1A0000 | 0x180000 (1,5 MB) | ranura B |
| `coredump` | data/coredump | 0x320000 | 0x10000 | volcado ELF si hay pánico (diagnóstico de D3) |
| libre | — | 0x330000 | 832 KB | reserva |

**Vuelta atrás:** una imagen nueva (OTA) arranca como `PENDING_VERIFY`. `app_main.c` la marca válida solo
cuando hay IP, el detector corre y pasaron 30 s. Si se reinicia antes (cuelgue, pánico o la variante de
prueba D8d), el cargador vuelve a la ranura anterior.

## 2. Secretos fuera del binario (NVS)

- **Claves en NVS** (namespace `aura_cred`, `aura_config.c`): `wifi1_ssid`, `wifi1_pass` (principal),
  `wifi2_ssid`, `wifi2_pass` (hotspot de respaldo), `fb_api_key`, `fb_db_url`, `fb_email`, `fb_pass`
  (cuenta del **dispositivo**) y `local_key` (clave local compartida). Ninguna se compila: `sdkconfig` y
  `sdkconfig.defaults` no contienen credenciales (T3).
- **Carga** por USB con `C:\aura\analisis\cargar_credenciales.py --puerto COMx`:
  - pide cada valor sin eco (`getpass`) y lo envía como `AURA SET <clave> <hex>`;
  - la placa solo confirma el **nombre** de la clave;
  - `AURA LIST` dice qué claves están definidas, sin valores.
- **La carga solo es posible por USB**, no por la red.
- **Nunca en los registros:**
  - la placa no repite valores;
  - los registros del driver WiFi (que imprimen el SSID) y de HTTP/TLS (cuyas URLs llevan `?auth=<token>`)
    se limitan a advertencias;
  - los buffers con secretos se borran después de usarse.
  - D1 lo verifica buscando cada secreto, en texto, hexadecimal y base64, en las capturas USB y local.

## 3. Vía local

**Transporte: UDP unicast con suscripción**, no WebSocket ni broadcast.
- Un servidor WebSocket en la placa costaría 35–50 KB de flash, 12–16 KB de RAM y conexiones TCP.
- El broadcast WiFi sale a la tasa básica y sin acuse de recibo: más pérdidas y más tiempo de aire.
- Con UDP unicast, el receptor envía `SUB <nombre>` cada 10 s y la placa le da una concesión de 30 s.
  Admite hasta 3 receptores.

**Descubrimiento: anuncio por broadcast cada 2 s** (`AURA-ANUNCIO {id, ip, puerto, ota, ver, mac}`, UDP
45455). No se usa mDNS: el navegador de Android no siempre resuelve `.local`, y mDNS ocupa flash.
`receptor_local.py` escucha el anuncio; también acepta `--ip`.

**Datos completos, sin resúmenes.** Cada datagrama es `A1 <seq> <t_us> <tipo> <cuerpo>`:
- `seq` es un contador global (uint32) para medir pérdidas;
- `t_us` es la hora UNIX por SNTP (0 si todavía no hay hora);
- `tipo hms`: cada mensaje HMS tal cual: muestras (~16/s), telemetría (cada 10 s), acks y eventos;
- `tipo csi`: cada paquete CSI del AP con sus metadatos y, en base64, `raw` y `valid` (ver la sección 4).

| Flujo | Volumen |
|---|---|
| HMS | ~14 KB/s |
| CSI (≈ 50–110 paquetes/s) | ~40–60 KB/s |
| **Total** | **< 0,6 Mbit/s por receptor** |

**Receptor `receptor_local.py`:**
- graba todo en `C:\aura\datos\crudos\<id>_local.csv` (`t_pc_unix, linea`);
- informa cada 5 s la tasa por tipo, la pérdida, el desorden y los duplicados;
- abre una "época" nueva si la placa se reinicia;
- alimenta el panel (`visor.py`) mediante `al_recibir`.

**Comandos locales:** `CMD <ctr> <hmac> <texto>`, con `hmac = HMAC-SHA256(local_key, "<ctr> <texto>")`.
- `ctr` son los milisegundos UNIX del emisor: la placa exige que sea mayor que el último aceptado y que
  esté a menos de 120 s de su hora SNTP (contra repeticiones).
- Lista de permitidos: `RESET_BASELINE`, `TRAIN_START`, `TRAIN_STOP`, `SET_CFG`, `SET_AMPLITUDE_LOG`,
  `GET_CFG`.
- La clave nunca viaja por la red.
- Herramienta: `comando_local.py`.

**Limitación:** los datos locales viajan **sin cifrar**. Cualquiera en la red puede suscribirse y leerlos:
el estado, las muestras y el CSI. No puede enviar comandos ni OTA sin la clave.

## 4. Amplitud y CSI crudo: qué se entrega exactamente

Fuentes revisadas: `esp_radar.c` (`esp_radar_csi_rx_cb`, `esp_radar_rebuild_csi_data`,
`copy_subcarrier_data`) y `esp_csi_gain_ctrl.h`.

- La captura se engancha con la API pública `esp_radar_change_config` (`csi_filtered_cb`). Se ejecuta
  **dentro del callback de CSI del WiFi**, antes de que esp-radar encole el paquete para la detección.
  Solo copia y encola: no modifica los datos que usa el detector.
- **`raw`** = `info->buf` del driver WiFi **tal cual**: sin filtrar, sin compensar e incluidas las
  subportadoras no válidas. Es el CSI crudo de cada paquete que esp-radar acepta del AP.
  - En el C5 con LLTF forzado (`tipo_dato = 1`) son palabras little-endian de 16 bits con valores de
    12 bits con signo (`((int16)(w << 4)) >> 4`).
  - La interpretación exacta de los pares en este modo **se verificará con datos reales** (primera prueba).
- **`valid`** = subportadoras válidas copiadas de `raw` según la tabla de esp-radar
  (`csi_sub_carrier_table.c`; para el C5, LLTF 20 MHz: rangos `{0,52}` y `{52,104}`), con la extensión de
  signo anterior, y luego **multiplicadas en el mismo buffer por un factor escalar** `comp`.
  - `comp` lo calcula `esp_csi_gain_ctrl_compensate_rx_gain()` (biblioteca **precompilada**) a partir de
    la ganancia AGC/FFT del paquete y de una línea base (mediana) de ganancias.
  - El factor se entrega en cada paquete, junto con `agc` y `fft`.
  - Si el redondeo o la saturación de esa multiplicación coinciden con `raw × comp` se comprueba con datos
    reales.
- **Amplitud** = √(a² + b²) por par de `valid`. Es lo que acumula la placa para `/crudo` (media y
  desviación por subportadora) y lo que dibuja el visor.
- Para la investigación conviene usar **`raw` más `agc`, `fft` y `comp`**, que son reproducibles sin la
  parte cerrada.

## 5. Vía nube (Firebase, proyecto aura-csi, plan Spark)

**Autenticación** (`aura_nube.c`):
1. `accounts:signInWithPassword` (Identity Toolkit) con `fb_email` y `fb_pass` del dispositivo devuelve
   `idToken` (1 h) y `refreshToken`.
2. Se renueva a los ~50 min con `securetoken.googleapis.com` (se cuentan en `renov`); si falla, se vuelve
   a iniciar sesión.

**Nunca la clave de servicio en la placa.**

**TLS:** `esp_http_client` con `esp_crt_bundle_attach` y el bundle **completo**. La verificación no se
puede desactivar (no hay opción en el código). Sin hora SNTP no se conecta, porque la vigencia de los
certificados no puede validarse.

**Escrituras** (solo al cambiar el estado o por intervalo):

| Ruta | Cuándo | Contenido |
|---|---|---|
| `/sensores/hab1/estado` | al cambiar | `estado` (CALIBRANDO, MOVIMIENTO, PRESENCIA_QUIETA, VACIA, SIN_MOVIMIENTO), `mov`, **`presencia`** (`no_disponible`, `vacia` o `presente`), `entrenada` (presencia utilizable), `alerta` (quietud ≥ 2 min), `desde`, `t` (servidor). **Sin entrenar** (al arrancar, tras un cambio de red o sin `TRAIN_STOP`), `presencia` es siempre `no_disponible` y el estado nunca es VACIA ni PRESENCIA_QUIETA. Lo exigen el firmware y las reglas `.validate` (T5: casos 36–39) |
| `/sensores/hab1/latido` | cada 60 s | `up`, `heap`, `heap_min`, `red`, `rssi`, `ver`, `renov`, `hms_s`, `ts_p95`, `reinicio` |
| `/sensores/hab1/comando` | por comando | `id`, `cmd`, `ok`, `detalle`, `origen` (usb, local o nube), `t` |
| `/crudo/hab1/<t0_ms>` | cada 10 s | `t0`, `t1`, `n`, `mov`, `pres`, `ncsi`, `nsub`, `jit` (jitter ×10⁴ separado por comas), `am` y `ad` (media y desviación de la amplitud por subportadora) |

**Volumen frente al plan Spark** (1 GB guardado, 10 GB/mes de descarga):

| Ítem | Por bloque | Por hora | Por día |
|---|---|---|---|
| `/crudo` (~163 jitter + 2 × 52 amplitudes) | ~1,4 KB | ~0,5 MB | **~12 MB** |
| `latido` y `estado` | — | ~20 KB | ~0,5 MB |
| Llenado de 1 GB sin borrar | | | **~80 días** |

Descargar cada sesión una vez suma unos 0,4 GB/mes, muy por debajo de los 10 GB.

**Descarga y borrado:** `C:\aura\analisis\descargar_crudo.py --sensor hab1`.
- Usa tu cuenta de usuario.
- Guarda `datos\crudos\nube_hab1_<fecha>.json`, verifica la copia y luego borra **solo** los bloques
  descargados (`PATCH` con `null`).
- Las reglas permiten a tu UID borrar bloques uno por uno, pero no escribir datos ni borrar `/crudo/hab1`
  completo.

**Comandos por la nube:** **consulta periódica** cada 5 s (`GET /comandos/hab1`), reutilizando la
conexión HTTPS.
- Se descartó el stream (SSE) porque mantendría una sesión TLS abierta todo el tiempo (RAM) y es más
  frágil ante cortes.
- La placa ejecuta los ids posteriores al último ejecutado, que guarda en NVS para no repetirlos tras un
  reinicio.
- Rechaza los de más de 10 min y confirma en `/sensores/hab1/comando`.
- Latencia esperada: ≤ 5 s + ida y vuelta (D5: ≤ 8 s).

**Reglas** (`C:\aura\firebase\database.rules.plantilla.json` → `preparar_reglas.py` con los dos UID):
- `/sensores` y `/crudo` los **escribe solo el UID de la placa** y los **lee solo tu UID**;
- `/comandos` lo **escribe solo tu UID** (sin poder leerlo) y lo **lee solo la placa**;
- sin acceso anónimo;
- `.validate` de estructura (campos exactos), valores (estados permitidos, origen), tamaño (longitud de
  cadenas), lista de comandos permitidos por expresión regular y `t` igual a la hora del servidor.
- La matriz completa está en `plan_pruebas.md` (T5 y D6).

**App:** inicia sesión con **tu** cuenta (correo y contraseña), ya no de forma anónima. Lee `/sensores`
y escribe `/comandos`.

## 6. Comandos de las tres vías

- **Cola única** (`aura_comandos.c`) en **estricto orden de llegada**, sin prioridad entre USB, local y
  nube.
- **Bloqueo de entrenamiento:** si una vía hizo `TRAIN_START`, los `TRAIN_*` y `RESET_BASELINE` de las
  otras vías se rechazan ("entrenamiento en curso desde <vía>") hasta su `TRAIN_STOP`.
- **Registro del origen:** cada ack HMS lleva `origen` e `id` (USB y local); la nube los confirma en
  `/sensores/hab1/comando` con su origen.

## 7. Redes principal y de respaldo

- `aura_wifi.c` intenta la red principal. Tras 3 intentos fallidos seguidos (20 s cada uno) pasa a la de
  respaldo, y viceversa, con esperas de 2, 4, 8, 16 y 30 s.
- Admite WPA2 y WPA3 (`sae_pwe_h2e = BOTH`).
- Al cambiar de AP o de puerta de enlace se **recrea el detector**, porque `esp_wifi_sensing` guarda la
  puerta de enlace en caché. Eso recalibra y **pierde el entrenamiento de presencia**: hay que volver a
  entrenar (`TRAIN_START`/`TRAIN_STOP`). El estado queda en `SIN_MOVIMIENTO` hasta entonces.
- Provisionamiento desde el celular: pendiente.

## 8. Resiliencia

- Ninguna vía bloquea a otra: colas no bloqueantes (se descarta y se cuenta), `MSG_DONTWAIT`, USB sin
  bloqueo y solo con host presente.
- Esperas crecientes:

  | Componente | Esperas |
  |---|---|
  | WiFi | 2 → 30 s |
  | Inicio de sesión en la nube | 5 → 300 s |
  | Errores HTTP repetidos | 5 → 300 s |
  | Sockets locales | 2 s |

- Watchdog de tareas de 30 s y coredump en flash.
- `usb_serial_jtag_is_connected()` evita escribir por USB con cargador o batería (no hay SOF).

## 9. OTA local autenticada

TCP 45456, una actualización a la vez. Cabecera `AURAOTA <ctr> <tamaño> <sha256> <hmac>`, con
`hmac = HMAC-SHA256(local_key, "<ctr> OTA <tamaño> <sha256>")`.

Antes de activar la imagen, la placa comprueba:
1. el HMAC y que el contador sea reciente;
2. que el tamaño quepa en la ranura;
3. que la versión actual no esté pendiente de validar;
4. el **SHA-256 de lo recibido** contra la cabecera autenticada;
5. `esp_ota_end()`, que valida el formato de la imagen.

Después hay vuelta atrás automática si la nueva no se valida. Herramienta: `ota_local.py`.

**Limitaciones (prototipo):** sin **secure boot** ni **cifrado de flash**. Con acceso físico se puede
grabar cualquier firmware por USB y leer la flash, incluida la NVS con las credenciales.

## 10. Telemetría (cada 10 s, por USB y por la vía local)

`{"type":"telemetria", ...}` con:
- `heap_libre`, `heap_minimo`, `hms_por_s`, `ts_mediana_ms`, `ts_p95_ms` (intervalo entre `ts_ms` de las
  muestras), `motivo_reinicio` y `encendido_s`;
- además: `ver`, `red`, `rssi`, `cambios_red`, `sntp`, `usb`, `local_subs`, `local_seq`,
  `local_descartes`, `csi_total`, `detector_recreado`, `estado`, `nube`, `nube_renovaciones`,
  `nube_errores`, `particion`, `estado_ota` y `rx_buf`.

### Marca de agua de las pilas (desde el 23/10)

- Cada 60 s se emite `{"type":"pilas","encendido_s":…,"tareas":{"aura_wifi":{"tam":5120,"libre_min":…},…}}`
  por USB y por la vía local. Incluye las 7 tareas propias: `aura_wifi`, `aura_local`, `aura_cmd`,
  `aura_ota`, `aura_nube`, `aura_tel` y `web_serial_moni`.
- `libre_min` es `uxTaskGetStackHighWaterMark`, en **bytes**: en IDF la pila es de `uint8_t`.
- Los tamaños están centralizados en `main\aura_pilas.h`.
- Después de D1 y D3, `analisis\pruebas\pilas_propuesta.py <capturas>` propone para cada tarea
  `ceil(1,25 × usado_max / 256) × 256` (mínimo 2 KB). Solo vale para los caminos que se ejecutaron durante
  la medición: tiene que haber pasado al menos una renovación de token y, para `aura_ota`, una OTA.

### ¿Conviene fusionar tareas de red? (evaluación; se decide con las mediciones)

| Fusión | Ahorro aprox. | Costo y riesgo |
|---|---|---|
| **`aura_ota` dentro de `aura_local`**: el mismo bucle hace `select` sobre el socket UDP y el de escucha TCP | ~5 KB (6 KB de pila menos ~1 KB más en la local) | Bajo. Durante una OTA (~10–30 s) se pausa la vía local, lo que es aceptable porque la OTA termina en reinicio |
| **Telemetría dentro de `aura_cmd`**: `xQueueReceive` con espera hasta la próxima telemetría | ~4,5 KB | Bajo. Un comando largo retrasa la telemetría unos segundos |
| **`aura_wifi` como manejadores de eventos con `esp_timer`**, sin tarea propia | ~5 KB, pero parte se pierde | Medio. La recreación del detector correría en la tarea de eventos del sistema, cuya pila habría que agrandar |
| `aura_nube` con otra tarea | — | **No conviene.** Las llamadas HTTPS bloquean varios segundos y el handshake TLS necesita la pila de 8 KB |

**Recomendación:** primero **ajustar los tamaños** con las marcas de agua de D1 y D3. Si cada tarea usa
~3 KB de sus 5 KB, eso solo libera ~10–12 KB sin reestructurar nada. Fusionar (empezando por OTA dentro de
la vía local y la telemetría dentro de los comandos, ~10 KB más) solo si después sigue faltando memoria.

## 11. Visor en la PC (`C:\aura\analisis\visor.py`)

- `--vivo`: muestra el mapa de calor de la amplitud, la señal suavizada del detector con sus umbrales de
  entrada y salida, y el estado.
  - Usa la vía local. Si no llegan datos en 10 s y se pasó `--nube`, consulta `/sensores` y el último
    bloque de `/crudo` con **tu** cuenta.
  - Graba lo recibido en `datos\crudos`.
- `--reproducir archivo`: reconstruye el panel desde la grabación, ordenada por la hora SNTP de la placa.
  Con `--exportar DIR --fps N` escribe un PNG por cuadro, con la hora UNIX en milisegundos en el nombre y
  en la imagen, para alinearlo con el video. Probado en T4d.

## 12. Limitaciones declaradas

1. **Credencial del dispositivo en NVS sin cifrado de flash.** Con acceso físico se puede leer.
   - **Cómo revocarla:** consola de Firebase → Authentication → Usuarios → cuenta del dispositivo →
     **Inhabilitar cuenta** (corta el inicio de sesión y la renovación de tokens) o cambiar su contraseña.
     Después, cargar la nueva con `cargar_credenciales.py --claves fb_pass`.
   - Cambiar también la contraseña del WiFi y la `local_key` si la placa se pierde.
2. **Datos locales sin cifrar** (sección 3).
3. **Sin secure boot.**
4. **Detección y control de ganancia precompilados** (`esp_radar_motion_dec`, `esp_csi_gain_ctrl`). La
   investigación debe usar `raw` con procesamiento propio (ver `evaluacion_wifi_sensing.md`).
5. **La alerta de quietud no distingue entre reposo y caída.**
6. **Sin push sin la PC.** Las notificaciones FCM necesitarían la clave de servicio, que no va en la placa.
   La app ve la alerta mientras está abierta (lee `/sensores/hab1/estado.alerta`).
7. **Cambiar a la red de respaldo exige volver a entrenar la presencia.**

## 13. Esfuerzo y riesgos por punto

| Punto | Estado | Esfuerzo restante | Riesgo | ¿Necesita USB? |
|---|---|---|---|---|
| Particiones, vuelta atrás, `-Os` | hecho, T1/T2 aprobadas | — | bajo | **sí: la grabación inicial** (cargador nuevo y tabla) |
| Secretos en NVS y carga por USB | hecho | prueba D1 | bajo | sí (carga por USB) |
| Vía local (UDP, anuncio, receptor) | hecho, T4 aprobada en simulación | D4, D2 | medio: carga de la placa | no |
| CSI crudo | hecho | verificar el formato con datos reales | **medio**: modo LLTF de 16 bits sin verificar | no |
| Comandos locales con HMAC | hecho | D1/D8 | bajo | no |
| Vía nube (auth, renovación, escrituras, comandos) | hecho, sin probar | D3, D5, D6 | **medio**: RAM del TLS, primera conexión real | no |
| Reglas | hechas | T5 (instalación pendiente) y D6 | bajo | no |
| Redes principal y respaldo | hecho | D7c | medio: recreación del detector | no |
| Resiliencia | hecho | D7a, D7b, D3 | medio | no |
| OTA y vuelta atrás | hecho; variante de prueba compilada | D8 | medio | no (salvo la grabación inicial) |
| Telemetría | hecha | — | bajo | no |
| Visor | hecho, T4d aprobada | probarlo en vivo | bajo | no |
| **RAM total** | **sin medir** | D3, D9 | **alto** | una OTA si hay que recortar |

Después de la grabación inicial por USB, los cambios de firmware pueden ir por OTA. Vuelve a hacer falta
USB solo si cambia la tabla de particiones o el cargador, o si una imagen nueva no se puede validar y
tampoco la anterior.
