# Sesión 2026-10-26 — Red AURA-LAB: capturar sin PC con router propio y el celular como receptor

- **Equipo:** PC principal (`DESKTOP-7O57OU0`, usuario `usuario`), ruta `C:\aura`, Claude Code.
- **Commit al inicio:** `66aec28`. El commit final se consulta con `git log`.
- **Restricción de la fase:** no se graba firmware ni se cambian credenciales.

## Objetivo
Preparar la captura sin PC: router Huawei B315s-519, red `AURA-LAB` (2,4 GHz, sin internet), celular como receptor.

## Qué se hizo
- Lectura del firmware de trabajo (`firmware/aura_nodo/main/`, idéntico a `firmware/versiones/0.1.3/main/` según
  `diff -rq`), de `analisis/receptor_local.py`, `analisis/aura_proto.py` y `analisis/visor.py` (las copias de
  `kit_captura/scripts/` son idénticas).
- Medición con `datos/crudos/S002_local.csv` (script temporal en la carpeta temporal del sistema, fuera del repo).
- Creados `docs/red_aura.md` y ADR-0023 (Propuesta); línea en `INDICE.md` y en la bitácora.

## Respuestas

**1. ¿La recepción necesita `local_key`?** No (leído en el código).
- `SUB`/`UNSUB`/`TIEMPO` se atienden sin autenticar: `firmware/aura_nodo/main/aura_local.c:228-236`.
- Solo `CMD` (`aura_local.c:255`) y la OTA (`aura_ota.c:73`) autentican; `autenticar` es lo único que lee
  `local_key` (`aura_comandos.c:302`).
- `receptor_local.py` solo importa puertos y lectores (`analisis/receptor_local.py:24`); `leer_clave_local`
  (`aura_proto.py:61-67`) la usan `comando_local.py:61`, `ota_local.py:50`, `prueba_hotspot.py:47` y las pruebas D7/D8.
- Conclusión: el celular no lleva la clave. Pierde `CMD` y OTA en el lugar. `AURA REBOOT` ya era solo por USB
  (`aura_comandos.c:164`; `REBOOT` no está en `PERMITIDOS`, `aura_comandos.c:42-44`).

**2. Dependencias de SNTP.**
- Firmware: SNTP con `time.google.com` y `pool.ntp.org` (`aura_tiempo.c:25`); sin hora, `aura_tiempo_unix_us()`
  devuelve 0 (`aura_tiempo.c:52-54`). Efectos: `t_us` = 0 en la cabecera A1 (`aura_local.c:170-172`) y en el CSI
  (`aura_sensing.c:90`); `TIEMPO` responde 0 y `sntp_ok`=0 (`aura_local.c:234-235`); los comandos solo exigen contador
  creciente (la ventana de ±120 s se salta, `aura_comandos.c:321-328`); la nube espera hora (`aura_nube.c:556-561`,
  sin efecto en modo solo local). El CSI no depende de internet: sale del ping al router (`aura_sensing.c:169`).
  La placa no toma NTP del DHCP (`firmware/versiones/0.1.3/sdkconfig.usado:1965`).
- `receptor_local.py`: no depende de SNTP. Marca cada línea con la hora del receptor (`receptor_local.py:141-143`) y
  la pérdida usa la secuencia (`receptor_local.py:149`).
- `visor.py --reproducir`: con `t_us` = 0 usa `t_pc_unix` (`visor.py:196` y `visor.py:60`); ordena por hora y luego
  por secuencia (`visor.py:200`). Los nombres de los PNG llevan esa hora (`visor.py:216`), o sea, la del celular.
- **Medido** (S002, 72 672 datagramas A1, receptor = PC): orden idéntico con `t_us` y con `t_pc_unix` (0,00 % de
  posiciones distintas); desfase constante t_pc − t_us = −1,127 s (p5 −1,144; p95 −1,124); fluctuación respecto al
  desfase: p50 4,8 ms, p95 16,4 ms, p99 16,9 ms; 26,5 % de los datagramas comparte la hora con el anterior (envío en
  lotes, `aura_local.c:353`); duración igual (618,2 s). Reproducción de los primeros 30 s con `t_us` forzado a 0:
  3 532 datagramas, 30 cuadros, sin error, panel correcto (revisado un cuadro).
