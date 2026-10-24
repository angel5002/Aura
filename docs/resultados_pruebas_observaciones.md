# Observaciones sobre los resultados

Complementa `resultados_pruebas.md` sin modificar sus filas.

---

## 23/10/2026 — Corrección de un falso positivo en T3 (autorizada) y nueva ejecución

**Corrección autorizada** (mensaje del 23/10/2026): se excluyen **solo** las tres cadenas exactas de
`components/mbedtls/mbedtls/library/pk_internal.h`:
- `-----BEGIN RSA PRIVATE KEY-----` (línea 36);
- `-----BEGIN EC PRIVATE KEY-----` (línea 40);
- `-----BEGIN PRIVATE KEY-----` (línea 42).

La exclusión aplica **solo si no las sigue un bloque base64** (≥ 40 caracteres `[A-Za-z0-9+/]`, tras
espacios o saltos de línea opcionales).

Implementación en `analisis\pruebas\t3_secretos.py`, función `contar_pem`:
- detecta cualquier encabezado `-----BEGIN <...> PRIVATE KEY-----`;
- cuenta como secreto todo encabezado seguido de base64, sea cual sea;
- cuenta también todo encabezado que no sea una de las tres cadenas;
- autoprueba en `t3_autoprueba_pem.py`: **7/7** (las tres constantes se excluyen; RSA y PKCS8 seguidas de
  base64, ENCRYPTED y OPENSSH cuentan).

**Nueva ejecución de T3 → FALLIDA (1 coincidencia).** El detector, más general que el patrón original,
encontró un **cuarto** encabezado en `aura_nodo.bin` (offset 0x130ec): `-----BEGIN ENCRYPTED PRIVATE KEY-----`.
Es otra constante de mbedTLS (`pk_internal.h`, **línea 44**, `PEM_BEGIN_ENCRYPTED_PRIVATE_KEY_PKCS8`),
seguida de un byte nulo, **sin base64**. El patrón original (`BEGIN (RSA |EC )?PRIVATE KEY`) no la
detectaba. **No se excluyó porque la autorización cubre solo tres cadenas.** Decisión pendiente: autorizar
también esta cuarta cadena exacta (línea 44), con la misma condición de "sin base64".

Valores reales en esta ejecución: SSID de menuconfig 0, marcadores 0, API keys 0, JWT 0, `private_key` 0.

## 23/10/2026 — Cuarta constante de mbedTLS excluida (autorizada) y T3b

- **Autorizado el 23/10/2026:** se excluye también `-----BEGIN ENCRYPTED PRIVATE KEY-----`
  (`pk_internal.h`, línea 44, `PEM_BEGIN_ENCRYPTED_PRIVATE_KEY_PKCS8`), con la misma condición: **solo si
  no la sigue un bloque base64**. Autoprueba `t3_autoprueba_pem.py`: **9/9**. Las cuatro constantes sin
  base64 se excluyen; RSA, PKCS8 y ENCRYPTED seguidas de base64 cuentan; DSA y OPENSSH, que no están en
  la lista, cuentan.
- **T3b (nuevo):** verifica que ningún `sdkconfig` de `aura_nodo` contenga valores secretos. Revisa el
  principal, `sdkconfig.rollback`, `sdkconfig.build_rx64`, `sdkconfig.build_bajo_ram`, `sdkconfig.defaults`
  y los tres archivos de variantes. Criterio:
  - 0 opciones **de texto** con nombre sensible (SSID, PASS, PASSWORD, PSK, SECRET, TOKEN, EMAIL,
    API_KEY, PRIVATE, CREDENTIAL, KEY, USER) y valor no vacío;
  - 0 opciones `CONFIG_EXAMPLE_WIFI_*`;
  - 0 apariciones de los valores secretos conocidos, en texto y en hexadecimal.

  Hay 26 opciones con nombre sensible en cada `sdkconfig` generado, pero **todas son booleanas o
  numéricas**: ninguna de texto. Autoprueba con un `sdkconfig` falso: detecta la contraseña y la
  `CONFIG_EXAMPLE_WIFI_SSID` (3 hallazgos); en el caso limpio, 0.

## Límite de T3: no detecta secretos compilados en las instrucciones

- T3 busca **bytes contiguos** (texto, hexadecimal y patrones). Si un secreto se compila en el firmware
  (por ejemplo, una contraseña de `menuconfig` que inicializa una estructura), el compilador RISC-V puede
  convertirlo en **valores inmediatos repartidos entre instrucciones** (`lui`/`addi`/`sw`) y no quedar como
  texto en el binario.
