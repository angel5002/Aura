# ADR-0010: 0.1.3 en modo solo local como versión de trabajo; nube en pausa

- **Estado:** Aceptada (2026-10-23)
- **Fecha:** 2026-10-26 (registro); decisión tomada en la fecha del estado
- **Decide:** Deisy
- **Equipo donde se tomó:** conversación de diseño + PC principal
- **Nota:** Reconstruida el 26/10/2026 desde las conversaciones de diseño; verificar rutas de evidencia.

## Contexto
La 0.1.4 falló; el plazo del video no permitía investigar el atasco de la pila de red.

## Decisión
Usar la 0.1.3 (reconstruida) sin `fb_pass`: sin TLS. Captura por USB o por la vía local con la laptop en la misma red. La nube se retoma después del 30/10.

## Alternativas consideradas
| Alternativa | Por qué no |
|---|---|
| 0.1.5 sin diagnóstico | Binario nuevo sin probar antes del video. |

## Consecuencias
- Sin tormenta: APROBADA (mínimo 34,5 KB). Con tormenta: FALLIDA por criterio (26,4 KB) sin fallos ni reinicios.
- Pendientes: hora SNTP tras reinicio por software (401), atasco 0.1.4, push sin PC.

## Evidencia
- `docs/pendientes_nube.md`; etiqueta git `firmware-v0.1.3`.

## Cómo revertir
Grabar otra versión archivada en `firmware/versiones/`.
