# ADR-0023: Red AURA aislada con router propio y receptor en el celular

- **Estado:** Aceptada (2026-10-26)
- **Fecha:** 2026-10-26
- **Decide:** Deisy (aceptada el 2026-10-26; redacción y análisis de Claude)
- **Equipo donde se tomó:** PC principal (`DESKTOP-7O57OU0`, `C:\aura`)
- **Relacionadas:** ADR-0005 (dos vías), ADR-0007 (secretos en NVS), ADR-0010 (0.1.3 solo local), ADR-0013 (kit
  portátil), ADR-0018 (presencia no disponible)

## Contexto
Hoy cada captura depende de una laptop y de la red del lugar o del hotspot del celular de Deisy
(`docs/decisiones/0000_reporte_inicial.md:19`). La red de casa tuvo tormentas de broadcast de otra PC
(`docs/resultados_pruebas_observaciones.md`) y las redes ajenas pueden aislar clientes o pedir firewall de
administrador. Se quiere capturar **sin PC**: placa B (aura_nodo 0.1.3), un router propio Huawei B315s-519 con la red
`AURA-LAB` (2,4 GHz, sin internet) y el celular con Termux + `receptor_local.py` como receptor
(`docs/guia_salon.md:78`).

Análisis del código (2026-10-26, sesión `docs/decisiones/sesiones/2026-10-26_pc-principal_red-aura.md`):
1. **La recepción no usa `local_key`.** `SUB`, `UNSUB` y `TIEMPO` se atienden sin autenticación
   (`firmware/aura_nodo/main/aura_local.c:228-236`); solo `CMD` (`aura_local.c:255`) y la OTA
   (`aura_ota.c:73`) llaman a `autenticar`, que es lo único que lee `local_key` (`aura_comandos.c:302`).
   `receptor_local.py` solo importa puertos y lectores (`analisis/receptor_local.py:24`); la clave solo la leen
   `comando_local.py`, `ota_local.py`, `prueba_hotspot.py` y las pruebas D7/D8.
2. **Sin internet no hay SNTP** (`aura_tiempo.c:25`) y `t_us` vale 0 en todos los datagramas
   (`aura_tiempo.c:52-54`, `aura_local.c:170-172`). El visor reproduce con `t_pc_unix` cuando `t_us` es 0
   (`analisis/visor.py:196`, `visor.py:60`). Medido con `datos/crudos/S002_local.csv` (72 672 datagramas, receptor en
   la PC): mismo orden que con `t_us` (0,00 % de posiciones distintas), desfase constante de −1,127 s entre los dos
   relojes y fluctuación de la llegada de 4,8 ms (p50) / 16,4 ms (p95); el 26,5 % de los datagramas comparte la
   hora de llegada con el anterior porque la placa los envía en lotes (`aura_local.c:353`). Reproducción de 30 s con
   `t_us` forzado a 0: 3 532 datagramas y 30 cuadros sin error.
3. **`receptor_local.py` es portable por diseño** (rutas relativas a `RAIZ`, `analisis/receptor_local.py:26-27`;
   sockets UDP estándar; solo numpy como dependencia externa, `analisis/aura_proto.py:20`; Python 3.10+ por las
   anotaciones `dict | None`, `receptor_local.py:82`). **No verificado** fuera de Windows.

## Decisión
Propuesta: usar una red aislada propia, `AURA-LAB`, en el router Huawei B315s-519 sin internet, como **wifi1**
(principal) de la placa; el **hotspot del celular** queda como **wifi2** (respaldo); y el **celular**, conectado a
AURA-LAB, es el receptor de la vía local con Termux + `receptor_local.py` + `aura_proto.py`, **sin la clave local**.
La configuración del router se documenta en `docs/red_aura.md`, sin contraseñas.

## Alternativas consideradas
| Alternativa | Por qué no |
|---|---|
| Seguir con la red del lugar (casa, colegio) | Tormentas de broadcast medidas en casa; redes ajenas pueden aislar clientes, cambiar de canal o exigir firewall de administrador. No es reproducible. |
| Solo el hotspot del celular (opción 3 de `docs/guia_salon.md:79`) | El celular hace de router y de receptor a la vez; su tráfico y su posición cambian el canal medido; con datos móviles mezcla la hora SNTP. Queda como respaldo. |
| Laptop como receptor (kit, ADR-0013) | Es justo lo que se quiere evitar: depende de la laptop prestada. Sigue siendo el plan B. |
| Celular con la clave local para mandar comandos | La recepción no la necesita; llevarla al celular amplía la superficie de ataque sin beneficio (los comandos de entrenamiento no sirven mientras la presencia no esté disponible, ADR-0018). |
| USB OTG + terminal serie en el celular (opción 1) | Sin CSI crudo (solo HMS) y app no verificada con el VID 303A (`docs/guia_salon.md:85-88`). |

## Consecuencias
- Mejora: red controlada y reproducible (canal fijo, sin tráfico ajeno, IP reservada de la placa); no hace falta PC
  ni firewall de Windows en el lugar.
