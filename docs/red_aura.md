# Red AURA-LAB: router propio aislado para capturar sin PC

Decisión asociada: [ADR-0023](decisiones/adr/ADR-0023-red-aura-aislada-router-propio.md) (**Propuesta**).
Creado el 2026-10-26 en la PC principal. **Este archivo no lleva contraseñas**: la del WiFi vive solo en la NVS de
la placa (`wifi1_pass`, cargada con `analisis/cargar_credenciales.py`) y en `secretos\` (fuera de git), y la de
administración del router solo la conoce Deisy.

Estado: los campos marcados **POR DICTAR** se completan cuando Deisy dicte la configuración. Nada de lo de abajo
está medido todavía en el router; lo marcado como "recomendado" es propuesta de Claude, no verificado.

## 1. Router

| Campo | Valor | Fuente / estado |
|---|---|---|
| Equipo | Huawei B315s-519 (router 4G LTE) | dictado por Deisy |
| Internet | **ninguno** (sin SIM ni WAN) | dictado por Deisy |
| IP del router (puerta de enlace) | **POR DICTAR** | no verificado |
| Máscara / rango DHCP | **POR DICTAR** | no verificado |
| Usuario/contraseña de administración | no se registra aquí | Deisy |

## 2. WiFi (wifi1 de la placa)

| Campo | Valor | Fuente / estado |
|---|---|---|
| SSID | `AURA-LAB` | dictado por Deisy |
| Banda | 2,4 GHz (sin 5 GHz) | dictado por Deisy |
| Canal | **POR DICTAR** (recomendado: fijo, no "automático") | propuesta |
| Modo | **POR DICTAR** (recomendado: 802.11b/g/n, ancho 20 MHz) | propuesta |
| Seguridad | **POR DICTAR** (recomendado: WPA2-PSK con AES) | propuesta |
| Contraseña | no se registra aquí (NVS `wifi1_pass` y `secretos\`) | — |
| WPS | **desactivado** (por confirmar en el router) | Deisy, sección 7 |
| Aislamiento de clientes (AP isolation) | **desactivado** (por confirmar en el router) | Deisy, sección 7 y 4.a |

## 3. Reserva DHCP (IP fija por MAC)

| Dispositivo | MAC | IP reservada | Estado |
|---|---|---|---|
| Placa B (`hab1`, aura_nodo 0.1.3) | `3C:DC:75:8A:6F:CC` | **POR DICTAR** | MAC de CLAUDE.md, sección 2 |
| Celular receptor (Termux) | **POR DICTAR** (ver 4.d) | **POR DICTAR** | — |

## 4. Por qué cada ajuste (con referencia al código)

a. **Aislamiento de clientes desactivado.** El celular y la placa se hablan directo por UDP: el celular manda
   `SUB` al puerto 45454 y la placa le responde en unicast (`firmware/aura_nodo/main/aura_local.c:111`,
   `aura_local.c:228-229`). Si el router aísla a los clientes, no llega nada.
b. **Sin internet no importa para la vía local, pero no hay hora SNTP.** La placa pide hora a
   `time.google.com`/`pool.ntp.org` (`aura_tiempo.c:25`); sin internet `t_us` sale en 0 en cada datagrama
   (`aura_tiempo.c:52-54`, `aura_local.c:170-172`). El visor usa entonces la hora del celular (`t_pc_unix`), ver
   `decisiones/sesiones/2026-10-26_pc-principal_red-aura.md` (pregunta 2).
c. **El router debe responder al ping.** El CSI sale del ping que la placa hace al router
   (`aura_sensing.c:169`); es tráfico local, no necesita internet. No verificado en el B315s.
d. **IP fija de la placa.** En Android el anuncio por broadcast (UDP 45455) puede no llegar con la pantalla apagada
   (inferido, no verificado); con la IP reservada se usa `receptor_local.py --ip <IP> --sin-bind`
   (`analisis/receptor_local.py:182-186`). Para reservar la IP del celular hay que fijar en Android la MAC de esa
   red ("MAC del dispositivo" o la aleatoria persistente de esa red) antes de leerla.
e. **Seguridad WPA2.** La placa exige como mínimo WPA2-PSK si hay contraseña (`aura_wifi.c:87`). La vía local va
   **sin cifrar** (`aura_local.h:2`) y `SUB` no se autentica (`aura_local.c:228`): cualquiera dentro de AURA-LAB
   podría suscribirse (máximo 3 suscriptores, `firmware/versiones/0.1.3/sdkconfig.usado:731`). La contraseña del
   WiFi es la única barrera.
f. **Canal fijo.** Un cambio de canal del router obliga a la placa a reconectar; si falla 3 veces seguidas pasa a
   wifi2 (`aura_wifi.c:33`, `aura_wifi.c:202-209`) y el detector se recrea (`aura_wifi.c:5-7`).

## 5. wifi2 = hotspot del celular (respaldo)

- Solo se usa si AURA-LAB falla 3 veces seguidas (`aura_wifi.c:202`); la placa vuelve a AURA-LAB cuando la ve en un
  escaneo, cada 15 min (`firmware/versiones/0.1.3/sdkconfig.usado:739`, `aura_wifi.c:177-189`).
- Si la placa cae al hotspot, cambia de IP: `receptor_local.py` con `--ip` deja de recibir y hay que reiniciarlo con la
  IP nueva (el receptor no redescubre, `analisis/receptor_local.py:194-204`).
- Si el hotspot tiene datos móviles, la placa obtiene hora SNTP y desde ahí `t_us` deja de ser 0: un mismo archivo
  puede mezclar las dos bases de tiempo (inferido). Por eso, en las sesiones capturadas con el celular la referencia
  es siempre `t_pc_unix` (ADR-0023).
- El SSID y la contraseña del hotspot no se registran aquí (NVS `wifi2_ssid`/`wifi2_pass`).

## 6. Celular receptor (lo que lleva y lo que NO lleva)

- Lleva: Termux + `python` + `python-numpy`, y solo `receptor_local.py` y `aura_proto.py`
  (`docs/guia_salon.md:78`, `docs/guia_salon.md:93-96`).
- **No lleva** la clave local (`secretos\clave_local.txt`) ni ningún otro archivo de `secretos\`: la recepción no la
  usa (ver ADR-0023). Sin la clave, desde el celular no se pueden enviar comandos `CMD` ni hacer OTA.
- Ajustes de Android recomendados (inferidos, no verificados): mantener la conexión a una red sin internet (no
  cambiar a datos móviles), excluir Termux de la optimización de batería y usar `termux-wake-lock`.

## 7. Seguridad del router y de la red

Motivo: la recepción por `SUB` no se autentica (`firmware/aura_nodo/main/aura_local.c:228`) y va sin cifrar
(`aura_local.h:2`); quien entre a AURA-LAB puede recibir el CSI crudo (ADR-0023).

- [ ] **Tras el reset de fábrica, cambiar la contraseña del panel de administración** del router. La elige y guarda
      Deisy; no se escribe en este repositorio.
- [ ] **Tras el reset, cambiar la clave WiFi** de AURA-LAB (no dejar la de fábrica). Va solo a la NVS de la placa
      (`wifi1_pass`) y a `secretos\`.
- [ ] **WPS desactivado** (permite entrar a la red sin la clave, con el botón o un PIN).
- [ ] **Aislamiento de clientes (AP isolation) desactivado**: es necesario para que el celular y la placa se hablen
      (sección 4.a). No es una medida de seguridad sino un requisito; la protección la da la clave WiFi.
- [ ] **La clave WiFi de AURA-LAB no se comparte con alumnos ni con el público.**
- [ ] **No publicar la etiqueta del router** (fotos, videos, diapositivas, repositorio): suele traer la clave WiFi y
      la del panel de fábrica, además de identificadores del equipo.
- En este repositorio **no se registran** el IMEI, el número de serie ni ningún otro identificador de la etiqueta
  del router.

## 8. Pendiente

- [ ] Deisy dicta IP del router, rango DHCP, canal, modo, seguridad, WPS, aislamiento e IPs reservadas.
- [ ] Prueba en la red: anuncio visible, `SUB` con `--ip`, tasa `csi` y pérdida (criterio de `docs/guia_salon.md:95`).
- [ ] Cargar `wifi1` = AURA-LAB en la NVS de la placa B (fase posterior; en esta fase **no** se cambian credenciales).
