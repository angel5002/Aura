# ADR-0003: Consola por USB Serial/JTAG

- **Estado:** Aceptada (2026-10-22)
- **Fecha:** 2026-10-26 (registro); decisión tomada en la fecha del estado
- **Decide:** Claude (aprobada)
- **Equipo donde se tomó:** conversación de diseño + PC principal
- **Nota:** Reconstruida el 26/10/2026 desde las conversaciones de diseño; verificar rutas de evidencia.

## Contexto
La FireBeetle 2 ESP32-C5 tiene USB nativo (sin chip conversor). Los ejemplos de esp-csi sacaban la consola por UART0.

## Decisión
Configurar `CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y` en todas las copias de firmware.

## Alternativas consideradas
| Alternativa | Por qué no |
|---|---|
| UART a 921600 baudios | Con USB nativo las líneas CSI no habrían salido por el USB-C. |

## Consecuencias
- Los baudios no limitan la velocidad.
- Hubo que verificar que el firmware no se bloquea sin PC leyendo (alimentado por cargador).

## Evidencia
- Wiki DFRobot DFR1222; Kconfig de IDF v5.5.

## Cómo revertir
Volver a UART y usar un adaptador USB-serie externo.