- **No verificado:** la fluctuación con el celular por WiFi como receptor; archivos que mezclan `t_us` = 0 y > 0.

**3. ¿`receptor_local.py` funciona fuera de Windows?** Por diseño sí; **no verificado** en Linux/Android.
- Rutas relativas a `RAIZ` (`receptor_local.py:26-27`), crea `datos/crudos` (`receptor_local.py:189`). Las
  menciones a `C:\aura` son solo de la ayuda (`receptor_local.py:5`, `:12`).
- Sockets UDP estándar; `SO_REUSEADDR` + `bind` al 45455 (`receptor_local.py:84-85`). `ConnectionResetError`
  (`:137-140`) es de Windows y no estorba en otros sistemas. `SO_RCVBUF` de 4 MB (`:111`): en Linux/Android el núcleo
  lo recorta en silencio a su máximo (inferido).
- Dependencias: biblioteca estándar + numpy, que entra por `aura_proto.py:20` aunque el receptor no lo use. Python
  3.10+ por `dict | None` (`receptor_local.py:82`, `aura_proto.py:37`).
- El broadcast de anuncios puede no llegar a Android con la pantalla apagada (inferido): usar `--ip` y `--sin-bind`
  con la IP reservada de la placa.

## Segunda parte (después del commit f6dd354)

**Reinicios en `receptor_local.py`.** Desorden medido en el orden de llegada (F1, S002, PV; 110 376 datagramas,
receptor en la PC): **0** llegadas por debajo del máximo ya visto. Propuesta aplicada: `VENTANA_DESORDEN = 1000`
(≈ 8,5 s a 117,6 datagramas/s; ≈ 15 lotes de 64 del firmware). Primera versión (caída > 1000 = reinicio): T4a y T4b
**FALLIDAS**: el simulador de T4 manda al final 10 duplicados de toda la sesión, que "caen" más de 1000. No se cambió
la prueba; se exige además confirmación sostenida (`CONFIRMAR_REINICIO = 20` datagramas seguidos por debajo de la
ventana y dentro de un rango < 1000). Resultados: prueba sintética 8/8 (solo demuestra que el código corre); T4a–d
APROBADAS; resumen de F1, S002 y PV idéntico al de la versión anterior (medido). Límite: un reinicio antes de ~1000
datagramas no se detecta.

**`visor.py --reproducir`.** Por decisión de Deisy, `t_pc_unix` por defecto para cualquier archivo; `--hora-placa`
con validación (todo `t_us` > 0, no decreciente, |desfase − mediana| ≤ 1 s) y aviso si se rechaza. S002 (medido):
con `--hora-placa`, 61/61 PNG idénticos byte a byte al visor anterior en 30 s; por defecto, 6 183 cuadros como antes y
la misma secuencia de 22 cambios de estado, desplazada −1,14 s (mediana; −1,140 a −1,040). Conteo de cuadros por
estado: MOVIMIENTO 10 frente a 9 y SIN_MOVIMIENTO 6 147 frente a 6 148, por el redondeo a la rejilla de 0,1 s.
Rechazo comprobado en 4 variantes de S002 (mezcla de 0 y > 0, todo 0, retroceso, salto de 5 s).

Copias temporales de S002 creadas para estas pruebas: borradas.

## Tercera parte (después de los commits 8d0b8bf y 266000a)

**Telemetría y reinicios (solo revisión).** No hay contador de arranques. Por la vía local llegan `sample.ts_ms`
(milisegundos desde el arranque, `esp_timer`, `firmware/aura_nodo/main/web_serial_monitor.c:271`; ~17/s en S002) y
`telemetria` cada 10 s con `encendido_s` y `motivo_reinicio` (`aura_telemetria.c:182-183`, `:213-214`). El mensaje
`arranque` (`app_main.c:51`) se emite antes de que haya suscriptores y no llega al receptor (inferido del código,
`aura_local.c:166`). Propuesta, no implementada: en el receptor, reinicio = `ts_ms` de una muestra menor que el de
la anterior; detecta reinicios a cualquier edad (también en bucle) y sin SNTP; la regla de la secuencia queda como
respaldo.

