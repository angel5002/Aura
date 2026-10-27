# Cambios del kit móvil de AURA

Android con Termux. La versión está en el archivo `VERSION`.

## 0.1.0 — 26/10/2026

- Primera versión (fase 1). Copias sin cambios desde el repositorio (base: commit `57a3349`, más el commit que
  agrega este kit):
  - `scripts/receptor_local.py` ← `analisis/receptor_local.py` (reinicios por `ts_ms`, con la secuencia de respaldo);
  - `scripts/aura_proto.py` ← `analisis/aura_proto.py`;
  - `scripts/verificar_captura.py` ← `analisis/verificar_captura.py` (criterios, reinicios y telemetría);
  - `docs/ensayos/kit_movil_criterios.md` ← `docs/ensayos/kit_movil_criterios.md` (umbrales; fuente única).
  SHA-256 (primeros 16 caracteres): `aura_proto.py` b5902c0d5e39baff, `receptor_local.py` b9cda3f992712a29,
  `verificar_captura.py` 461d01741db9f9ff, `kit_movil_criterios.md` 251fb60ce5b3cfc4.
- `LEEME.md`: instalación de Termux, copia al celular, IP de la placa leída en el panel del router (sin reserva
  DHCP), captura con `--ip --sin-bind`, criterios de la prueba y paso de los datos a la PC. Sin la clave local ni
  otros secretos.
- **Estado de la prueba:** probado solo en la PC del proyecto (Windows): verificador con S002, F1 y PV (cumplen) y
  receptor del kit con una placa simulada en 127.0.0.1 (`t_us` = 0, hueco de 6 s → FALLIDO, reinicio por
  `brownout` → 2 épocas por `ts_ms` y 2 arranques en la telemetría). Datos sintéticos: solo demuestran que el código
  corre. **No verificado en un celular.**
- Pendiente (después del video del 30/10/2026): generar `kit_captura/` y `kit_movil/` desde `analisis/` con un
  script, en vez de copias a mano.
