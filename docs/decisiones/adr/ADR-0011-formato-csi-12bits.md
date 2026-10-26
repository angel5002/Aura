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
- D11a–d y D11f en `docs/resultados_pruebas.md` (24/10 00:26) y `docs/resultados_pruebas_observaciones.md` (sección «Formato del CSI crudo del C5»); script `analisis/pruebas/d11_formato_csi.py`.
- `esp_wifi_he_types.h` (`lltf_bit_mode`), fuera del repositorio: `C:\esp\v5.5.6\esp-idf\components\esp_wifi\include\esp_wifi_he_types.h` (línea 63).
- Parsers de esp-radar y esp-csi.

## Cómo revertir
Cambiar `lltf_bit_mode` y adaptar el decodificador.
