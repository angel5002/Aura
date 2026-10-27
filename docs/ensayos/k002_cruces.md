# K002: prueba de cruces del enlace placa B – Huawei (5 min, 10 cruces de ida y vuelta)

Fijada **antes de ejecutarla** (commit antes de la primera ejecución). Criterio de detección propuesto por Claude el
27/10/2026; montaje y criterio de falsas alarmas **definidos por Deisy el 27/10/2026** antes de ejecutar (por falta de
espacio del lado de la cama), con el mismo horario y la misma detección. Después de ejecutarla no se cambia (regla 11
de `CLAUDE.md`).

Firmware: el que tenga la placa al ejecutarla (hoy 0.1.3, **sin** filtro de destino; ver ADR-0024). Un K002 con
0.1.5 sería otra prueba, no comparable.

## Montaje

- Placa B en el cuarto con su cargador, a ~2 m del Huawei; Huawei en su sitio (el mismo de K001).
- **Celular** receptor sobre la cama, quieto, con su cargador, **a la misma altura que el Huawei y la placa** y a
  **1 m o más** de la línea Huawei–B; Termux con `capturar.sh`.
- Marcas en el suelo (cinta adhesiva), **frente a la mitad de la línea Huawei–B**:
  - **Punto 1**, en el lado libre, a **0,80 m** de la línea: ahí la persona espera **de pie y quieta** entre cruces.
  - **Marca de vuelta**, del lado de la cama, a **0,20 m** de la línea (1,00 m entre ambas marcas).
- Una sola persona en el cuarto: la que cruza. Nadie más entra.
- **Los cruces se guían por el semáforo** de `kit_movil/scripts/k002.sh` en la pantalla del celular (cambio del
  27/10/2026, decisión de Deisy, antes de ejecutar; antes: un cronómetro aparte). El horario y los criterios no cambian.
- La pantalla del celular debe seguir encendida toda la prueba: suspensión de pantalla mayor que 330 s (el
  wake-lock solo mantiene la CPU). Pitidos: `bell-character=beep` en `~/.termux/termux.properties`.

## Semáforo (`k002.sh`)

t = 0 es el `t_pc_unix` del **primer datagrama** de la captura (el mismo cero que usa `k002_cruces.py`; mismo reloj).

| Color | Cuándo | Qué hacer |
|---|---|---|
| **AZUL** + cuenta regresiva | desde el inicio, y 5 s después de cada horario | de pie y quieta en el Punto 1 |
| **AMARILLO** + 1 pitido | 3 s antes de cada horario | seguir quieta; prepararse |
| **ROJO** + 2 pitidos | 1 s antes de cada horario (30, 55, …, 255 s) hasta 5 s después | cruzar **ida y vuelta** por la mitad de la línea y volver al Punto 1 |
| **VERDE** + 3 pitidos | a los 300 s (fin del horario) | ya se puede mover; esperar el resumen de la captura |

## Horario (t = 0: primer datagrama de la captura; lo marca el semáforo)

| t (s) | Acción |
|---|---|
| 0 – 30 | De pie y **quieta** en el **Punto 1** |
| **30, 55, 80, 105, 130, 155, 180, 205, 230, 255** | **Cruce de ida y vuelta:** del Punto 1 a la marca de vuelta y de regreso al Punto 1, atravesando la línea **dos veces por su mitad** (~3 s); luego, de pie y quieta en el Punto 1 hasta el siguiente cruce |
| 255 – 300 | De pie y quieta en el Punto 1 hasta el final |

La captura dura 330 s para tener margen:

```
bash ~/kit_movil/scripts/k002.sh K002 <IP_DE_LA_PLACA> 330
```

(`k002.sh` lanza `receptor_local.py` en segundo plano, con su salida en `datos/crudos/K002_receptor.log`, y deja la
captura en `K002_local.csv` y su resumen, igual que `capturar.sh`.)

Después: `exportar.sh K002`, pasar a la PC (`adb pull` mientras no haya MTP), `verificar_export.py --copiar-a-crudos`
y evaluar:

```
python C:\aura\analisis\pruebas\k002_cruces.py C:\aura\datos\crudos\K002_local.csv
```

## Qué se evalúa

`motion_status` de las muestras del detector, con t = 0 en el primer datagrama de la captura (reloj del celular). El
primer datagrama llega ~1–2 s después del Enter: lo cubre la tolerancia.

`motion_status` es el estado del detector de esp_wifi_sensing (`firmware/aura_nodo/main/web_serial_monitor.c:288`),
**sin** la retención de 10 s del estado MOVIMIENTO de AURA (`aura_sensing.c:281`); solo mantiene ACTIVO 300 ms
(`ESP_WIFI_SENSING_ACTIVE_FILTER_MS`, `firmware/versiones/0.1.3/sdkconfig.usado:2453`) más la confirmación de salida
(< 1 s en total, inferido).

## Criterios

- **Validez:** captura ≥ 290 s, 0 huecos > 5 s y 0 reinicios de la placa. Si no: NO EJECUTADA (se repite).
- **Detección:** **≥ 8 de 10 cruces** con algún `motion_status = true` en **[t_k − 3 s, t_k + 8 s]**.
  - −3 s: imprecisión humana (con el semáforo, el cero es el primer datagrama: ya no hay desfase de cronómetro).
  - +8 s: la ida y vuelta dura ~3 s (hasta ~6 s si se arranca tarde) y la latencia observada antes fue < 1 s (0,83 s
    en S002, plan anulado); queda margen.
- **Persona quieta a 0,80 m del enlace:** **≤ 5 %** del tiempo en MOVIMIENTO (umbral de prototipo) en las ventanas
  tranquilas: [5, 27] s, [t_k + 10, t_k+1 − 3] s entre cruces (12 s cada una) y [265, 290] s, **155 s en total**. No se
  compara con S002 (allí la sala estaba vacía).
  - **Más exigente que lo previsto:** el plan anterior ponía a la persona a más de 1,5 m de la línea; a 0,80 m su
    cuerpo (respiración, pequeños movimientos) afecta más al enlace, así que es más probable que el detector marque
    MOVIMIENTO con la persona quieta. El umbral (≤ 5 %) no cambia.
  - Ventanas con la ida y vuelta (revisadas el 27/10, sin cambios): la persona vuelve al Punto 1 hacia t_k + 3 s
    (hasta ~t_k + 6 s si arranca tarde) y el detector se apaga en < 1 s; las ventanas empiezan en t_k + 10 s.
- Resultado: APROBADA si se cumplen detección y persona quieta a 0,80 m del enlace; FALLIDA si no.

Se informa además (sin criterio): latencia del primer positivo de cada cruce y cruces detectados uno por uno.

## Prueba del script (no es la prueba K002)

27/10/2026, sin registrar resultados: S002 (sin cruces) → 0/10 detectados, 0,00 % en tranquilo; K000 (60 s) → NO
EJECUTADA; una captura sintética con 9 cruces con movimiento y 1,5 s de falsa alarma → 9/10 y 0,99 %. Solo demuestra
que el código corre.
