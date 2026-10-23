/*
 * AURA - configuracion y credenciales en NVS (namespace "aura_cred").
 * Los valores secretos NUNCA se imprimen: solo se informa si una clave esta definida.
 */
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include "esp_err.h"

/* Claves admitidas (whitelist). Las marcadas como secretas no se devuelven por ninguna via. */
typedef enum {
    AURA_CFG_WIFI1_SSID = 0,
    AURA_CFG_WIFI1_PASS,
    AURA_CFG_WIFI2_SSID,
    AURA_CFG_WIFI2_PASS,
    AURA_CFG_FB_API_KEY,
    AURA_CFG_FB_DB_URL,
    AURA_CFG_FB_EMAIL,
    AURA_CFG_FB_PASS,
    AURA_CFG_LOCAL_KEY,
    AURA_CFG_NUM
} aura_cfg_clave_t;

esp_err_t aura_config_init(void);

/* Copia el valor en buf (terminado en '\0'). Devuelve ESP_ERR_NOT_FOUND si no esta definido. */
esp_err_t aura_config_leer(aura_cfg_clave_t clave, char *buf, size_t len);
bool aura_config_definida(aura_cfg_clave_t clave);

/* Solo se llaman desde la consola USB (origen usb). */
esp_err_t aura_config_guardar_por_nombre(const char *nombre, const char *valor);
esp_err_t aura_config_borrar_por_nombre(const char *nombre);
/* Escribe en out un JSON {"wifi1_ssid":true,...} con el estado definido/no definido (sin valores). */
void aura_config_resumen_json(char *out, size_t len);

/* Valores no secretos que persisten (ultimo comando de la nube ejecutado). */
esp_err_t aura_config_leer_str(const char *nombre, char *buf, size_t len);
esp_err_t aura_config_guardar_str(const char *nombre, const char *valor);
