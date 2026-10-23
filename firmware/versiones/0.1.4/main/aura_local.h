/*
 * AURA - via local por UDP (sin cifrar; ver limitaciones en docs/arquitectura_dos_vias.md).
 *
 * Descubrimiento: la placa difunde cada 2 s  "AURA-ANUNCIO {json}"  al puerto CONFIG_AURA_ANUNCIO_PUERTO.
 * Suscripcion:    el receptor envia "SUB <nombre>" al puerto CONFIG_AURA_UDP_PUERTO y lo renueva cada <30 s.
 * Datos:          a cada suscriptor, un datagrama por mensaje:
 *                     "A1 <seq> <t_us> <tipo> <cuerpo>"
 *                 seq  = contador global de datagramas de datos (uint32) para medir perdidas;
 *                 t_us = hora UNIX en microsegundos (SNTP); 0 si aun no hay hora;
 *                 tipo = "hms" (cuerpo = JSON del mensaje HMS) o "csi" (cuerpo = JSON con base64).
 * Hora:           "TIEMPO <t_pc_us>"  ->  "TIEMPO <t_pc_us> <t_placa_us> <sntp_ok>"  (prueba D10).
 * Comandos:       "CMD <ctr> <hmac_hex> <texto>"  con HMAC-SHA256(clave_local, "<ctr> <texto>").
 */
#pragma once

#include <stddef.h>
#include <stdint.h>
#include "esp_err.h"

typedef enum {
    AURA_LOCAL_TIPO_HMS = 'h',
    AURA_LOCAL_TIPO_CSI = 'c',
} aura_local_tipo_t;

/* Registro binario de un paquete CSI tal como llega del driver (ver aura_sensing.c). */
typedef struct __attribute__((packed)) {
    uint32_t seq_id;        /* contador de esp-radar por par */
    int64_t  t_us;          /* hora UNIX (us) al recibir el callback; 0 sin SNTP */
    uint32_t rx_ts_us;      /* rx_ctrl.timestamp (us desde el arranque de la radio) */
    int8_t   rssi;
    int8_t   noise_floor;
    uint8_t  channel;
    uint8_t  agc_gain;
    int8_t   fft_gain;
    uint8_t  rate;
    uint8_t  rx_format;
    uint8_t  cwb;
    uint8_t  data_type;     /* 0 = int8, 1 = int16 (valid_data) */
    float    compensacion;  /* factor escalar aplicado por esp_csi_gain_ctrl a valid_data */
    uint16_t raw_len;       /* bytes de raw (buffer del driver, sin filtrar ni compensar) */
    uint16_t valid_len;     /* bytes de valid (subportadoras validas, compensadas) */
    uint8_t  datos[];       /* raw_len bytes de raw y luego valid_len bytes de valid */
} aura_csi_registro_t;

esp_err_t aura_local_iniciar(void);

/* No bloqueantes; si la cola esta llena el mensaje se descarta y se cuenta. */
void aura_local_encolar(aura_local_tipo_t tipo, const void *datos, size_t len);

/* Reserva espacio en la cola para escribir sin copias (se usa desde el callback de CSI, que corre en la
 * tarea del WiFi y no debe usar buffers grandes en la pila). NULL si no hay espacio o no hay receptores. */
void *aura_local_reservar(aura_local_tipo_t tipo, size_t len);
void aura_local_confirmar(void *ptr);

typedef struct {
    uint32_t enviados;       /* datagramas de datos enviados (suma sobre suscriptores) */
    uint32_t descartes_cola; /* mensajes perdidos por cola llena */
    uint32_t errores_envio;
    uint32_t seq;            /* ultimo numero de secuencia asignado */
    uint8_t  suscriptores;
} aura_local_stats_t;

void aura_local_stats(aura_local_stats_t *out);
