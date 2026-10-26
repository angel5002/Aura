# ADR-0013: Kit de captura portátil solo para Windows

- **Estado:** Aceptada (2026-10-24)
- **Fecha:** 2026-10-26 (registro); decisión tomada en la fecha del estado
- **Decide:** Deisy
- **Equipo donde se tomó:** conversación de diseño + PC principal
- **Nota:** Reconstruida el 26/10/2026 desde las conversaciones de diseño; verificar rutas de evidencia.

## Contexto
Hay que capturar en lugares sin la PC principal, con laptops ajenas.

## Decisión
Kit con dependencias fijadas (Python 3.12 64 bits), detección automática del puerto (VID 303A), `kit_captura/scripts/verificar_kit.py`, visor en vivo con mapa de calor y teclas E/S/M, receptor por IP directa sin regla de firewall, sin secretos, versión y SHA-256.

## Alternativas consideradas
| Alternativa | Por qué no |
|---|---|
| Soporte macOS/Linux | Innecesario: solo se usarán equipos Windows. |

## Consecuencias
- Probado en laptop de campo (kit 1.1.0, SHA-256 0088F550…).
- Pendiente 1.1.1: espera de IP 60 → 120 s.

## Evidencia
- `kit_captura/`, `kit_captura/CAMBIOS.md`; commit `1f36374` (kit 1.1.0); el zip `kit_captura_aura_v1.1.0.zip` queda fuera de git.
- La prueba en la laptop de campo no está registrada en el repositorio (el informe quedó en la laptop).

## Cómo revertir
Volver a la versión anterior del zip archivada.
