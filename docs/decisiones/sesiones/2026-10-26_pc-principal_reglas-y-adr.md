# Sesión 2026-10-26 — Reglas en CLAUDE.md, observaciones del registro y división de ADR

- **Equipo:** PC principal (`DESKTOP-7O57OU0`, usuario `usuario`), ruta `C:\aura`, Claude Code.
- **Commit al inicio:** `105fc85`. El commit final se consulta con `git log`.

## Objetivo
Aplicar lo que Deisy aprobó tras la instalación del registro de decisiones.

## Qué se hizo
- `CLAUDE.md`: reglas nuevas aprobadas (sección 3, renumeradas 1–23), nombre del equipo como criterio de la PC
  principal (sección 1), commit final por `git log` (sección 5) y nota técnica del firewall (sección 6).
- Reporte inicial: cifra de las tormentas ARP y estado "pendiente de copiar al repo" para L001 y la prueba del kit.
- D11 reejecutada con S002 (ver resultados).
- Etiqueta `firmware-v0.1.4`.
- ADR-0018 a ADR-0021; ADR-0012 y ADR-0014 marcadas como reemplazadas; `INDICE.md` actualizado.

## Resultados
- D11a–d: **APROBADAS** con S002 (medido, 62 045 paquetes), igual que el 24/10 con F1.
- D11f: mismo valor que el 24/10 (medido): 100,00 % de bytes altos en 0x00–0x0F, 52 valores = 26 subportadoras.
  Queda como **informativa / NO EJECUTADA**: el plan no le da criterio de aceptación.

## ADR creados o modificados
- Nuevos: ADR-0018 (Aceptada), ADR-0019 (Propuesta), ADR-0020 (Aceptada), ADR-0021 (Propuesta).
- Reemplazadas: ADR-0012, ADR-0014. Evidencia ajustada: ADR-0011.

## Pendientes y riesgos
- Copiar al repo los registros de L001 y de la prueba del kit en la laptop (Deisy avisará).
- D11f: resuelto en el cierre (criterio aceptado por Deisy, definido a posteriori; APROBADA con S002).
- 0.1.0–0.1.2 no se archivaron y se perdieron; no se etiquetan.
- **ADR-0022** (pendiente, no iniciado): respaldo del repositorio (GitHub privado o `git bundle`), con revisión
  previa de toda la historia en busca de secretos y datos.
- **Fase 1 de la ADR-0019** (pendiente, no iniciado): definirla en `docs/plan_presencia.md`.
