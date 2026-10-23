# Plan de pruebas — AURA nodo (dos vías)

Firmware: `C:\aura\firmware\aura_nodo` (v0.1.0). Scripts: `C:\aura\analisis\pruebas\`.
Resultados: `C:\aura\docs\resultados_pruebas.md`; cada ejecución agrega una fila con fecha.
**Regla:** si una prueba falla, se registra FALLIDA y se informa. No se cambia el criterio ni se marca
como aprobada.

Python de las pruebas: `C:\aura\analisis\.venv\Scripts\python.exe` (en adelante `py`).

---

## Sin placa

| Id | Qué se prueba | Procedimiento | Criterio de aprobación |
|---|---|---|---|
| **T1** | Compilación con `-Os` y margen OTA | `idf.py -C C:\aura\firmware\aura_nodo build`; luego `py pruebas\t1_compilacion.py` | `CONFIG_COMPILER_OPTIMIZATION_SIZE=y` y **≥ 20 % libre** en cada ranura OTA de 1,5 MB |
| **T2** | Tabla de particiones | `py pruebas\t2_particiones.py` (usa `gen_esp32part.py` de IDF) | Válida para 4 MB; sin solapamientos; apps alineadas a 64 KB; el cargador no pisa la tabla (0xA000) |
| **T3** | Secretos en la imagen | `py pruebas\t3_secretos.py`: busca en `.bin`, cargador, `sdkconfig`, `sdkconfig.defaults` y `build\config` el SSID y la contraseña cargados antes por menuconfig, la clave local y la API key (si existen en `secretos\`), sus versiones en hexadecimal y patrones (marcadores de menuconfig, PEM, `private_key`, `AIza…`, JWT). Solo informa cuántas coincidencias hay | **0 coincidencias**; el `sdkconfig` de `aura_nodo` no contiene la contraseña del WiFi. Corrección autorizada el 23/10: se excluyen SOLO las 4 cadenas exactas de `pk_internal.h` (líneas 36, 40, 42 y 44) cuando no las sigue un bloque base64; cualquier encabezado PEM seguido de base64 sigue contando. **T3b:** ningún `sdkconfig` de `aura_nodo` (principal y variantes) tiene opciones de texto con nombre sensible y valor, ni `CONFIG_EXAMPLE_WIFI_*`, ni valores secretos conocidos. Límite: no detecta secretos compilados como inmediatos en instrucciones (la garantía es de diseño; ver observaciones) |
| **T4** | Receptor local con flujo simulado | `py pruebas\t4_receptor_simulado.py`: simulador UDP en 127.0.0.1 con 5.000 datagramas, 1 % perdido, ~2 % de pares desordenados y 10 duplicados | a) pérdida informada **entre 0,8 % y 1,2 %**; b) desorden detectado y duplicados sin contar como recibidos; c) se guarda todo lo que llegó; d) la reproducción genera ≥ 5 cuadros del panel desde el archivo |
| **T5** | Reglas de Firebase en el emulador | `py pruebas\t5_reglas.py` (envuelve `npx firebase emulators:exec … node pruebas/reglas.test.mjs` en `C:\aura\firebase`). Requiere instalar `firebase-tools` y `@firebase/rules-unit-testing` (**pendiente de autorización**) | Los 39 casos de la matriz (abajo) dan el resultado esperado |

### Matriz de reglas (T5 en el emulador y D6 en el proyecto real)

UID de prueba: "usuario" (tú), "placa" (dispositivo), "otro" (cualquier otra cuenta), "sin auth".

| # | Quién | Operación | Esperado |
|---|---|---|---|
| 1–6 | sin auth | leer `/sensores/hab1`, `/crudo/hab1`, `/comandos/hab1`, la raíz; escribir `/sensores/hab1/estado`, `/comandos/hab1/x` | DENEGADO |
| 7–9 | placa | escribir `/sensores/hab1/estado`, `latido`, `comando` (estructura válida) | PERMITIDO |
| 10 | placa | escribir `/crudo/hab1/<13 dígitos>` (bloque válido) | PERMITIDO |
| 11 | placa | leer `/comandos/hab1` | PERMITIDO |
| 12 | placa | escribir `/comandos/hab1/x` | DENEGADO |
| 13 | placa | leer `/sensores/hab1` | DENEGADO |
| 14–15 | usuario | leer `/sensores/hab1` y `/crudo/hab1` | PERMITIDO |
| 16 | usuario | escribir `/comandos/hab1/x` (comando válido, `t` = hora del servidor) | PERMITIDO |
| 17–18 | usuario | escribir `/sensores/hab1/estado`; escribir datos en `/crudo/hab1/<bloque>` | DENEGADO |
| 19 | usuario | leer `/comandos/hab1` | DENEGADO |
| 20 | usuario | borrar un bloque `/crudo/hab1/<bloque>` | PERMITIDO |
| 21 | usuario | borrar `/crudo/hab1` completo | DENEGADO |
| 22 | usuario | borrar `/comandos/hab1/x` | PERMITIDO |
| 23–24 | otro | leer `/sensores`; escribir `/comandos` | DENEGADO |
| 25–29 | placa | estado con campo extra / valor no permitido / sin campo obligatorio; bloque con `jit` de 5.000 caracteres; bloque con clave no numérica | DENEGADO (.validate) |
| 30–32 | usuario | comando no permitido (`FORMAT_FLASH`); `t` distinto de la hora del servidor; campo extra | DENEGADO (.validate) |
| 33–34 | placa | latido con versión de 40 caracteres; id de sensor inválido | DENEGADO (.validate) |
| 35 | usuario | comando `SET_CFG AP motion_sensitivity=0.4` | PERMITIDO |
| 36 | placa | estado con `entrenada:false` y `presencia:"vacia"` | DENEGADO |
| 37 | placa | estado con `entrenada:false` y `presencia:"no_disponible"` | PERMITIDO |
| 38 | placa | estado `VACIA` con `entrenada:false` | DENEGADO |
| 39 | placa | `presencia` con un valor no permitido | DENEGADO |

Si el emulador no se autoriza, la misma matriz puede probarse a mano en la consola: Realtime Database →
Reglas → **Simulador** (tipo de operación, ruta, "Autenticado" con proveedor personalizado y el UID).

---

## Con la placa

Requisitos: `aura_nodo` grabado, credenciales en NVS, cuentas de usuario y de dispositivo en Firebase,
reglas publicadas. El PC y la placa en la misma red para las pruebas locales.

| Id | Qué se prueba | Procedimiento (script) | Criterio de aprobación | Duración |
|---|---|---|---|---|
| **D0** | **Prueba de humo (obligatoria para TODO firmware nuevo, antes de cualquier otra prueba)** | `pruebas\d00_humo.py --puerto COMx --id-sesion D0_<ver> --version <ver>`: escucha el USB **sin enviar órdenes de reinicio** 150 s (tras grabar o reconectar el USB); también analiza una captura con `--archivo` | a) **arranca**: llega `arranque` o `telemetria` con la versión esperada; b) **no se reinicia en 2 min**: `encendido_s` crece sin volver atrás y cubre ≥ 120 s, un solo `arranque`, sin líneas de pánico/assert/`rst:` ni reconexiones del puerto; c) **reporta memoria**: telemetría con `heap_libre` y `heap_minimo`. Observaciones sin efecto en el resultado: pila mínima por tarea y líneas `HMS:` vacías. Si falla, no se ejecuta ninguna otra prueba con ese firmware | 3 min |
| **D1** | Arranque y credenciales | `pruebas\d01_arranque.py --puerto COMx`: captura USB 3 min con reinicio, más vía local 2 min; luego pide (sin eco) cada secreto y busca, en ambas capturas, el valor, su hexadecimal y su base64 | La placa conecta a WiFi (IP), envía HMS y telemetría; **0 secretos** en las capturas | 10 min |
| **D2** | Sin degradación | `pruebas\d02_degradacion.py --ip …`: 10 min por vía local con nube y USB activos; usa la telemetría de la placa (ventanas de 10 s calculadas a bordo, sin efecto de la pérdida local) | **Mediana de las medianas por ventana ≤ 62 ms** y **percentil 95 de los p95 por ventana ≤ 65 ms**; mediana de `hms_por_s` ≥ 90 % de 16,3/s (S001, un canal) = 14,7/s | 12 min |
| **D11** | Formato del CSI crudo de 16 bits (LLTF del C5) con datos reales | `pruebas\d11_formato_csi.py --ip …`: 2 min de paquetes `csi` por la vía local | a) `raw_len`/`valid_len` constantes por formato y = total de la tabla de IDF (o su doble); b) conjunto de posiciones siempre nulas estable (≥ 95 %); c) `valid` = redondeo(`raw` extendido a 12 bits en los rangos de esp-radar × `comp`) con \|error\| ≤ 1 en ≥ 99 %; d) `agc`, `fft` y `comp` en el 100 % de los paquetes; e) orden Re/Im: **informativo** (no distinguible con una sola placa; IDF documenta Im, Re) | 3 min |
| **D3** | Duración sin PC por USB (cargador) | Placa con cargador; `pruebas\d03_duracion.py --ip … --horas 2.1` graba la vía local y consulta `/sensores/hab1` cada 60 s con tu cuenta | **0 reinicios** (encendido_s creciente, motivo sin cambios); heap mínimo ≥ **40 KB**; ≥ 1 renovación de token (`renov` ≥ 1 tras pasar 60 min); `/sensores` sin cortes (latido sin huecos > 2 min) | 2 h 10 min |
| **D4** | Vía local 30 min | `receptor_local.py --id-sesion D4 --duracion 1800` | Pérdida **< 1 %** por número de secuencia | 31 min |
| **D5** | Vía nube: estado y comandos | `pruebas\d05_nube.py`: verifica estado y latido en `/sensores/hab1`; escribe 10 comandos `GET_CFG AP` en `/comandos/hab1` y mide hasta la confirmación en `/sensores/hab1/comando` | Estado y latido presentes; **presencia** ∈ {no_disponible, vacia, presente}, `no_disponible` si no está entrenada y nunca VACIA/PRESENCIA_QUIETA sin entrenar (D5c); las **10** confirmaciones en ≤ intervalo de consulta (5 s) **+ 3 s = 8 s** | 5 min |
| **D6** | Reglas reales | `pruebas\d06_reglas_reales.py`: la matriz de T5 por REST contra `aura-csi` con sensor `prueba` (no toca `hab1`) y limpieza al final | Todos los casos con el resultado esperado | 5 min |
| **D7r** | Comandos de simulación sin clave | `pruebas\d07_resiliencia.py --caso r --ip … [--puerto COMx]`: `SIM_SIN_INTERNET` y `SIM_PIERDE_PRINCIPAL` firmados con una clave falsa (y por USB) | Los dos vuelven `RECHAZADO` (autenticación fallida; por USB "solo por la vía local autenticada"), `cmd_rechazados` sube y ninguna simulación se activa | 2 min |
| **D7a-sim** | Corte de internet **simulado** 5 min | `--caso a-sim --ip …`: `SIM_SIN_INTERNET 300` (la placa bloquea solo sus conexiones a Firebase; WiFi, vía local y SNTP siguen) | Vía local sin pérdidas significativas (< 1 %); 0 reinicios; durante el corte la nube no está `operando` y `nube_espera_s` crece (5, 10, 20…); al terminar vuelve sola a `operando` y escribe. **Es una simulación: prueba la lógica de recuperación de la placa, no una caída real de la red** | 12 min |
| **D7b** | Apagar el receptor de la PC | `--caso b`: se detiene el receptor 3 min | La nube sigue escribiendo latidos (sin huecos > 2 min) | 6 min |
| **D7c-sim** | Caída **simulada** de la red principal | Hotspot encendido; `--caso c-sim --ip …` (pide tu cuenta): `SIM_PIERDE_PRINCIPAL 600`. Se mide **desde la nube** (sondeo cada 5 s) | Reconecta por el hotspot (se informa el tiempo hasta la 1.ª escritura en la nube); latido con `red=respaldo`; presencia `no_disponible`; no vuelve a la principal antes de 600 s; **vuelve sola** en el primer reintento (cada 15 min, `CONFIG_AURA_REINTENTO_PRINCIPAL_MIN`), a más tardar 15 + 2 min después de pasar al respaldo; 0 reinicios. **Simulación** (ver D7a-sim) | 20 min |
| **D7a-real** | **Opcional**: corte real de internet | `--caso a-real --ip …` en el horario que elijas: desconectar el cable **coaxial** del router 5 min (la casa queda ~10 min sin internet por la resincronización del módem) | Mismos criterios que D7a-sim | 16 min |
| **D8a** | OTA correcta | `ota_local.py --ip … build\aura_nodo.bin` | Respuesta `OK`; arranca la nueva imagen y se valida (`fase: validada`) **solo después** de la autoprueba: ≥ 30 s desde el arranque y 10 s seguidos con IP, detector recibiendo CSI, todas las tareas propias vivas y heap libre ≥ 16 KB (el mensaje informa `ventana_s` y `heap_min_ventana`) | 5 min |
| **D8b** | OTA con clave incorrecta | `ota_local.py … --clave-erronea` | `ERROR autenticacion`; la placa sigue con su versión | 2 min |
| **D8c** | OTA con imagen corrupta | `ota_local.py … --corromper` | `ERROR sha256`; no se activa | 3 min |
| **D8d** | Vuelta atrás | Compilar con `CONFIG_AURA_PRUEBA_ROLLBACK=y` en otra carpeta de compilación, enviar por OTA | La imagen de prueba no se valida, se reinicia a los 30 s y **la placa vuelve sola a la versión anterior** | 10 min |
| **D9** | Buffers WiFi con carga | `pruebas\d09_carga.py --ip …` 10 min con tráfico en la red (video o iperf en otro equipo) | Se registran el heap mínimo y el intervalo de `ts_ms`. Si heap mínimo < **50 KB**: repetir con 64 buffers (OTA) y comparar en tabla. **La decisión se toma con esos datos** | 15–30 min |
| **D10** | Sincronía SNTP | `pruebas\d10_sntp.py --ip …`: 50 intercambios "TIEMPO" (estilo NTP) | Desfase placa–PC **< 100 ms** (requiere el reloj de Windows sincronizado) | 2 min |

### Orden recomendado

**D0** (con cada firmware nuevo, incluidas las imágenes enviadas por OTA) → carga de credenciales → D1 → D10 → D2 → **D11** → D5 → D6 → D4 → D7b → D7r → D7a-sim → D7c-sim → D8b → D8c → D8a → D8d → D9 → D3 (en la noche). D7a-real es opcional, en el horario que elijas. Las pruebas formales D1–D11 se ejecutan con la 0.1.2 (o la versión que se decida tras el ajuste de memoria).

**Regla de parada (23/10):** si **D2** o **D9** fallan, se detiene la secuencia y se informa antes de seguir.

**Pilas (tras D1 y D3):** `py pruebas\pilas_propuesta.py ..\..\datos\crudos\D1_usb.csv ..\..\datos\crudos\D3_local.csv` propone tamaños con un 25 % de margen sobre el máximo medido (mensajes `pilas` cada 60 s). Solo propone; los cambios se aprueban antes de aplicarlos.
Motivo: primero lo que valida el arranque y la hora (base de las demás), luego las vías, después las
pruebas que cortan la red, la OTA y, al final, las de larga duración.
