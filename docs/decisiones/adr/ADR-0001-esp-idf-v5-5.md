# ADR-0001: ESP-IDF v5.5.x (v5.5.6) en lugar de la última versión

- **Estado:** Aceptada (2026-10-22)
- **Fecha:** 2026-10-26 (registro); decisión tomada en la fecha del estado
- **Decide:** Deisy
- **Equipo donde se tomó:** conversación de diseño + PC principal
- **Nota:** Reconstruida el 26/10/2026 desde las conversaciones de diseño; verificar rutas de evidencia.

## Contexto
Hacía falta un entorno para compilar los ejemplos de esp-csi en el ESP32-C5. La versión estable más reciente era 6.0.x.

## Decisión
Usar ESP-IDF **v5.5.6**, instalado con EIM en `C:\esp` (`eim install -i v5.5.6 -p C:\esp`).

## Alternativas consideradas
| Alternativa | Por qué no |
|---|---|
| ESP-IDF 6.0.x (instalación fácil de EIM) | esp-csi solo se compila en su CI con IDF v5.4 y v5.5; sus `sdkconfig.defaults` se generaron con 5.5.0. |
| ESP-IDF 5.4 | El soporte de producción del C5 llegó en la rama 5.5. |

## Consecuencias
- Compatibilidad con esp-csi y esp_wifi_sensing.
- Rama con soporte hasta enero de 2028 (anuncio oficial de v5.5.5).
- Instalado como administrador: requirió `git safe.directory`.
- El error `compote ... No such command 'cooking'` de EIM no afecta (gestor de componentes 2.5.2 funciona).

## Evidencia
- Informe de Claude Code 22/10 (diagnóstico de entorno; no está en el repositorio). La instalación quedó documentada en `README.md` (sección «ESP-IDF v5.5 con EIM») y `docs/guia_placas.md` (paso 0).
- https://docs.espressif.com/projects/esp-idf/en/v5.5/esp32c5/get-started/windows-setup.html

## Cómo revertir
Instalar otra versión con EIM en otra ruta y recompilar; revisar cambios de API de esp-csi.
