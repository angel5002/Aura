/*
 * AURA - ejecucion de comandos de las tres vias (USB, local, nube) en UNA sola cola.
 *
 * Orden: estricto orden de llegada (FIFO), sin prioridad entre vias.
 * Bloqueo: mientras una via tiene un entrenamiento en curso (TRAIN_START sin TRAIN_STOP), los comandos
 * TRAIN_* y RESET_BASELINE de las otras vias se rechazan con "entrenamiento en curso desde <via>".
 * Cada comando y su resultado se publican como HMS {"type":"ack",...,"origen":..,"id":..}; la via nube
 * ademas confirma en /sensores/<id>/comando.
 */
#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"

typedef enum {
    AURA_ORIGEN_USB = 0,
    AURA_ORIGEN_LOCAL,
    AURA_ORIGEN_NUBE,
} aura_origen_t;

typedef struct {
    char id[32];
    char cmd[32];
    char detalle[96];
    bool ok;
    aura_origen_t origen;
} aura_cmd_resultado_t;

/* Resultado de cada comando ejecutado (lo usa la via nube para confirmar). */
typedef void (*aura_cmd_cb_t)(const aura_cmd_resultado_t *res);

esp_err_t aura_comandos_iniciar(aura_cmd_cb_t al_terminar);
const char *aura_comandos_origen_nombre(aura_origen_t o);

/* texto = "RESET_BASELINE", "TRAIN_START AP", "SET_CFG AP motion_sensitivity=0.4", ... (sin "HMSCMD "). */
esp_err_t aura_comandos_encolar(aura_origen_t origen, const char *id, const char *texto);
void aura_comandos_rechazo(aura_origen_t origen, const char *id, const char *motivo);

/* Consola USB (solo origen usb), lineas que empiezan con "AURA ":
 *   AURA SET <clave> <valor_hex>   guarda en NVS (el valor nunca se repite en la respuesta)
 *   AURA DEL <clave>               borra
 *   AURA LIST                      que claves estan definidas (sin valores)
 *   AURA INFO                      version, particion y estado OTA
 *   AURA REBOOT                    reinicia */
void aura_comandos_consola(const char *linea);

/* HMAC-SHA256(clave_local, "<ctr> <texto>") en hexadecimal, y ctr creciente (anti repeticion).
 * Si hay hora SNTP, ctr (ms UNIX del emisor) debe estar a menos de 120 s de la hora de la placa. */
bool aura_comandos_autenticar(uint64_t ctr, const char *texto, const char *hmac_hex);
/* Igual, para la cabecera de OTA (texto = "<tamano> <sha256_hex>"). */
bool aura_comandos_autenticar_ota(uint64_t ctr, const char *texto, const char *hmac_hex);

/* Comandos rechazados desde el arranque (autenticacion fallida, via no permitida, cola llena...). */
uint32_t aura_comandos_rechazados(void);
