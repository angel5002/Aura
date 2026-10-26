# ADR-0008: Flash de 4 MB con dos ranuras OTA de 1,5 MB y vuelta atrás

- **Estado:** Aceptada (2026-10-22)
- **Fecha:** 2026-10-26 (registro); decisión tomada en la fecha del estado
- **Decide:** ambos
- **Equipo donde se tomó:** conversación de diseño + PC principal
- **Nota:** Reconstruida el 26/10/2026 desde las conversaciones de diseño; verificar rutas de evidencia.

## Contexto
Las placas irán a casas ajenas; actualizar sin cable es más valioso que espacio de sobra.

## Decisión
Tabla: nvs 64 KB, otadata, phy_init, ota_0 y ota_1 de 1,5 MB, coredump. Vuelta automática a la versión anterior si la nueva no se valida; validación tras autoverificación (IP, CSI fresco, 7 tareas vivas, memoria ≥ 16 KB durante 10 s).

## Alternativas consideradas
| Alternativa | Por qué no |
|---|---|
| Una sola aplicación de 3 MB | Sin OTA ni vuelta atrás. |

## Consecuencias
- Binario con -Os ~1,18–1,20 MB (~24 % libre por ranura).
- OTA local autenticada con clave compartida y SHA-256; sin secure boot ni cifrado de flash (prototipo).

## Evidencia
- T1, T2 en `docs/resultados_pruebas.md`.

## Cómo revertir
Borrado completo y tabla de una sola aplicación.