**Relojes en la evaluación (solo revisión).** `evaluar_deteccion.py` lee la captura USB (`S002.csv`) y usa
`t_pc_unix − t_pc_unix de la primera línea` (`evaluar_deteccion.py:63-77`); no usa `t_us` ni `ts_ms`. Las etiquetas
de `sesion_programada.py` son horas de la misma PC (`time.time()`, `:62-63`, `:78`, `:147-151`). Mismo reloj: **sin
sesgo por mezcla y sin recálculo por esa causa**. Lo que queda es el retraso de llegada, medido en S002 entre WiFi y USB
para la misma muestra: mediana +2,6 ms (p5 −7,0; p95 +6,7 ms). `latencias_S002.csv` (24/10 01:18) se calculó con las
etiquetas del plan anulado (`S002_etiquetas_plan_no_seguido.csv`); al reetiquetar (01:21) no se sobrescribió porque no
hay cambios de condición (`evaluar_deteccion.py:271`). Está obsoleto y ningún documento lo cita.

**Fase 1 de `kit_movil/`.** Versión 0.1.0: copias exactas de `receptor_local.py`, `aura_proto.py` y del nuevo
`analisis/verificar_captura.py`, con `LEEME.md`, `CAMBIOS.md` y `VERSION`. Probado en la PC: el verificador con S002
y F1 (cumplen); el receptor del kit con una placa simulada (2 500 datagramas con `t_us` = 0, un hueco de 6 s y un
reinicio): 2 épocas, 0 pérdida, hueco marcado FALLIDO. Prueba sintética: solo demuestra que corre. No verificado en
Android. `.gitignore` ahora excluye `kit_captura/datos/` y `kit_movil/datos/`.

## Cuarta parte (configuración final, criterios y reinicios por ts_ms)

- `docs/red_aura.md`: WPA2-PSK; sin reserva DHCP (IP de B en la lista de conectados antes de cada sesión);
  aislamiento de clientes a comprobar en la prueba.
- `docs/ensayos/kit_movil_criterios.md` (nuevo, fuente única; commit `57a3349` antes de la prueba): pérdida ≤ 2 %
  (antes < 1 %, cambio de Deisy antes de la prueba), 0 huecos > 5 s, mediana de CSI/s en ventanas de 10 s ≥ 80 % de
  S002 = 80,32/s (S002 = 100,40/s, medido con el verificador).
- `receptor_local.py`: reinicios por `ts_ms` (aprobado), respaldo por secuencia. T4: FALLIDA con la primera versión,
  APROBADA tras corregir. Sintéticas 9/9 y 8/8 (solo demuestran que el código corre).
- `verificar_captura.py`: lee los criterios del documento; informa `motivo_reinicio` y `encendido_s`.
- Borrado `datos/procesados/latencias_S002.csv` (obsoleto).

## Pruebas
- T4 (receptor simulado): primera ejecución con el cambio: T4a, T4b **FALLIDAS**, T4c, T4d APROBADAS; tras la
  corrección: T4a–d **APROBADAS** (`docs/resultados_pruebas.md`).
- Mediciones informativas con S002, sin criterio de aceptación.

## ADR creados o modificados
- Nuevo: ADR-0023 (Propuesta); ampliada en la segunda parte (consecuencias de seguridad, reinicio y visor);
  **Aceptada por Deisy el 2026-10-26** (quinta parte).

## Pendientes y riesgos
- Deisy dicta la configuración del router (IP, DHCP, canal, modo, seguridad, aislamiento, reservas) para completar
  `docs/red_aura.md`.
- Prueba con el celular en AURA-LAB (criterio de `docs/guia_salon.md:95`).
- `kit_captura/scripts/receptor_local.py` y `visor.py` siguen con la versión anterior y **no se actualizan antes del
  video del 30/10/2026** (decisión de Deisy). Después: **generar ambos kits (`kit_captura/` y `kit_movil/`) desde
  `analisis/` con un script**, en vez de copias a mano.
- Criterio agregado antes de la prueba del kit móvil: 0 huecos mayores de 5 s por placa (`docs/guia_salon.md:95-97`).
- `kit_movil/` probado solo en la PC; la primera captura en el celular es su prueba.
- La referencia de tasa (S002) se tomó con el router de casa; en AURA-LAB la tasa depende de la respuesta al ping del
  B315s (no verificado).
- Fase 2 (cargar wifi1 = AURA-LAB en B): pendiente de la confirmación de Deisy.
- ADR-0022 (respaldo del repositorio) sigue pendiente; esta ADR toma el número 0023.
