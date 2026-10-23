/*
 * AURA - hora por SNTP. Marca de tiempo UNIX en microsegundos para cada mensaje.
 */
#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

esp_err_t aura_tiempo_iniciar(void);
bool aura_tiempo_sincronizado(void);
/* Hora UNIX en us; 0 si todavia no hay hora valida. */
int64_t aura_tiempo_unix_us(void);
