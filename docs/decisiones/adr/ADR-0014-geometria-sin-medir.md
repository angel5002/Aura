# ADR-0014: No exigir medición de distancias: regla de instalación + prueba de cobertura

- **Estado:** Reemplazada por ADR-0020 y ADR-0021 (2026-10-26). Antes: Propuesta (2026-10-24).
- **Reemplazo:** la regla de instalación y la prueba de cobertura pasan a ADR-0020 (Aceptada); FTM, a ADR-0021 (Propuesta). Este texto no se modifica.
- **Fecha:** 2026-10-26 (registro); decisión tomada en la fecha del estado
- **Decide:** ambos
- **Equipo donde se tomó:** conversación de diseño + PC principal
- **Nota:** Reconstruida el 26/10/2026 desde las conversaciones de diseño; verificar rutas de evidencia.

## Contexto
Medir distancias entre placas en cada instalación es irreal. L001 mostró además que un enlace sobre una mesa no puede cruzarse.

## Decisión
Regla: transmisor y placa a 2–3 m, misma altura (~1 m), zona de interés entre ambos. Prueba de cobertura automática (caminata de 30 s → buena / débil / reubicar). Geometría solo como metadato (RSSI siempre; FTM a evaluar).

## Alternativas consideradas
| Alternativa | Por qué no |
|---|---|
| Medir con cinta en cada sesión | Inviable fuera del laboratorio. |
| Modelo 3D de la habitación por fotos | No aporta a la detección (los objetos fijos no generan cambios; resolución ~7,5 m a 20 MHz). Útil solo para simulación futura. |

## Consecuencias
- FTM: soportado en C5 según docs IDF v6.0 (iniciador estación, respondedor AP); precisión limitada según Espressif; requiere placa como AP. No verificado en v5.5.6.
- Varias placas receptoras reducen la dependencia de la posición.

## Evidencia
- Wang et al., zonas de Fresnel, UbiComp 2016, DOI 10.1145/2971648.2971744.

## Cómo revertir
Volver a registrar distancias medidas en el protocolo.
