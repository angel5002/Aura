# ADR-0021: FTM para estimar la distancia entre placas (por evaluar)

- **Estado:** Propuesta (2026-10-26)
- **Fecha:** 2026-10-26
- **Decide:** ambos
- **Equipo donde se tomó:** conversación de diseño; registrada en la PC principal
- **Relacionadas:** reemplaza (en parte) a ADR-0014; ADR-0020

## Contexto
La regla de instalación (ADR-0020) no mide distancias. Una distancia estimada automáticamente serviría como
metadato de cada sesión.

## Decisión (propuesta)
Evaluar FTM (Fine Timing Measurement, 802.11mc) entre placas para estimar la distancia. No se adopta hasta medir su
precisión con el hardware del proyecto.

## Alternativas consideradas
| Alternativa | Por qué no |
|---|---|
| Medir con cinta | Inviable fuera del laboratorio (ADR-0020). |
| Solo RSSI | Muy sensible a obstáculos y orientación; se guarda igual como metadato. |

## Consecuencias
- FTM en C5: soportado según la documentación de ESP-IDF v6.0 (iniciador en estación, respondedor en AP);
  precisión limitada según Espressif; requiere una placa como AP. **No verificado en v5.5.6.**
- Evaluarlo exige firmware nuevo (con D0 y el protocolo de pruebas).

## Evidencia
- Espressif, ESP-IDF v6.0 (ESP32-C5), Wi-Fi Location / FTM (documentación oficial; no verificado en v5.5.6).
- `docs/investigacion/AURA_mapa_investigacion.md` (preguntas sobre FTM/RTT).

## Cómo revertir
Es una propuesta: si la precisión no sirve, se marca como Descartada.
