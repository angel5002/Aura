# ADR-0016: Protocolo de pruebas: criterios fijos, D0 obligatoria, sesiones con "listo"

- **Estado:** Aceptada (2026-10-23)
- **Fecha:** 2026-10-26 (registro); decisión tomada en la fecha del estado
- **Decide:** Deisy
- **Equipo donde se tomó:** conversación de diseño + PC principal
- **Nota:** Reconstruida el 26/10/2026 desde las conversaciones de diseño; verificar rutas de evidencia.

## Contexto
Hubo un bucle de reinicios que ninguna prueba sin placa detectó, y una sesión remota programada sin confirmación que no se pudo seguir (S002).

## Decisión
T1–T3, T3b y D0 para todo firmware nuevo; criterios no se cambian para aprobar; condiciones etiquetadas, repetidas y en orden variado; video como referencia; a distancia, nada empieza sin el "listo" de Deisy (≥ 2 min).

## Alternativas consideradas
| Alternativa | Por qué no |
|---|---|
| Ajustar criterios a posteriori | Invalida los resultados. |

## Consecuencias
- Más tiempo por versión, resultados confiables.

## Evidencia
- `docs/plan_pruebas.md`, `docs/resultados_pruebas.md`.

## Cómo revertir
—
