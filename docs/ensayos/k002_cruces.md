# K002: prueba de cruces del enlace placa B – Huawei (5 min, 10 cruces)

Fijada **antes de ejecutarla** (commit antes de la primera ejecución). **Criterio de detección: PROPUESTO por Claude el
27/10/2026, pendiente de aprobación de Deisy**; si lo cambia, se cambia aquí y en `analisis/pruebas/k002_cruces.py`
antes de ejecutar, con commit y una línea en la bitácora. Después no se cambia (regla 11 de `CLAUDE.md`).

Firmware: el que tenga la placa al ejecutarla (hoy 0.1.3, **sin** filtro de destino; ver ADR-0024). Un K002 con
0.1.5 sería otra prueba, no comparable.

## Montaje (el mismo de K001)

- Placa B en el cuarto con su cargador, a ~2 m del Huawei; Huawei en su sitio.
- Celular receptor quieto, con su cargador, **fuera** de la línea Huawei–B; Termux con `capturar.sh`.
- Una sola persona en el cuarto: la que cruza. Nadie más entra.
- Un cronómetro (otro teléfono o reloj) para seguir el horario.

## Horario (t = 0: al pulsar Enter en `capturar.sh`; se arranca el cronómetro a la vez)

| t (s) | Acción |
|---|---|
| 0 – 30 | Quieta, de pie, a ≥ 1 m de la línea Huawei–B (siempre en el mismo sitio) |
| **30, 55, 80, 105, 130, 155, 180, 205, 230, 255** | **Cruce:** caminar a paso normal atravesando la línea Huawei–B (2–3 s) y volver a quedarse quieta en el otro lado, a ≥ 1 m de la línea |
| 255 – 300 | Quieta hasta el final |

Los cruces alternan de lado (ida y vuelta). La captura dura 330 s para tener margen:

```
bash ~/kit_movil/scripts/capturar.sh K002 <IP_DE_LA_PLACA> 330
```

Después: `exportar.sh K002`, pasar a la PC (`adb pull` mientras no haya MTP), `verificar_export.py --copiar-a-crudos`
y evaluar:

```
python C:\aura\analisis\pruebas\k002_cruces.py C:\aura\datos\crudos\K002_local.csv
```

## Qué se evalúa

`motion_status` de las muestras del detector (sin la retención de 10 s del estado de la placa), con t = 0 en el primer
datagrama de la captura (reloj del celular). El primer datagrama llega ~1–2 s después del Enter: lo cubre la
tolerancia.

## Criterios (PROPUESTOS; pendientes de aprobación)

- **Validez:** captura ≥ 290 s, 0 huecos > 5 s y 0 reinicios de la placa. Si no: NO EJECUTADA (se repite).
- **Detección:** **≥ 8 de 10 cruces** con algún `motion_status = true` en **[t_k − 3 s, t_k + 8 s]**.
  - −3 s: diferencia entre el Enter, el cronómetro y el primer datagrama, más imprecisión humana.
  - +8 s: el cruce dura 2–3 s y la latencia observada antes fue < 1 s (0,83 s en S002, plan anulado); queda margen.
- **Falsas alarmas:** **≤ 5 %** del tiempo en MOVIMIENTO en las ventanas tranquilas: [5, 27] s, [t_k + 10, t_k+1 − 3] s
  entre cruces (12 s cada una) y [265, 290] s (155 s en total). Referencia: S002 con la sala vacía, 0,25 %.
- Resultado: APROBADA si se cumplen detección y falsas alarmas; FALLIDA si no (con la persona quieta en el cuarto, una
  falsa alarma alta también indica que el detector confunde presencia quieta con movimiento).

Se informa además (sin criterio): latencia del primer positivo de cada cruce y cruces detectados uno por uno.

## Prueba del script (no es la prueba K002)

27/10/2026, sin registrar resultados: S002 (sin cruces) → 0/10 detectados, 0,00 % en tranquilo; K000 (60 s) → NO
EJECUTADA; una captura sintética con 9 cruces con movimiento y 1,5 s de falsa alarma → 9/10 y 0,99 %. Solo demuestra
que el código corre.
