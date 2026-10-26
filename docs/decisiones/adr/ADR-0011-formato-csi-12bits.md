# ADR-0011: Formato CSI: LLTF de 12 bits, 26 subportadoras

- **Estado:** Aceptada (2026-10-24)
- **Fecha:** 2026-10-26 (registro); decisión tomada en la fecha del estado
- **Decide:** Claude (verificada)
- **Equipo donde se tomó:** conversación de diseño + PC principal
- **Nota:** Reconstruida el 26/10/2026 desde las conversaciones de diseño; verificar rutas de evidencia.

## Contexto
Se dudó si el decodificador leía mal (52 subportadoras esperadas a 8 bits).

## Decisión
Mantener el decodificador: el C5 entrega por defecto 53 palabras de 16 bits (valores de 12 bits) = 26 pares imaginario/real + relleno. Se guarda siempre el búfer crudo de 106 B.

## Alternativas consideradas
| Alternativa | Por qué no |
|---|---|
| Modo de 8 bits (52 subportadoras) | Menor precisión por valor; requiere firmware nuevo. Pendiente de comparar. |

## Consecuencias
- Resolución en frecuencia reducida; qué subportadoras físicas son las 26 no está documentado (inferencia: paso 2).
- Debe declararse en cualquier publicación.

## Evidencia
- D11a–d APROBADAS en `docs/resultados_pruebas.md` (24/10 00:26 con `F1_sin_regla_local.csv`, 30 159 paquetes;
  repetidas el 26/10 14:56 con `S002_local.csv`, 62 045 paquetes); script `analisis/pruebas/d11_formato_csi.py`;
  observaciones en `docs/resultados_pruebas_observaciones.md` (sección «Formato del CSI crudo del C5»).
- Decodificadores oficiales: esp-radar y `csi_recv_router` de esp-csi (leen palabras de 16 bits con extensión de
  12); `lltf_bit_mode` en `C:\esp\v5.5.6\esp-idf\components\esp_wifi\include\esp_wifi_he_types.h` (línea 63, fuera
  del repositorio).
- D11f **APROBADA** el 26/10/2026 con `S002_local.csv` (100,00 % de bytes altos en 0x00–0x0F; `valid` = 52 valores
  = 26 subportadoras), en `docs/resultados_pruebas.md`. Criterio (≥ 99 % y 52 valores) en `docs/plan_pruebas.md`,
  **definido a posteriori (26/10/2026), tras observar el resultado del 24/10**; el 24/10 figuraba como informativa
  / NO EJECUTADA con el mismo valor.

## Cómo revertir
Cambiar `lltf_bit_mode` y adaptar el decodificador.
