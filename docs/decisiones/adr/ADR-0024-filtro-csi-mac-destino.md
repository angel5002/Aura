# ADR-0024: Filtrar el CSI por MAC de destino (solo tramas dirigidas a la placa)

- **Estado:** Propuesta
- **Fecha:** 2026-10-27
- **Decide:** Deisy (dirección pedida por Deisy; análisis y redacción de Claude; pendiente de aprobación)
- **Equipo donde se tomó:** PC principal (`DESKTOP-7O57OU0`, `C:\aura`)
- **Relacionadas:** ADR-0002 (esp_wifi_sensing como base), ADR-0011 (formato CSI), ADR-0023 (red AURA-LAB)

## Contexto
En K000 (27/10/2026, AURA-LAB, receptor en el celular por WiFi) la placa B midió **~436 CSI/s** (la propia placa lo
confirma: `csi_total` sube ~436/s), frente a ~100/s en S002 (24/10, router de casa, receptor por cable); la memoria
mínima por intervalo bajó a **10 588 B** (S002: 27 544 B). Medido: `docs/decisiones/bitacora.md` (27/10, 09:40) y
`datos/crudos/K000_local.csv` (fuera de git).

Lectura del código (sin cambios):
- esp-radar pone la radio en **modo promiscuo** (`firmware/aura_nodo/managed_components/espressif__esp-radar/src/esp_radar.c:1623`).
- **No hay filtro de destino**: `filter_dmac_flag = false` por defecto (`esp_radar.h:375`); AURA no lo cambia
  (`firmware/aura_nodo/main/aura_sensing.c:108-122`). El filtro existe (`esp_radar.c:522`, `:563`).
- La selección es por **MAC de origen**: el par del detector es la MAC del router (`esp_wifi_sensing.c:1445`,
  `esp_radar.c:538-541`); en ESP-IDF `mac` = origen y `dmac` = destino (`esp_wifi_types_native.h:119-120`).
- Las ventanas del detector se cuentan en **paquetes** (`esp_radar.c:1488`, `:870`): 20 paquetes por ventana,
  pensados para ~10 ms por paquete (ping de 100 Hz, `firmware/versiones/0.1.3/sdkconfig.usado:2451`).

Motivo doble:
- **(a) Bucle por retransmisión con receptor WiFi** (hipótesis de Deisy, **inferida, en verificación**: procedimiento
  en `docs/ensayos/bucle_csi_procedimiento.md`): cada datagrama que B envía al celular lo reemite el router por el aire
  con origen = router; B lo mide como CSI del router y genera otro datagrama.
- **(b) En cualquier red**, el modo promiscuo sin filtro de destino hace que la tasa de CSI, y con ella la duración
  de las ventanas del detector, dependa del tráfico de otros equipos con el router (en S002, el de la casa).

## Decisión
Propuesta: en `enganchar_csi()` (`aura_sensing.c`), configurar esp-radar con `filter_dmac` = MAC propia de la placa
(STA) y `filter_dmac_flag = true`, para medir CSI **solo de tramas dirigidas a la placa** (en la práctica, las
respuestas al ping de 100 Hz). Versión de firmware **0.1.5**, en una rama aparte; no se graba hasta que Deisy lo
decida, después de K001, el procedimiento del bucle (casos 1 y 2) y K002.

## Alternativas consideradas
| Alternativa | Por qué no |
|---|---|
| Dejarlo como está | La tasa y las ventanas dependen del tráfico ajeno; con receptor WiFi, posible bucle (más carga y menos memoria). |
| Desactivar el modo promiscuo tras iniciar esp-radar | No verificado qué CSI entrega ESP-IDF sin promiscuo; esp-radar lo activa a propósito y podría dejar de recibir. Más invasivo que un filtro que la librería ya ofrece. |
| Filtrar por origen (`filter_mac` = router) | Ya es lo que hace el par del detector; no evita las tramas del router hacia otros equipos (el caso del bucle). |
| Limitar la tasa de CSI en AURA (descartar por tiempo) | Esconde el síntoma; las tramas ajenas siguen entrando y cambiando la señal medida. |
| Receptor solo por cable | Evita (a) pero no (b), y contradice ADR-0023 (receptor en el celular). |

## Consecuencias
- Mejora: tasa de CSI acotada por el ping (≈100/s, como suponen las ventanas de esp-radar), independiente del
  tráfico ajeno; sin bucle con receptor WiFi (si la hipótesis se confirma); menos carga y más memoria libre (inferido).
- Empeora o limita: se pierden las balizas y demás tramas no dirigidas a la placa como fuente de CSI; si el router no
  responde al ping, no habrá CSI (antes llegaba de otras tramas). Firmware nuevo: T1–T3b y D0 obligatorias (regla 12).
- **A declarar:** S002, K000 y K001 (y cualquier dato anterior) se midieron **sin** ese filtro: no son comparables con
  los datos tomados con 0.1.5 o posteriores (tasa de CSI, ventanas del detector, % en MOVIMIENTO, memoria).
- Obliga a: D0 de 0.1.5 en una placa (propuesta: A), procedimiento del bucle, K002, y repetir la prueba del kit con
  0.1.5 si se adopta.

## Evidencia
- Medido: K000 (`datos/crudos/K000_local.csv`, fuera de git; resumen en la bitácora del 27/10).
- Código: citas de arriba (`managed_components` de `firmware/aura_nodo`, versión usada por 0.1.3).
- Rama con el cambio: `firmware-0.1.5-filtro-dmac` (T1–T3b en `docs/resultados_pruebas.md` de esa rama).
- No verificado: el bucle (en verificación); el comportamiento del detector con 0.1.5.

## Cómo revertir
Volver a 0.1.3 (archivada en `firmware/versiones/0.1.3`, etiqueta `firmware-v0.1.3`) o quitar las dos líneas del
filtro en `enganchar_csi()`; los datos tomados con 0.1.5 se marcan como de otra versión.
