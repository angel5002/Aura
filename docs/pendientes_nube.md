# Pendientes de la vía nube (se retoman después del 30/10/2026)

Para el video se usa el modo solo local con captura por USB (`guion_grabacion.md`). Estado al 23/10/2026.

## 1. Atasco de la pila de red con la CPU libre (0.1.4) — causa NO identificada

- 0.1.4 (BA 6, TCP_WND 5760, 12 buffers de recepción) falló D0: con una tormenta de ARP en el arranque, la cola
  de entrada de `tiT` llegó a 11–12 (= todos los buffers) con la CPU 44–80 % libre, la memoria libre bajó a
  12 B y la placa se reinició (`assert ... dtoa.c:239 (REENT malloc succeeded)`: un `printf` con `%f` sin memoria).
- 0.1.3 (BA 12, TCP_WND 12 KB) pasó 74 min con ~36 min de tormenta sin asignaciones fallidas, pero con caídas de
  < 20 ms hasta 9 KB. Con una sola observación de cada versión no se puede atribuir la diferencia a BA/TCP_WND.
- Hipótesis descartada: falta de CPU para `tiT` por el radar (prioridad 24): IDLE ≥ 44 % en todos los episodios.
- Próximo paso propuesto: memoria por tarea (`CONFIG_HEAP_TASK_TRACKING`, ~1–2 KB) con instantánea al inicio y al
  fin de cada episodio, más el estado de `tiT` (bloqueada/lista); si no basta, rastreo de heap acotado a ~200 ms
  (~3–4 KB de búfer).
- Riesgos conocidos sin corregir: `RADAR_MALLOC_RETRY` de `esp_radar` reintenta con `vTaskDelay` dentro de la
  tarea WiFi cuando no hay memoria (no se modifica esp-radar antes del 30/10); los `printf` con `%f` abortan si
  newlib no consigue memoria.

## 2. Tormentas de ARP como condición de prueba

- Origen real del 23/10: una PC HP de la casa (`192.168.0.89`, `a0:d3:c1:24:88:c6`, DESKTOP-VQMJ5PC) con
  150–220 broadcast ARP por segundo; apagada el 23/10 a las ~17:00 (desde las 17:09:33 la placa ve 0–1 ARP
  cada 10 s).
- Toda prueba de memoria de la nube debe repetirse **con y sin tormenta** (encendiendo esa PC de forma
  controlada o con un generador de ARP en la red de laboratorio).
- 0.1.4 informa los 3 emisores de broadcast de cada intervalo con tormenta (`{"type":"tormenta"}`); está
  archivada en `firmware\versiones\0.1.4` junto con el registro del cuerpo de los errores de la nube y la
  conservación de bloques rechazados.

## 3. Corrección de la hora SNTP (pendiente; afecta a todas las versiones)

- `aura_tiempo_sincronizado()` solo comprueba que el año sea > 2025; el ESP32 conserva la hora tras un reinicio
  por software/USB. La nube arranca con la hora vieja y el primer bloque `/crudo` queda con t1 < t0 tras la
  corrección SNTP → 401 de la regla `t1 >= t0` (reproducido en el emulador: `firebase\pruebas\reproducir_401.mjs`).
- Corrección: marcar "sincronizado" solo en el callback real de SNTP
  (`sntp_set_time_sync_notification_cb`), y descartar o reabrir el bloque si el reloj retrocede.
- Mientras tanto: tras grabar o reiniciar por USB, desconectar y reconectar la alimentación.

## 4. Otros

- Costo de memoria del diagnóstico (`aura_diag`, estadísticas de lwIP, run-time stats): ~9,8 KB.
- Modo solo local: sin credenciales de Firebase la tarea de la nube no abre TLS, pero sus buffers (~12,4 KB) y su
  pila (8 KB) se reservan igual; cambio mínimo propuesto: no crearla si faltan credenciales al arrancar.
- La regla del 30 KB de mínimo por intervalo sigue sin cumplirse en ninguna versión medida.
