# ADR-0002: Usar esp_wifi_sensing (esp-csi) como base de la detección

- **Estado:** Aceptada (2026-10-22)
- **Fecha:** 2026-10-26 (registro); decisión tomada en la fecha del estado
- **Decide:** ambos
- **Equipo donde se tomó:** conversación de diseño + PC principal
- **Nota:** Reconstruida el 26/10/2026 desde las conversaciones de diseño; verificar rutas de evidencia.

## Contexto
Con 8 días al hackathon no era viable escribir un detector propio desde cero.

## Decisión
Partir del ejemplo `wifi_sensing_demo` y del componente `esp_wifi_sensing` (licencia Apache 2.0 verificada en el archivo descargado, versión 0.1.1~3).

## Alternativas consideradas
| Alternativa | Por qué no |
|---|---|
| Detector propio sobre CSI crudo desde el inicio | Demasiado trabajo para el plazo; queda como línea de investigación (ADR-0012). |
| Ingeniería inversa del núcleo precompilado | Incierta, costosa y no da un método publicable (descartada 22/10). |

## Consecuencias
- Detección de movimiento disponible en horas.
- **El núcleo (`esp_radar_motion_dec`, `esp_csi_gain_ctrl`) es precompilado: caja negra.** No se puede describir metodológicamente; para publicar hará falta algoritmo propio.
- La presencia depende de entrenar con sala vacía y se pierde al reiniciar (la API no permite cargar umbrales ni plantillas).

## Evidencia
- `docs/evaluacion_wifi_sensing.md`
- https://github.com/espressif/esp-csi

## Cómo revertir
Reemplazar la decisión de movimiento/presencia por el detector propio (ADR-0012) sin cambiar el resto del firmware.
