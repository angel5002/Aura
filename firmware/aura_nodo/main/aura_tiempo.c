/*
 * AURA - hora por SNTP.
 */
#include <sys/time.h>

#include "esp_log.h"
#include "esp_netif_sntp.h"

#include "aura_tiempo.h"
#include "aura_wifi.h"

static const char *TAG = "aura_tiempo";
#define UNIX_2025_S  1735689600LL   /* 2025-01-01: cualquier hora anterior se considera "sin sincronizar" */

static bool s_iniciado;

static void al_cambiar_red(bool conectado, const uint8_t bssid[6], uint32_t gw)
{
    (void)bssid;
    (void)gw;
    if (!conectado) {
        return;
    }
    if (!s_iniciado) {
        esp_sntp_config_t cfg = ESP_NETIF_SNTP_DEFAULT_CONFIG_MULTIPLE(2, ESP_SNTP_SERVER_LIST("time.google.com", "pool.ntp.org"));
        cfg.start = true;
        if (esp_netif_sntp_init(&cfg) == ESP_OK) {
            s_iniciado = true;
            ESP_LOGI(TAG, "SNTP iniciado");
        }
    } else {
        esp_netif_sntp_start();   /* al reconectar, pedir hora de nuevo */
    }
}

esp_err_t aura_tiempo_iniciar(void)
{
    return aura_wifi_registrar_cb(al_cambiar_red);
}

bool aura_tiempo_sincronizado(void)
{
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return tv.tv_sec > UNIX_2025_S;
}

int64_t aura_tiempo_unix_us(void)
{
    struct timeval tv;
    gettimeofday(&tv, NULL);
    if (tv.tv_sec <= UNIX_2025_S) {
        return 0;
    }
    return (int64_t)tv.tv_sec * 1000000LL + tv.tv_usec;
}