- Se comprobó el 23/10: en el `wifi_sensing.bin` compilado con la contraseña del WiFi no aparecían **ni
  sus 4 primeros bytes**. Por eso **un 0 en T3 no prueba por sí solo que no haya secretos compilados.**
- **La garantía de `aura_nodo` es de diseño**, no de la búsqueda:
  1. ninguna credencial pasa por Kconfig ni por el código: se leen de NVS en ejecución
     (`aura_config_leer`), cargadas por USB con `cargar_credenciales.py`;
  2. **T3b** verifica que ningún `sdkconfig` (de donde saldrían secretos compilados) tenga valores
     secretos;
  3. el código no usa `CONFIG_EXAMPLE_WIFI_*` ni ninguna otra opción de credenciales:
     `protocol_examples_common` se quitó del proyecto.

  T3 queda como red de seguridad adicional, sobre todo para texto, claves PEM, API keys y tokens.

## 23/10/2026 — Filas de T1, T2 y T3 que midieron un binario viejo

Tras agregar las opciones `AURA_LOCAL_COLA_KB` y `AURA_NUBE_BUFFER_KB`, la compilación principal falló
(`CONFIG_AURA_NUBE_BUFFER_KB undeclared`): el `sdkconfig` existente no las había incorporado. Las filas de
T1, T2 y T3 registradas a continuación (T1 con **1.180.656 B**) **midieron el binario anterior**, que
seguía en `build\`. Se corrigió con `idf.py reconfigure`. Las filas válidas para v0.1.0 definitiva son
las siguientes (T1 con **1.180.736 B, 24,93 % libre**): T1 APROBADA, T2 APROBADA, T3 FALLIDA (cuarta
constante de mbedTLS, ver arriba).

## 23/10/2026 — Contraseña de menuconfig borrada de `wifi_sensing`

- Se reemplazó `CONFIG_EXAMPLE_WIFI_PASSWORD` por el valor por defecto (`"mypassword"`) en
  `firmware\wifi_sensing\sdkconfig` y se recompiló `wifi_sensing`, para regenerar `build\config\sdkconfig.h`,
  `sdkconfig.json`, `sdkconfig.cmake` y el binario.
- Búsqueda de la contraseña anterior (texto y hexadecimal) en **todo `C:\aura`**, sin mostrarla:
  - **antes**: 4 coincidencias, en `sdkconfig` y en los tres `build\config\sdkconfig.*`;
  - **después**: **0 coincidencias en 17.464 archivos**.
- El valor se leyó desde un archivo temporal del scratchpad (fuera de `C:\aura`), que se sobrescribió
  con ceros y se borró.
- **Limitación de método detectada:** la contraseña **no aparecía como texto** en el `wifi_sensing.bin`
  compilado con ella, ni siquiera sus 4 primeros bytes. El compilador RISC-V la convirtió en **valores
  inmediatos dentro de las instrucciones** al inicializar `wifi_config`. Una búsqueda de cadenas como la
  de T3 **no detecta secretos compilados en el código**.
  - En `aura_nodo` esto no aplica: por diseño ninguna credencial se compila (todas vienen de NVS).
  - La placa B **todavía** tiene grabado el `wifi_sensing` anterior con la contraseña. El borrado completo
    del flash, autorizado para mañana, la elimina.
- El SSID sigue en `firmware\wifi_sensing\sdkconfig`; no se pidió borrarlo.

## 23/10/2026 — T5 ejecutada

`firebase-tools` 15.34.1, `@firebase/rules-unit-testing` 6.0.0 y `firebase` 13.1.0 se instalaron **en local**
(`C:\aura\firebase\node_modules`, autorizado; `firebase` no queda en el PATH global). El emulador descargó
su JAR (`firebase-database-emulator-v4.11.2.jar`) a la caché de usuario (`%USERPROFILE%\.cache\firebase`).
**Resultado: 39/39**, incluidos los 4 casos nuevos del estado de presencia (36–39).

---

## 22/10/2026 (noche)

## T3 — FALLIDA (3 coincidencias): diagnóstico, criterio sin cambiar

- Las 3 coincidencias son del patrón "clave privada PEM" en `aura_nodo.bin`, en los offsets 0x12fb1,
  0x12ff1 y 0x1302d de la imagen de las 19:5x. Son las cadenas `-----BEGIN RSA PRIVATE KEY-----`,
  `-----BEGIN EC PRIVATE KEY-----` y `-----BEGIN PRIVATE KEY-----`, que mbedTLS define como constantes para
  **reconocer** claves al parsearlas: `components/mbedtls/mbedtls/library/pk_internal.h`, líneas 36, 40 y
  42 (`PEM_BEGIN_PRIVATE_KEY_*`).
- Comprobación: después de cada cabecera vienen `-----` y un byte nulo, **sin material base64**. Además,
  esas cadenas no aparecen en `wifi_sensing.bin`, que no enlaza TLS.
- Valores reales: **0** coincidencias del SSID y la contraseña de menuconfig (también en hexadecimal),
  **0** marcadores `myssid`/`mypassword`/`CONFIG_EXAMPLE_WIFI_*`, **0** API keys `AIza…`, **0** tokens JWT y
  **0** `private_key`.
- **No se cambió el criterio ni el estado.** Queda a tu decisión si el patrón PEM debe exigir material
  base64 después de la cabecera (por ejemplo, `BEGIN … PRIVATE KEY-----\s*[A-Za-z0-9+/]{40,}`) o excluir
  las constantes conocidas de mbedTLS. Si lo apruebas, se vuelve a ejecutar T3 y se agrega una fila nueva.
- Informativo: `firmware\wifi_sensing\sdkconfig`, del proyecto anterior que hoy está grabado en la placa
  B, **todavía contiene** la contraseña del WiFi de menuconfig (1 coincidencia). Está fuera de git; ver
  `grabacion_aura_nodo.md`, paso 8.

## T5 — NO EJECUTADA

- Node.js 24.21 y Java 21 están instalados; `firebase-tools` y `@firebase/rules-unit-testing` **no**.
- Instalarlos (`npm install` en `C:\aura\firebase`; el emulador además descarga su JAR la primera vez) es
  instalar programas: **queda pendiente de tu autorización** (regla 1).
- Está todo listo: `firebase\pruebas\reglas.test.mjs` (35 casos, sintaxis verificada con
  `node --check`), `firebase\firebase.json`, `firebase\package.json` y `analisis\pruebas\t5_reglas.py`.
- Alternativa sin instalar: probar la matriz a mano en el Simulador de reglas de la consola
  (`plan_pruebas.md`).

## Hallazgos de la compilación

- **IPv6 es obligatorio**: con `CONFIG_LWIP_IPV6=n`, `esp_wifi_sensing.c:855` no compila (`ip_addr_t` sin
  `u_addr`). Se mantiene activado y está documentado en `sdkconfig.defaults`.
- **Error corregido antes de la entrega**: la tarea que lee la consola USB solo se creaba al conectarse a
  WiFi, así que en una placa recién grabada no se podrían haber cargado las credenciales. Ahora arranca
  siempre en `app_main`.
- Ninguna advertencia del compilador en el código de AURA. Las únicas advertencias vienen de
  `managed_components/espressif__esp-radar/src/esp_radar.c` (`-Wstrict-aliasing`, código de Espressif).


## Observación preliminar con 0.1.1 (23/10/2026) — NO es D1

Escucha USB de 10 min sin reinicio por RTS (`datos\crudos\P1_011.csv`), con las credenciales recién
cargadas. La placa venía de un `AURA REBOOT` (motivo `software`); la captura cubre `encendido_s` 280 → 870.

| Qué | Resultado |
|---|---|
| WiFi | conectada a la red **principal** (RSSI −38 a −41 dBm), SNTP sincronizado |
| Detector | fuera de calibración (estable); estado **MOVIMIENTO** en las 60 telemetrías (10 min seguidos), CSI ~17 muestras/s, p95 del intervalo 60 ms |
| Firebase | sesión iniciada (1 token), estado `operando`, escrituras 32 → 108 con **0 errores** (respuestas 2xx de la base) |
| Memoria libre | 62,3–62,7 KB, estable |
| **Memoria mínima histórica** | **21.912 B (< 30 KB)** — ocurrió antes de los 280 s (arranque, conexión o handshakes TLS) |
| Reinicios | 0 |
| Pilas (libre mín.) | wifi 2652, local 2916, cmd 4316, ota 5592, nube 4916, tel 2028, monitor 2036 B |

- **Se aplica la regla de parada** (mínima < 30 KB): no se sigue con la 0.1.2 hasta decidir entre la
  variante `bajo_ram`, otros ajustes de memoria o el ajuste de pilas.
- Con 0.1.1 no se puede saber en qué momento ocurrió el mínimo (la telemetría es cada 10 s y la captura
  empezó a los 280 s). La 0.1.2 emite `{"type":"memoria"}` en cada momento clave.
- El estado MOVIMIENTO continuo no se interpretó: puede ser actividad real cerca de la placa o
  sensibilidad sin línea base; se evalúa en las pruebas con la habitación vacía.
- La escritura en `/sensores/hab1` se infiere del contador de escrituras con respuesta 2xx; no se leyó la
  base con la cuenta de la persona.


## Diagnóstico de memoria con 0.1.2 (23/10/2026) — observación, NO es D1

0.1.2 grabada por USB sin borrado (T1–T3 y T3b APROBADAS; D0 APROBADA). Capturas `D0_012.csv` (0–140 s) y
`P2_012.csv` (75 min, hasta 4650 s de encendido), sin reinicios. Análisis: `analisis\diagnostico_memoria.py`.
La telemetría informa el mínimo de cada intervalo de 10 s, el bloque libre más grande y las asignaciones
fallidas; hay marcas de inicio/fin de cada handshake TLS y de cada inicio de sesión o renovación.

| Momento | Mínimo (B) | Bloque mayor (B) | Detalle |
|---|---|---|---|
| Régimen estable | ~53.700 (mediana por intervalo) | 34.816 | libre ~62.100; cada 10 s baja ~9 KB al publicar `/crudo` |
| Inicio de sesión (TLS auth, 15 s) | 55.364 | 47.104 | handshake 501 ms |
| 1.ª conexión a la base (TLS db, 16 s) | **44.576** | 34.816 | handshake 1052 ms |
| Reconexión implícita de la base (2936 s) | **41.876** | 34.816 | el servidor cerró el keep-alive |
| Renovación del token (3016 s): auth + db | 47.684 / **40.472** | 36.864 / 38.912 | la sesión de la base se cierra antes: nunca hay dos TLS a la vez |
| **Episodio 1 (970–980 s)** | **48** | 34.816 al informar | 126 asignaciones fallidas; sin TLS ni registros |
| **Episodio 2 (1080–1090 s)** | **3.344** | 34.816 al informar | 16 asignaciones fallidas |
| **Episodio 3 (1410–1420 s)** | **2.704** | 34.816 al informar | 0 fallidas |

- **142 asignaciones fallidas** en total, la mayor de **2.368 B**; ningún error de TLS, mbedTLS ni HTTP; nube con
  0 errores (696 escrituras, 1 renovación correcta); 0 reinicios.
- Los tres episodios: duran menos de 10 s, no coinciden con ningún handshake ni con registros de error, y la
  tasa de CSI no cambia. `esp_radar` registra un aviso cuando no consigue memoria y no hay ninguno: las
  asignaciones que fallaron son de un componente que falla en silencio. El tamaño (≤ 2.368 B) coincide con un
  buffer de recepción WiFi con CSI (el arranque informa 2212 B: rxctrl 64 + CSI 512 + trama). **Atribución:
  ráfaga de recepción WiFi** (muy probable; no confirmada por el llamador de cada asignación).
- CSI de referencia (para comparar tras la corrección): **101,4 CSI/s** (mediana; p5 94,5), **17,0 muestras/s**
  (p5 16,8), p95 del intervalo 60 ms.
- El 21.912 B de la 0.1.1 es compatible con un episodio de este tipo.


## Observación de 0.1.3 (23/10/2026) — diagnóstico, NO es D1

Cambios respecto de 0.1.2 (antes → después): buffers dinámicos de recepción WiFi 128 → **12**; ventana BA 6 →
**12** (= mín(2 × 10 estáticos, 12 dinámicos), guía de Espressif); ventana TCP 5760 → **12288** (= 12 KB);
`KEEP_PEER_CERTIFICATE` y → **n**; diagnóstico de CPU por tarea, cola de lwIP y tráfico de entrada.
T1–T3 y T3b APROBADAS; D0 APROBADA. Capturas `D0_013.csv` + `P3_013.csv` (4460 s de encendido, sin reinicios),
solo USB (receptor local no activo). Análisis: `analisis\diagnostico_013.py`.

| Criterio ampliado | Medido | Resultado |
|---|---|---|
| 0 asignaciones fallidas | **0** (0.1.2: 142) | CUMPLE |
| Mínimo por intervalo ≥ 30 KB | 142 de 438 intervalos por debajo; mediana 39,7 KB; mínimo **9.268 B** | **NO CUMPLE** |
| CSI dentro del 5 % (ref. 101,4/s; p5 94,5) | 102,2/s (+0,8 %); p5 100,9; muestras 16,8/s | CUMPLE |
| p95 del intervalo entre muestras ≤ 65 ms | mediana 60, máximo 61 ms | CUMPLE |
| Nube sin errores ni reintentos anómalos | **1 error**: 401 en la 1.ª escritura de `/crudo` (27 s); 1 renovación correcta; 6 handshakes | **NO CUMPLE** (1 error) |
| Pérdida en la vía local < 1 % | receptor local no activo | NO EVALUADO |

- **Hipótesis de falta de CPU de la pila de red: DESCARTADA.** IDLE 76,6 % (mín. 71,3 %); `tiT` 4,1 %;
  `csi_handle` 1,9 % y `csi_combine` 1,6 % (prioridad 24); `wifi` 8,9 %. Cola de `tiT`: máximo 4 de 32,
  0 descartes por cola llena, también durante los episodios.
- **Tráfico real**: desde los 2280 s, tormentas de ARP de hasta 2242 broadcast cada 10 s (217 intervalos),
  siempre junto con segmentos TCP descartados por lwIP (los mismos 217 intervalos): patrón de un equipo de la
  red haciendo un barrido. Con 12 buffers no provocaron asignaciones fallidas, y el mínimo en esos intervalos
  (mediana 38,8 KB) es similar al resto (41,8 KB).
- **Caídas cortas nuevas**: el mínimo por intervalo empeoró respecto de 0.1.2 (mediana 53,7 → 39,7 KB) y el
  libre bajó ~7 KB (costo del diagnóstico). Las caídas duran casi siempre < 20 ms (el muestreador solo vio 3
  episodios, de ~0,5 s, mínimo 24 KB) y no se relacionan con TLS (1 de 142), con TCP, con broadcast ni con la
  cola. Hipótesis a probar: la ventana BA 12 (agregados de hasta 12 tramas = 12 buffers de ~2,4 KB) y la
  ventana TCP de 12 KB, que duplicaron la ráfaga máxima respecto de 0.1.2 (BA 6, 5,6 KB).


## 0.1.4 (23/10/2026): D0 FALLIDA por agotamiento de memoria durante una tormenta de ARP

Cambios respecto de 0.1.3: ventana BA 12 → **6** y ventana TCP 12288 → **5760** (12 buffers dinámicos se
mantienen); errores de la nube con su cuerpo (token vencido / rechazo / red) y bloque `/crudo` conservado;
emisores de las tormentas de ARP. T1–T3 y T3b APROBADAS; MAC verificada; grabada sin borrar.

- **D0 FALLIDA** (`D0_014.csv`): a los ~60 s la memoria libre llegó a 12 B; `esp_radar` reintentó cada 100 ms
  (`<ESP_ERR_NO_MEM> esp_radar_rebuild_csi_data:619`), fallaron el ping y `mmap`, y un `printf` con `%f` abortó:
  `assert failed: newlib/libc/stdlib/dtoa.c:239 (REENT malloc succeeded)` (traza: `_svfprintf_r` → `_dtoa_r`).
  Reinicio por pánico. Tras el reinicio siguió 80 s sin volver a caer. No se ejecutó la observación de 70 min
  (regla: con D0 fallida no se hacen otras pruebas).
- Durante el arranque había una tormenta de ARP en curso; en los episodios la cola de `tiT` llegó a **11–12**
  (= los 12 buffers) con la CPU 44–80 % libre: la pila de red no estaba sin CPU, sino detenida o lenta por otra
  causa (a confirmar).
- **Origen de las tormentas**: un solo equipo de la red, MAC `a0:d3:c1:24:88:c6`, IP `192.168.0.89`
  (también en la tabla de vecinos de la PC), con 350–2163 broadcast ARP cada 10 s. No es la PC (`dc:4a:3e:88:8c:39`,
  192.168.0.132, 1 broadcast). Durante P3_013 (desde los 2280 s) solo corría `capturar.py` (USB), sin tráfico de red.
- **Causa del 401 de `/crudo` (0.1.3, 27 s)**: `aura_tiempo_sincronizado()` solo comprueba que el año sea > 2025,
  y el ESP32 conserva la hora tras un reinicio por software o USB. La nube arrancó con la hora vieja (~29,6 s
  adelantada respecto de la PC), abrió el primer bloque y luego SNTP corrigió el reloj hacia atrás: t1 < t0, que
  la regla `t1 >= t0` rechaza. Reproducido en el emulador (`firebase\pruebas\reproducir_401.mjs`): el bloque típico
  pasa y t1 < t0 da 401; las otras violaciones posibles (n > 512, nsub > 64, jit > 3200, campo extra) el firmware
  no las puede producir, y am/ad > 800 exigiría amplitudes ≥ 10^13.
- Costo de memoria del diagnóstico: ~9,8 KB. 0.1.3 descontándolo: mínimo por intervalo mediana 48,3 KB, p5 27,4,
  mínimo 18,6 KB; intervalos < 30 KB: 48 de 438 (medido: 142).


## Memoria en modo solo local (0.1.3 sin `fb_pass`) y decisión para el video (23–24/10/2026)

- **45 min sin tormenta: APROBADA** (`M1_013_local.csv`): 0 asignaciones fallidas, mínimo por intervalo 34,5 KB
  (mediana 61,6), CSI 100,6/s (−0,8 %), p95 ≤ 61 ms, 0 reinicios.
- **20 min con tormenta de ARP: FALLIDA** (`M2_013_tormenta.csv`, desde 18:41:25; 120 de 120 intervalos con
  tormenta, mediana 1398 broadcast/10 s): el mínimo por intervalo bajó a **26,4 KB** (2 de 120 intervalos < 30 KB;
  < 20 ms, sin episodios del muestreador). El valor medido **incluye ~9,8 KB que ocupa el diagnóstico**; el
  criterio (≥ 30 KB medido) no se cambia. **No hubo asignaciones fallidas ni reinicios**; CSI 105,5/s, p95 ≤ 61 ms.
- **Decisión del 24/10/2026**: la **0.1.3 en modo solo local** (sin `fb_pass`, diagnóstico incluido) es la
  versión para el video. No se compila una versión sin diagnóstico antes del video.


## Formato del CSI crudo del C5 (D11 con datos reales, 24/10/2026)

Captura `F1_sin_regla_local.csv` (5 min, 30.159 paquetes `csi`, todos LLTF: rx_format 4, cwb 0).

- **Lo que entrega la placa**: `len` = 106 bytes = **53 palabras de 16 bits con valores de 12 bits con signo**
  (modo `lltf_bit_mode` = 0, el valor por defecto según `esp_wifi_he_types.h`: "0: 12-bit, 1: 8-bit, default:
  12-bit"). Evidencia: en el 100,00 % de las palabras el byte alto está en 0x00–0x0F (solo se usan los 4 bits
  bajos, como corresponde a 12 bits); con valores de 8 bits ese byte sería un valor más y se repartiría.
  La palabra 53 vale 0 en el 100 % de los paquetes (relleno).
- **Subportadoras**: las 52 primeras palabras son **26 pares (imaginario, real) = 26 subportadoras complejas**.
- **Comparación**:
  - IDF v5.5 (`wifi.rst`, sección esp32c5): LLTF "0~26, -26~-1", 106 bytes, "two bytes of signed characters,
    imaginary part followed by real part" → 53 subportadoras **en el modo de 8 bits**. Esa tabla no describe el
    modo de 12 bits que usa la placa.
  - esp-radar (`copy_subcarrier_data`, `csi_write_frame_to_ring`): en modo de 16 bits exige `len == 106`, lee
    palabras uint16 con extensión de signo de 12 bits en los rangos de bytes {0,52} y {52,104} (52 valores) y
    calcula la amplitud con 4 bytes por subportadora → 26 subportadoras.
  - esp-csi `csi_recv_router` (C5, LLTF forzado): imprime `(len − 2) / 2 = 52` valores de 12 bits; el parser
    `csi_data_read_parse.py` tiene la rama `csi_data_len == 52` → 26 subportadoras complejas (real en la
    posición impar, imaginario en la par).
- **Conclusión**: el decodificador de AURA (`aura_proto.decodificar_csi`) coincide con los dos parsers oficiales
  (26 subportadoras de 12 bits); **no se cambia**. El mapa de calor (26 filas) y los datos guardados son
  correctos; el buffer `raw` completo (106 B) se guarda siempre, así que no se pierde información.
- **Abierto**: qué subportadoras físicas son esas 26 no está documentado para el modo de 12 bits. El visor
  oficial agrupa los 52 valores en dos mitades de 13 subportadoras ((0,12) y (13,26)), lo que sugiere que
  cubren todo el canal (−26..26) con paso 2, pero es una inferencia, no una verificación. Para confirmarlo
  haría falta capturar con `lltf_bit_mode` = 1 (8 bits, 53 subportadoras) y comparar: no se hace antes del video.
