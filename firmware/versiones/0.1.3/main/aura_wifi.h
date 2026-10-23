/*
 * AURA - WiFi con red principal y de respaldo (credenciales en NVS).
 * Nunca registra el SSID ni la contrasena: solo "principal" / "respaldo".
 */
#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#include "esp_netif.h"

typedef enum {
    AURA_RED_NINGUNA = 0,
    AURA_RED_PRINCIPAL = 1,
    AURA_RED_RESPALDO = 2,
} aura_red_t;

/* conectado=true: hay IP; bssid y gw de la red actual. conectado=false: se perdio la red. */
typedef void (*aura_wifi_cb_t)(bool conectado, const uint8_t bssid[6], uint32_t gw);

esp_err_t aura_wifi_iniciar(void);
esp_err_t aura_wifi_registrar_cb(aura_wifi_cb_t cb);
bool aura_wifi_conectado(void);
bool aura_wifi_ip(esp_netif_ip_info_t *out);
aura_red_t aura_wifi_red_activa(void);
const char *aura_wifi_red_nombre(aura_red_t red);
int aura_wifi_rssi(void);
uint32_t aura_wifi_cambios_red(void);   /* cuantas veces se paso de una red a la otra */
uint32_t aura_wifi_reintentos_principal(void);   /* busquedas de la principal estando en el respaldo */

/* Prueba D7c-sim: la red principal se considera no disponible durante <segundos> (0 = cancelar). */
void aura_wifi_sim_pierde_principal(uint32_t segundos);
uint32_t aura_wifi_sim_restante_s(void);
