/*
 * SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 * AURA: modificado. La salida pasa por aura_salida (USB + via local), los comandos USB entran a la
 * cola unica de aura_comandos y cada ack lleva origen e id. Ver los comentarios "AURA:".
 */
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"
#include "esp_wifi_sensing.h"

#ifdef __cplusplus
extern "C" {
#endif

#define WEB_SERIAL_MONITOR_MAX_PEERS 8

typedef struct {
    const char *name; /**< Human-readable peer name shown by the UI. */
    uint8_t mac[6];   /**< Peer MAC address bound to the sensing channel. */
} web_serial_monitor_peer_t;

typedef struct {
    const web_serial_monitor_peer_t *peers;      /**< Peer table visible to the UI. */
    size_t peer_num;                             /**< Number of valid entries in `peers`. */
    uint32_t stream_period_ms;                   /**< Streaming period in milliseconds. Set `0` to use the default. */
} web_serial_monitor_config_t;

/* AURA: resultado del ultimo ack emitido al ejecutar un comando. */
typedef struct {
    bool ok;
    char detalle[96];
} web_serial_monitor_resultado_t;

esp_err_t web_serial_monitor_init(const web_serial_monitor_config_t *config);

/* AURA: actualiza la MAC de un par (cuando cambia el AP al pasar a la red de respaldo). */
void web_serial_monitor_actualizar_peer(size_t indice, const uint8_t mac[6]);

/* AURA: ejecuta un comando (texto sin "HMSCMD ") y devuelve el resultado de su ack. */
void web_serial_monitor_ejecutar(const char *texto, const char *origen, const char *id,
                                 web_serial_monitor_resultado_t *res);

/* AURA: emite un ack con origen e id. */
void web_serial_monitor_ack_origen(const char *cmd, bool ok, const char *detalle, const char *origen, const char *id);

/* AURA: emite un mensaje HMS arbitrario (fmt produce el JSON, sin "HMS:"). */
void web_serial_monitor_emitir(const char *fmt, ...) __attribute__((format(printf, 1, 2)));

#ifdef __cplusplus
}
#endif
