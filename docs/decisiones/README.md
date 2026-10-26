# Registro de decisiones del proyecto AURA

Esta carpeta guarda **por qué** el proyecto es como es. Las reglas para escribir aquí están en la
sección 4 de `CLAUDE.md` (raíz del repositorio).

| Archivo / carpeta | Qué contiene |
|---|---|
| `INDICE.md` | Lista de todas las decisiones (ADR), con estado. Empieza por aquí. |
| `0000_reporte_inicial.md` | Estado del proyecto al 26/10/2026 y origen de las primeras decisiones. |
| `adr/` | Una decisión por archivo (`ADR-NNNN-titulo.md`). |
| `plantilla_adr.md` | Plantilla para nuevas decisiones. |
| `bitacora.md` | Eventos menores, una línea cada uno. |
| `sesiones/` | Informe de cada sesión de trabajo (equipo, qué se hizo, ADR creados). |

## Cómo leer un ADR
- **Aceptada:** está vigente.
- **Reemplazada:** ya no rige; sigue el enlace a la que la reemplazó.
- **Descartada:** se evaluó y no se adoptó; es útil para no repetir el intento.
- **Propuesta:** espera la aprobación de Deisy.

## Nota sobre los ADR 0001–0017
Se reconstruyeron el 26/10/2026 a partir de las conversaciones de diseño del 22 al 26 de octubre.
Las rutas de evidencia apuntan a archivos que existen en la PC principal; Claude Code debe comprobar
que existan y corregir las rutas que no coincidan (y anotarlo en la bitácora).
