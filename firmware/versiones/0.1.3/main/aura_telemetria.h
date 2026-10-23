/*
 * AURA - telemetria cada 10 s por USB y por la via local (mensaje HMS {"type":"telemetria",...}).
 */
#pragma once

#include <stdint.h>
#include "esp_err.h"

typedef struct {
    uint32_t heap_libre;
    uint32_t heap_minimo;           /* minimo historico desde el arranque */
    uint32_t heap_min_intervalo;    /* minimo de los ultimos 10 s (se reinicia en cada informe) */
    uint32_t bloque_max;            /* bloque libre mas grande al informar */
    float hms_por_s;            /* muestras "sample" del canal AP por segundo en la ventana */
    float ts_mediana_ms;        /* intervalo entre ts_ms consecutivos */
    float ts_p95_ms;
    uint32_t encendido_s;
    const char *motivo_reinicio;
} aura_telemetria_t;

esp_err_t aura_telemetria_iniciar(void);
void aura_telemetria_muestra(uint64_t ts_ms);
void aura_telemetria_ultima(aura_telemetria_t *out);
const char *aura_telemetria_motivo_reinicio(void);
/* Nombre de la primera tarea propia que no existe (NULL si estan todas). Lo usa la autoprueba. */
const char *aura_telemetria_tarea_faltante(void);
/* Emite {"type":"memoria","momento":...,"heap_libre","heap_minimo","encendido_s"} en un momento clave:
 * "ip", "detector_creado", "detector_estable", "nube_sesion", "nube_primera_escritura". */
void aura_telemetria_hito(const char *momento);

/* Memoria. OJO: la telemetria usa el monitor local de heap de IDF, asi que esp_get_minimum_free_heap_size()
 * devuelve el minimo del intervalo en curso; para el historico usar aura_telemetria_minimo_historico(). */
uint32_t aura_telemetria_minimo_historico(void);
uint32_t aura_telemetria_minimo_intervalo(void);    /* minimo desde el ultimo informe (intervalo en curso) */
uint32_t aura_telemetria_bloque_max(void);           /* heap_caps_get_largest_free_block(MALLOC_CAP_DEFAULT) */
