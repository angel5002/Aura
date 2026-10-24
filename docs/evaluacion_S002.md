# Evaluación de la sesión S002 (24/10/2026, 01:12–01:17)

**Alcance (declarado):** una sola sesión, con orden fijo (vacía → caminando → sentada quieta), entrenamiento de
presencia de 20 s **justo antes** del tramo vacío (condición favorable para la presencia) y un **enlace corto de
0,8 m entre el router y la placa, con señal directa fuerte**. **No es una evaluación definitiva.** Firmware
aura_nodo 0.1.3 en modo solo local; 1 persona en la sala (madrugada); PC quieta junto a la placa.

Guiada a distancia con horas absolutas (`analisis\sesion_programada.py`): RESET_BASELINE 01:12:30 (STABLE a los
2,6 s), entrenamiento 01:13:10–01:13:30 (umbrales válidos: wander 0,0006, jitter 0,0182), vacía 01:13:45–01:14:45,
caminando 01:15:00–01:16:00 (ida y vuelta pasando cerca de placa y router), sentada quieta 01:16:10–01:17:10 a
~1 m. Transiciones marcadas "excluir". Datos: `S002.csv` (USB) y `S002_local.csv` (CSI crudo, 0,01 % de pérdida).
**Pendiente: confirmación de que la persona siguió el horario** (no hubo mensajes durante la sesión).

## Resultado (`evaluar_deteccion.py --sesiones S002`, rejilla 1 s, margen 5 s tras cada cambio)

| Detector | VP | FN | FP | VN | Sensibilidad | Especificidad | Latencia |
|---|---|---|---|---|---|---|---|
| Movimiento crudo | 0 | 55 | 0 | 110 | **0,00** | 1,00 | inicio: nunca; fin: 0,8 s |
| Movimiento suavizado (retención 10 s) | 0 | 55 | 0 | 110 | **0,00** | 1,00 | inicio: nunca; fin: 0,8 s |
| Presencia cruda | 110 | 0 | 55 | 0 | 1,00 | **0,00** | inicio: 0,8 s |
| Presencia suavizada (mayoría 5 s) | 110 | 0 | 55 | 0 | 1,00 | **0,00** | inicio: 0,8 s |

Positivo de movimiento = caminando; positivo de presencia = caminando o sentada quieta.

## Lectura

- **Movimiento: no detectó la caminata.** La señal suavizada del detector caminando (mediana 814.702) es igual a
  la de la sala vacía (848.410) y no alcanza el umbral de entrada (~1,23 M). Solo 14 muestras de movimiento en
  toda la sesión, casi todas cuando la sala debía estar vacía (01:12–01:14) y una sola caminando (01:15:3x).
- **Presencia: siempre "presente".** El entrenamiento de 20 s con la sala muy quieta y un enlace de 0,8 m dejó un
  umbral de presencia de 0,00007; con la sala vacía el "wander" medio ya fue 0,0034, así que la presencia salió
  positiva el 100 % del tiempo. Sí hay un cambio claro del "wander" entre tramos (vacía 0,004 → caminando 0,010 →
  sentada 0,08): la información existe, pero el umbral entrenado no sirve.
- **Hipótesis principal** (a verificar): con el router a 0,8 m, el trayecto directo domina el CSI y el cuerpo
  apenas lo perturba, salvo que cruce exactamente entre ambos. Por eso las guías recomiendan separar placa y
  router (o hotspot) 2–3 m y moverse cerca de la línea que los une.
- Con estos datos **no** se puede afirmar que el sistema detecta actividad; tampoco que no la detecta en
  condiciones normales de separación.

Archivos: `datos\procesados\evaluacion_S002.csv`, `latencias_S002.csv`, `S002_deteccion.png`.
