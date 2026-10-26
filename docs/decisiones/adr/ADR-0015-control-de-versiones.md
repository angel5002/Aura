# ADR-0015: Git con etiquetas y archivo de binarios por versión

- **Estado:** Aceptada (2026-10-23)
- **Fecha:** 2026-10-26 (registro); decisión tomada en la fecha del estado
- **Decide:** Deisy
- **Equipo donde se tomó:** conversación de diseño + PC principal
- **Nota:** Reconstruida el 26/10/2026 desde las conversaciones de diseño; verificar rutas de evidencia.

## Contexto
Se perdió el binario original de la 0.1.3 que había funcionado; hubo que reconstruirlo.

## Decisión
Repositorio git en `C:\aura`, una etiqueta `firmware-vX.Y.Z` por versión y copia en `firmware/versiones/`. Escaneo de secretos antes de cada commit.

## Alternativas consideradas
| Alternativa | Por qué no |
|---|---|
| Sin control de versiones | Ya causó una pérdida. |

## Consecuencias
- Repositorio sin remoto: riesgo al migrar o si falla el disco (pendiente decidir remoto privado o respaldo).

## Evidencia
- Commit inicial 37b4ae7; etiqueta firmware-v0.1.3.

## Cómo revertir
—
