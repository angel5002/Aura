# Sesión S002 (24/10/2026, 01:12:30–01:17:15): sala vacía

**La evaluación por tramos planeada queda ANULADA**: el horario no se siguió (la investigadora no vio el plan a
tiempo; no salió ni entró a la sala). **Ocupación según la investigadora: sala vacía; sin verificación
independiente.** Se reetiquetó como sala vacía (~5 min); las etiquetas del plan se conservan en
`S002_etiquetas_plan_no_seguido.csv`. La versión anterior de este documento está en git (commit bb137a1).

Condiciones: aura_nodo 0.1.3 en modo solo local; enlace corto router–placa de **0,8 m con señal directa fuerte**;
PC quieta junto a la placa; RESET_BASELINE 01:12:30 (STABLE a los 2,6 s) y entrenamiento de presencia de 20 s
(01:13:10–01:13:30) con la sala vacía; madrugada. Una sola sesión: **no es una evaluación definitiva.**

## Falsas alarmas en sala vacía (`pruebas\falsas_alarmas.py`, rejilla 1 s, margen 5 s)

| Detector | Falsas alarmas | Especificidad | Tiempo evaluado |
|---|---|---|---|
| Movimiento crudo | 1 de 280 s = **0,4 %** | 0,996 | 4,7 min |
| Movimiento suavizado (retención 10 s, como la placa) | 10 de 280 s = **3,6 %** | 0,964 | 4,7 min |
| Presencia cruda (desde 01:13:33, umbrales válidos) | 222 de 222 s = **100 %** | 0,000 | 3,7 min |
| Presencia suavizada (mayoría 5 s) | 222 de 222 s = **100 %** | 0,000 | 3,7 min |

- **Movimiento**: pocas falsas alarmas en sala vacía (una detección aislada se convierte en 10 s de MOVIMIENTO por
  la retención). No se puede decir nada sobre la sensibilidad: no hubo nadie moviéndose.
- **Presencia**: inutilizable con este entrenamiento. El umbral quedó en 0,00007, y el "wander" de la sala vacía
  subió solo con el tiempo (≈0,004 al comienzo, ≈0,08 cinco minutos después) sin nadie en la sala: **deriva**, no
  una persona. Con ese umbral, la presencia es positiva el 100 % del tiempo.
- Archivos: `S002.csv` (USB), `S002_local.csv` (CSI crudo), `S002_etiquetas.csv`.
