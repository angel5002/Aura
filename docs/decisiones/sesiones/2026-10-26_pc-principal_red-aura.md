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

## Pruebas
- Ninguna prueba del plan (T/D) ejecutada. Medición informativa con S002, sin criterio de aceptación.

## ADR creados o modificados
- Nuevo: ADR-0023 (Propuesta).

## Pendientes y riesgos
- Deisy dicta la configuración del router (IP, DHCP, canal, modo, seguridad, aislamiento, reservas) para completar
  `docs/red_aura.md`.
- Prueba con el celular en AURA-LAB (criterio de `docs/guia_salon.md:95`).
- Observación: `receptor_local.py:42` solo abre una época nueva si la secuencia cae más de 1 000 000; un reinicio de
  la placa en una sesión corta queda como duplicados y desorden en el resumen de pérdida.
- ADR-0022 (respaldo del repositorio) sigue pendiente; esta ADR toma el número 0023.
