# ADR-0009: Memoria: limitar buffers de recepción WiFi a 12 y ventana BA a 6

- **Estado:** Aceptada (2026-10-23)
- **Fecha:** 2026-10-26 (registro); decisión tomada en la fecha del estado
- **Decide:** ambos
- **Equipo donde se tomó:** conversación de diseño + PC principal
- **Nota:** Reconstruida el 26/10/2026 desde las conversaciones de diseño; verificar rutas de evidencia.

## Contexto
0.1.2 tuvo 142 asignaciones fallidas (mínimo 48 B) por ráfagas de recepción, no por TLS. La red tenía tormentas ARP de la PC .89.

## Decisión
`ESP_WIFI_DYNAMIC_RX_BUFFER_NUM` 128 → 12; `KEEP_PEER_CERTIFICATE` desactivado. La ventana BA se subió a 12 en 0.1.3 por una mala lectura de la guía (es un máximo, no un objetivo) y la 0.1.4 volvió a 6.

## Alternativas consideradas
| Alternativa | Por qué no |
|---|---|
| rx64 | 64 buffers × ~2,4 KB superan la memoria libre. |
| Variante bajo_ram | Riesgo de pérdidas en la vía local; queda como último recurso. |

## Consecuencias
- 0.1.3 sin fallos de asignación en 74 min con tormenta, pero mínimos de 9 KB con diagnóstico.
- 0.1.4 cayó en D0 con tormenta y la pila de red se atascó con CPU libre: **causa sin identificar**.
- Las tormentas de difusión son condición de prueba obligatoria.

## Evidencia
- Diagnósticos 0.1.2/0.1.3/0.1.4 en `docs/resultados_pruebas_observaciones.md`.
- https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-guides/wifi-driver/wifi-performance-and-power-save.html

## Cómo revertir
Volver a la configuración anterior por OTA (versiones archivadas).