- Mejora: el celular no guarda secretos del proyecto; la recepción solo necesita la contraseña de AURA-LAB.
- Limita: **sin hora SNTP** en la placa. **En las sesiones capturadas con el celular, la referencia de tiempo es
  siempre `t_pc_unix`** (reloj del celular al recibir), aunque algún datagrama traiga `t_us` > 0; así no se mezclan
  dos relojes en un mismo archivo. Tiene fluctuación de llegada (medida en PC: p95 16,4 ms; en el celular por
  WiFi: no medida). Para alinear con video, el video debe referirse al mismo reloj (p. ej., grabado o sincronizado
  con el mismo celular).
- Limita: sin la clave en el celular no hay `CMD` (`RESET_BASELINE`, `TRAIN_*`, `SET_CFG`, `GET_CFG`,
  `aura_comandos.c:42-44`) ni OTA en el lugar.
- Limita: **sin PC no hay `AURA REBOOT`**, que solo se acepta por USB (`aura_comandos.c:164`; `REBOOT` no está en
  `PERMITIDOS`). En el lugar la placa se reinicia **desenchufándola** (excepción a la regla 14 de CLAUDE.md, que
  supone una PC conectada).
- Riesgo: si la placa cae a wifi2 cambia de IP y el receptor con `--ip` deja de recibir (no redescubre,
  `analisis/receptor_local.py:194-204`); el detector se recrea al cambiar de red (`aura_wifi.c:5-7`).
- Riesgo: si el hotspot tiene datos móviles, la placa obtiene hora SNTP y un mismo archivo puede tener tramos con
  `t_us` = 0 (hora del celular) y tramos con `t_us` > 0 (hora de la placa), con un salto del orden del desfase entre
  relojes (−1,127 s medido en S002 entre placa y PC). Inferido, no verificado. Se evita usando siempre
  `t_pc_unix` como referencia (ver arriba).
- Riesgo: **la recepción por `SUB` no tiene autenticación** y la vía local va sin cifrar (`aura_local.h:2`,
  `aura_local.c:228`): cualquiera conectado a AURA-LAB puede suscribirse y recibir el CSI crudo. En AURA-LAB la
  contraseña WPA2 es la única barrera; por eso **la clave WiFi de AURA-LAB no se comparte con alumnos ni con el
  público** (ver `docs/red_aura.md`, sección de seguridad). Además, un intruso puede ocupar uno de los 3 cupos de
  suscriptor (`firmware/versiones/0.1.3/sdkconfig.usado:731`).
- Consecuencia en el visor (2026-10-26, pedida por Deisy): `visor.py --reproducir` usa **por defecto `t_pc_unix`
  para cualquier archivo** (no depende del nombre, del entorno ni de un cambio de formato). `--hora-placa` usa `t_us`
  solo si todo `t_us` > 0, no decrece en el orden del archivo y `t_pc_unix − t_us` no se aleja más de 1 s de su
  mediana (en S002 la mayor desviación fue 0,136 s); si no, avisa y usa `t_pc_unix`. Al empezar imprime la
  referencia usada y por qué. Comprobado con S002: con `--hora-placa`, 61/61 cuadros idénticos byte a byte al visor
  anterior; por defecto, los mismos 6 183 cuadros y los mismos 22 cambios de estado, desplazados −1,14 s (medido).
  Las ventanas `--desde`/`--hasta` y los nombres de los PNG quedan en la hora del receptor.
- Observación ajena a esta decisión, corregida el 2026-10-26 (bitácora): `receptor_local.py` solo detectaba el
  reinicio de la placa si la secuencia caía más de 1 000 000; ahora usa una ventana de desorden de 1000 datagramas
  con confirmación sostenida (20 datagramas). Afecta solo al resumen de pérdida, no al CSV ni al visor.
- Obliga a: completar `docs/red_aura.md` con lo que dicte Deisy; prueba en la red con el celular (criterios en
  `docs/ensayos/kit_movil_criterios.md`, fuente única que lee `verificar_captura.py`: pérdida < 1 %, 0 huecos
  mayores de 5 s por placa y mediana de CSI/s en ventanas de 10 s ≥ 80 % de la de S002 (100,40/s → 80,32/s);
  fijados por Deisy el 2026-10-26 antes de la prueba); en otra fase, cargar wifi1 = AURA-LAB en la NVS (sin grabar firmware).

## Evidencia
- Código: `firmware/aura_nodo/main/` = `firmware/versiones/0.1.3/main/` (`diff -rq` sin diferencias, 2026-10-26),
  commit al inicio `66aec28`.
- Medido: `datos/crudos/S002_local.csv` (fuera de git) con un script temporal; resultados en
  `docs/decisiones/sesiones/2026-10-26_pc-principal_red-aura.md`.
- No verificado: Termux en el celular con AURA-LAB; respuesta al ping del B315s; filtrado de broadcast en Android.

## Cómo revertir
Volver a la red del lugar o al hotspot como wifi1 (recargar credenciales por USB con `cargar_credenciales.py`) y
usar la laptop con el kit como receptor (ADR-0013). No requiere cambiar firmware.
