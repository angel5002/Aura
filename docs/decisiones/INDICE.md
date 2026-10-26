# Índice de decisiones (ADR)

| ADR | Título | Estado | Decide |
|---|---|---|---|
| [ADR-0001](adr/ADR-0001-esp-idf-v5-5.md) | ESP-IDF v5.5.x (v5.5.6) en lugar de la última versión | Aceptada (2026-10-22) | Deisy |
| [ADR-0002](adr/ADR-0002-base-esp-wifi-sensing.md) | Usar esp_wifi_sensing (esp-csi) como base de la detección | Aceptada (2026-10-22) | ambos |
| [ADR-0003](adr/ADR-0003-consola-usb-serial-jtag.md) | Consola por USB Serial/JTAG | Aceptada (2026-10-22) | Claude (aprobada) |
| [ADR-0004](adr/ADR-0004-firebase-en-vez-de-supabase.md) | Firebase (plan Spark) como nube, en vez de Supabase | Aceptada (2026-10-22) | Deisy |
| [ADR-0005](adr/ADR-0005-arquitectura-dos-vias.md) | Arquitectura de dos vías independientes (local + nube) sin PC en el lugar | Aceptada (2026-10-22) | Deisy |
| [ADR-0006](adr/ADR-0006-seguridad-nube.md) | Modelo de seguridad de la nube: cuenta por dispositivo y reglas por UID | Aceptada (2026-10-22) | ambos |
| [ADR-0007](adr/ADR-0007-secretos-en-nvs.md) | Secretos solo en NVS, fuera del binario y de git | Aceptada (2026-10-22) | Deisy |
| [ADR-0008](adr/ADR-0008-particiones-ota.md) | Flash de 4 MB con dos ranuras OTA de 1,5 MB y vuelta atrás | Aceptada (2026-10-22) | ambos |
| [ADR-0009](adr/ADR-0009-memoria-buffers-rx.md) | Memoria: limitar buffers de recepción WiFi a 12 y ventana BA a 6 | Aceptada (2026-10-23) | ambos |
| [ADR-0010](adr/ADR-0010-version-video-solo-local.md) | 0.1.3 en modo solo local como versión de trabajo; nube en pausa | Aceptada (2026-10-23) | Deisy |
| [ADR-0011](adr/ADR-0011-formato-csi-12bits.md) | Formato CSI: LLTF de 12 bits, 26 subportadoras | Aceptada (2026-10-24) | Claude (verificada) |
| [ADR-0012](adr/ADR-0012-presencia-propia.md) | Descartar la presencia de esp-radar y diseñar un detector propio | Propuesta (2026-10-24) | ambos |
| [ADR-0013](adr/ADR-0013-kit-captura-portatil.md) | Kit de captura portátil solo para Windows | Aceptada (2026-10-24) | Deisy |
| [ADR-0014](adr/ADR-0014-geometria-sin-medir.md) | No exigir medición de distancias: regla de instalación + prueba de cobertura | Propuesta (2026-10-24) | ambos |
| [ADR-0015](adr/ADR-0015-control-de-versiones.md) | Git con etiquetas y archivo de binarios por versión | Aceptada (2026-10-23) | Deisy |
| [ADR-0016](adr/ADR-0016-protocolo-de-pruebas.md) | Protocolo de pruebas: criterios fijos, D0 obligatoria, sesiones con "listo" | Aceptada (2026-10-23) | Deisy |
| [ADR-0017](adr/ADR-0017-alcance-hackathon.md) | Alcance del hackathon: video de detección de movimiento | Aceptada (2026-10-22) | Deisy |

Pendientes de decidir: remoto privado para git; plan Blaze para push; modo CSI 8 vs 12 bits; firmware para placas A y C.
