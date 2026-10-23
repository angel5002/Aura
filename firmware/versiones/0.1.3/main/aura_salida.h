/*
 * AURA - salida central de lineas.
 * Cada mensaje HMS va al USB (solo si hay un host USB, sin bloquear nunca) y a la via local (UDP).
 */
#pragma once

#include <stdarg.h>
#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"

/* Instala el driver USB Serial/JTAG, redirige ESP_LOG y deja la consola en modo no bloqueante. */
esp_err_t aura_salida_init(void);

/* Largo maximo del cuerpo de un mensaje HMS (sin prefijo ni '\n'); lo que exceda se recorta. */
#define AURA_SALIDA_HMS_MAX 1400

/* Formatea el cuerpo del mensaje (SIN el prefijo "HMS:"; los '\n' finales se quitan) en un buffer
 * estatico protegido por mutex, asi no ocupa pila de la tarea que llama. Al USB va en UNA sola
 * escritura: la linea llega completa o no llega (nunca un "HMS:" sin cuerpo). */
void aura_salida_hms_va(const char *fmt, va_list args);

/* Lectura no bloqueante del USB (comandos de consola). Devuelve bytes leidos. */
int aura_salida_leer_usb(uint8_t *buf, size_t len);

typedef struct {
    uint32_t hms_total;        /* mensajes HMS generados */
    uint32_t usb_descartes;    /* bytes no escritos porque el buffer USB estaba lleno */
    uint32_t usb_conectado;    /* 1 si hay host USB */
} aura_salida_stats_t;

void aura_salida_stats(aura_salida_stats_t *out);
