# ADR-0007: Secretos solo en NVS, fuera del binario y de git

- **Estado:** Aceptada (2026-10-22)
- **Fecha:** 2026-10-26 (registro); decisión tomada en la fecha del estado
- **Decide:** Deisy
- **Equipo donde se tomó:** conversación de diseño + PC principal
- **Nota:** Reconstruida el 26/10/2026 desde las conversaciones de diseño; verificar rutas de evidencia.

## Contexto
Con OTA, la imagen del firmware circula; los ejemplos compilaban el SSID y la contraseña desde menuconfig.

## Decisión
Credenciales (WiFi principal y respaldo, cuenta de la placa, clave local) en la NVS, cargadas por USB con `analisis/cargar_credenciales.py` (doble ingreso, prueba de la cuenta contra Firebase, `--solo`, `--borrar`).

## Alternativas consideradas
| Alternativa | Por qué no |
|---|---|
| menuconfig / sdkconfig.defaults | Los secretos quedan en el binario y pueden terminar en git. |

## Consecuencias
- T3 (búsqueda de secretos en el .bin) no detecta secretos compilados como valores en instrucciones; la garantía es de diseño y T3b revisa los sdkconfig.
- Cambiar de red exige USB o, a futuro, aprovisionamiento desde el celular.

## Evidencia
- `docs/resultados_pruebas.md` y `docs/resultados_pruebas_observaciones.md` (T3, T3b); script `analisis/pruebas/t3_secretos.py`.

## Cómo revertir
Volver a credenciales compiladas (no recomendado).
