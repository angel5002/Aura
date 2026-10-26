# ADR-0005: Arquitectura de dos vías independientes (local + nube) sin PC en el lugar

- **Estado:** Aceptada (2026-10-22)
- **Fecha:** 2026-10-26 (registro); decisión tomada en la fecha del estado
- **Decide:** Deisy
- **Equipo donde se tomó:** conversación de diseño + PC principal
- **Nota:** Reconstruida el 26/10/2026 desde las conversaciones de diseño; verificar rutas de evidencia.

## Contexto
La PC principal es de escritorio; montar una PC en cada lugar era trabajo desechable. Deisy pidió además datos completos (no resúmenes) en red local.

## Decisión
La placa trabaja sola: **vía local** UDP a velocidad completa (cada HMS y CSI crudo, con número de secuencia y marca SNTP) y **vía nube** con resúmenes y comandos por Firebase. Ninguna depende de la otra. Sin WebSocket en la placa.

## Alternativas consideradas
| Alternativa | Por qué no |
|---|---|
| Solo nube | Pierde la resolución completa para investigación y depende de internet. |
| Solo PC por USB | Obliga a llevar una PC a cada lugar. |
| WebSocket en la placa | ~12–16 KB de RAM y 35–50 KB de flash que no había (FASE 1). |

## Consecuencias
- Datos completos solo si un equipo de la misma red los graba.
- Datos locales sin cifrar; comandos locales protegidos con clave compartida (HMAC).
- Comandos remotos solo por Firebase.

## Evidencia
- `docs/arquitectura_dos_vias.md`

## Cómo revertir
Desactivar una vía por configuración; la otra sigue funcionando.
