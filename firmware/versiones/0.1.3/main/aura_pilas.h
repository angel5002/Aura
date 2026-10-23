/*
 * AURA - tamanos de pila (bytes) de las tareas propias, en UN solo lugar: los usan xTaskCreate y la
 * telemetria de marca de agua ({"type":"pilas"} cada 60 s). Ajustarlos con margen del 25 % sobre el
 * maximo medido en D1/D3 (analisis\pruebas\pilas_propuesta.py).
 */
#pragma once

#define AURA_PILA_WIFI      5120
#define AURA_PILA_LOCAL     5120
#define AURA_PILA_CMD       5120
#define AURA_PILA_OTA       6144
#define AURA_PILA_NUBE      8192
#define AURA_PILA_TEL       5120
#define AURA_PILA_MONITOR   5120    /* web_serial_monitor (antes 4096 en el ejemplo) */
#define AURA_PILA_DIAG      3584    /* aura_diag (diagnostico de memoria, 0.1.3) */
