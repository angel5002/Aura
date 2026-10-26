# Sesión 2026-10-26 — Creación del registro de decisiones

- **Equipo:** conversación de diseño (Claude en claude.ai); archivos para instalar en la PC principal.
- **Instalación:** PC principal (`DESKTOP-7O57OU0`, usuario `usuario`, `C:\aura`), 26/10/2026, Claude Code.
- **Commit al inicio:** `1f36374` (Kit de captura 1.1.0…).
- **Commit final:** `310b4ff` ("Registro de decisiones (ADR 0001-0017), CLAUDE.md y mapa de investigación"). Este
  dato se anotó en un commit posterior, porque un commit no puede contener su propio hash.

## Objetivo
Instalar un sistema para que cada decisión de diseño y arquitectura quede registrada con su porqué, y
que el contexto sobreviva a un cambio de equipo.

## Qué se hizo
- `CLAUDE.md` en la raíz: identificación del equipo, reglas no negociables, protocolo de ADR, informes
  de sesión y guía de migración.
- `docs/decisiones/`: README, plantilla, índice, bitácora y reporte inicial.
- ADR-0001 a ADR-0017 reconstruidos desde las conversaciones del 22 al 26/10.

## Instalación en la PC principal (Claude Code)
- SHA-256 del zip verificado; `CLAUDE.md` del zip idéntico al de la raíz.
- `docs/decisiones/` copiado (23 archivos, sin conflictos); mapa en `docs/investigacion/AURA_mapa_investigacion.md`.
- Rutas de evidencia comprobadas en ADR-0001…0017 y en el reporte inicial; 12 correcciones de rutas, sin cambiar
  el sentido de ninguna decisión (detalle en `bitacora.md`). Cuatro observaciones quedan sin corregir porque no
  son rutas (ver bitácora).
- Zip y carpeta temporal borrados; los `*.zip` de la raíz siguen fuera de git.

## Pendiente
- Rutas de evidencia: verificadas y corregidas (26/10/2026). Quedan las observaciones de la bitácora.
- Reglas de la memoria de Claude Code que no están en `CLAUDE.md`: propuestas a Deisy, pendientes de aprobación.
- Decidir remoto privado o respaldo del repositorio (para migrar de PC).
- Aprobar o ajustar ADR-0012 y ADR-0014 (están como Propuesta).
