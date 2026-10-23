/*
 * AURA - WiFi con red principal y de respaldo.
 *
 * - 3 intentos fallidos seguidos en una red -> se pasa a la otra.
 * - En la red de respaldo, cada CONFIG_AURA_REINTENTO_PRINCIPAL_MIN se busca la principal con un escaneo
 *   (sin desconectarse); si aparece, se vuelve a ella. Al cambiar de red el detector se recrea y el
 *   entrenamiento se pierde: la presencia queda "no_disponible" hasta reentrenar (aura_sensing.c).
 * - SIM_PIERDE_PRINCIPAL <seg> (prueba D7c-sim): durante <seg> la principal se trata como no disponible
 *   (cada intento falla tras SIM_ESPERA_FALLO_MS, como un "AP no encontrado") y el escaneo no la ve.
 */
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_wifi.h"

#include "aura_wifi.h"
#include "aura_pilas.h"
#include "aura_config.h"
#include "aura_telemetria.h"
#include "web_serial_monitor.h"

static const char *TAG = "aura_wifi";

#define BIT_IP          BIT0
#define BIT_DESC        BIT1
#define BIT_REVISAR     BIT2   /* despertar la tarea (inicio/fin de una simulacion) */
#define ESPERA_IP_MS    20000
#define FALLOS_CAMBIO   3      /* intentos fallidos seguidos antes de pasar a la otra red */
#define MAX_CB          4
#define SIM_ESPERA_FALLO_MS 3000   /* duracion simulada de un intento fallido (escaneo sin encontrar el AP) */
#define REINTENTO_US    ((int64_t)CONFIG_AURA_REINTENTO_PRINCIPAL_MIN * 60 * 1000000LL)

static EventGroupHandle_t s_ev;
static esp_netif_t *s_netif;
static volatile aura_red_t s_red_activa = AURA_RED_NINGUNA;
static volatile uint32_t s_cambios;
static volatile uint32_t s_reintentos_principal;
static volatile int64_t s_sim_principal_hasta_us;
static aura_wifi_cb_t s_cbs[MAX_CB];

static void manejador(void *arg, esp_event_base_t base, int32_t id, void *data)
{
    (void)arg;
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        xEventGroupClearBits(s_ev, BIT_IP);
        xEventGroupSetBits(s_ev, BIT_DESC);
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        xEventGroupSetBits(s_ev, BIT_IP);
    }
}

static void notificar(bool conectado)
{
    uint8_t bssid[6] = {0};
    uint32_t gw = 0;
    if (conectado) {
        wifi_ap_record_t ap;
        if (esp_wifi_sta_get_ap_info(&ap) == ESP_OK) {
            memcpy(bssid, ap.bssid, 6);
        }
        esp_netif_ip_info_t ip;
        if (esp_netif_get_ip_info(s_netif, &ip) == ESP_OK) {
            gw = ip.gw.addr;
        }
    }
    for (int i = 0; i < MAX_CB; i++) {
        if (s_cbs[i]) {
            s_cbs[i](conectado, bssid, gw);
        }
    }
}

static bool cargar_red(int idx, wifi_config_t *cfg)
{
    memset(cfg, 0, sizeof(*cfg));
    aura_cfg_clave_t k_ssid = idx == 0 ? AURA_CFG_WIFI1_SSID : AURA_CFG_WIFI2_SSID;
    aura_cfg_clave_t k_pass = idx == 0 ? AURA_CFG_WIFI1_PASS : AURA_CFG_WIFI2_PASS;
    if (aura_config_leer(k_ssid, (char *)cfg->sta.ssid, sizeof(cfg->sta.ssid)) != ESP_OK) {
        return false;
    }
    bool con_clave = aura_config_leer(k_pass, (char *)cfg->sta.password, sizeof(cfg->sta.password)) == ESP_OK;
    cfg->sta.threshold.authmode = con_clave ? WIFI_AUTH_WPA2_PSK : WIFI_AUTH_OPEN;
    cfg->sta.sae_pwe_h2e = WPA3_SAE_PWE_BOTH;     /* WPA3: admite H2E y hunting-and-pecking */
    cfg->sta.pmf_cfg.capable = true;
    cfg->sta.scan_method = WIFI_ALL_CHANNEL_SCAN;
    cfg->sta.sort_method = WIFI_CONNECT_AP_BY_SIGNAL;
    return true;
}

static bool principal_sim_caida(void)
{
    return esp_timer_get_time() < s_sim_principal_hasta_us;
}

/* Busca la red principal sin desconectarse (escaneo activo filtrado por su SSID). Nunca registra el SSID. */
static bool principal_visible(void)
{
    wifi_scan_config_t sc = { .show_hidden = false, .scan_type = WIFI_SCAN_TYPE_ACTIVE };
    uint8_t ssid[33] = {0};
    if (aura_config_leer(AURA_CFG_WIFI1_SSID, (char *)ssid, sizeof(ssid)) != ESP_OK) {
        return false;
    }
    sc.ssid = ssid;
    uint16_t n = 0;
    esp_err_t err = esp_wifi_scan_start(&sc, true);
    memset(ssid, 0, sizeof(ssid));
    if (err == ESP_OK) {
        esp_wifi_scan_get_ap_num(&n);
    }
    esp_wifi_clear_ap_list();
    return err == ESP_OK && n > 0 && !principal_sim_caida();
}

static void tarea_wifi(void *arg)
{
    (void)arg;
    int actual = 0;
    int fallos = 0;
    int fallos_totales = 0;
    wifi_config_t cfg;
    while (true) {
        bool hay0 = cargar_red(0, &cfg);
        bool hay1 = cargar_red(1, &cfg);
        memset(&cfg, 0, sizeof(cfg));
        if (!hay0 && !hay1) {
            ESP_LOGW(TAG, "sin credenciales WiFi en NVS: cargarlas con cargar_credenciales.py por USB");
            vTaskDelay(pdMS_TO_TICKS(30000));
            continue;
        }
        if ((actual == 0 && !hay0) || (actual == 1 && !hay1)) {
            actual ^= 1;
        }
        xEventGroupClearBits(s_ev, BIT_IP | BIT_DESC | BIT_REVISAR);
        EventBits_t b = 0;
        if (actual == 0 && principal_sim_caida()) {
            ESP_LOGW(TAG, "SIM: red principal no disponible (intento fallido simulado)");
            vTaskDelay(pdMS_TO_TICKS(SIM_ESPERA_FALLO_MS));
        } else {
            cargar_red(actual, &cfg);
            ESP_LOGI(TAG, "conectando a la red %s", actual == 0 ? "principal" : "respaldo");
            esp_wifi_set_config(WIFI_IF_STA, &cfg);
            memset(&cfg, 0, sizeof(cfg));       /* no dejar la contrasena en la pila */
            esp_wifi_connect();
            b = xEventGroupWaitBits(s_ev, BIT_IP | BIT_DESC, pdFALSE, pdFALSE, pdMS_TO_TICKS(ESPERA_IP_MS));
        }
        if (b & BIT_IP) {
            fallos = 0;
            fallos_totales = 0;
            s_red_activa = actual == 0 ? AURA_RED_PRINCIPAL : AURA_RED_RESPALDO;
            ESP_LOGI(TAG, "conectado a la red %s", aura_wifi_red_nombre(s_red_activa));
            esp_wifi_set_ps(WIFI_PS_NONE);      /* el CSI necesita la radio siempre activa */
            aura_telemetria_hito("ip");
            notificar(true);
            xEventGroupClearBits(s_ev, BIT_DESC);
            int64_t prox_reintento = esp_timer_get_time() + REINTENTO_US;
            while (true) {
                if (!(xEventGroupGetBits(s_ev) & BIT_IP)) {
                    break;      /* desconexion ocurrida antes de empezar a esperar */
                }
                bool en_respaldo = actual == 1 && hay0;
                int64_t falta_us = prox_reintento - esp_timer_get_time();
                TickType_t espera = en_respaldo ? pdMS_TO_TICKS(falta_us > 0 ? falta_us / 1000 : 0) : portMAX_DELAY;
                b = xEventGroupWaitBits(s_ev, BIT_DESC | BIT_REVISAR, pdTRUE, pdFALSE, espera);
                if (b & BIT_DESC) {
                    break;
                }
                if (actual == 0 && principal_sim_caida()) {
                    ESP_LOGW(TAG, "SIM: se desconecta la red principal");
                    esp_wifi_disconnect();          /* llega BIT_DESC y se sale del bucle */
                    continue;
                }
                if (en_respaldo && esp_timer_get_time() >= prox_reintento) {
                    s_reintentos_principal++;
                    bool visible = principal_visible();
                    ESP_LOGI(TAG, "reintento de la red principal: %s", visible ? "disponible, se vuelve" : "no disponible");
                    web_serial_monitor_emitir("{\"type\":\"red\",\"evento\":\"reintento_principal\",\"disponible\":%s}",
                                              visible ? "true" : "false");
                    if (visible) {
                        actual = 0;
                        fallos = 0;
                        s_cambios++;
                        esp_wifi_disconnect();
                    }
                    prox_reintento = esp_timer_get_time() + REINTENTO_US;
                }
            }
            ESP_LOGW(TAG, "se perdio la red %s", aura_wifi_red_nombre(s_red_activa));
            s_red_activa = AURA_RED_NINGUNA;
            notificar(false);
            vTaskDelay(pdMS_TO_TICKS(1000));
            continue;
        }

        esp_wifi_disconnect();
        fallos++;
        fallos_totales++;
        if (fallos >= FALLOS_CAMBIO && ((actual == 0 && hay1) || (actual == 1 && hay0))) {
            actual ^= 1;
            fallos = 0;
            s_cambios++;
            ESP_LOGW(TAG, "paso a la red %s", actual == 0 ? "principal" : "respaldo");
            web_serial_monitor_emitir("{\"type\":\"red\",\"evento\":\"cambio\",\"a\":\"%s\"}",
                                      actual == 0 ? "principal" : "respaldo");
        }
        int espera_s = 1 << (fallos_totales < 5 ? fallos_totales : 5);   /* 2,4,8,16,32 */
        if (espera_s > 30) {
            espera_s = 30;
        }
        vTaskDelay(pdMS_TO_TICKS(espera_s * 1000));
    }
}

esp_err_t aura_wifi_iniciar(void)
{
    s_ev = xEventGroupCreate();
    ESP_ERROR_CHECK(esp_netif_init());
    s_netif = esp_netif_create_default_wifi_sta();
    esp_netif_set_hostname(s_netif, "aura-" CONFIG_AURA_SENSOR_ID);
    wifi_init_config_t wcfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&wcfg));
    ESP_ERROR_CHECK(esp_event_handler_register(WIFI_EVENT, WIFI_EVENT_STA_DISCONNECTED, manejador, NULL));
    ESP_ERROR_CHECK(esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, manejador, NULL));
    ESP_ERROR_CHECK(esp_wifi_set_storage(WIFI_STORAGE_RAM));
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_start());
    /* El driver WiFi imprime el SSID al conectar: se limita a advertencias. */
    esp_log_level_set("wifi", ESP_LOG_WARN);
    return xTaskCreate(tarea_wifi, "aura_wifi", AURA_PILA_WIFI, NULL, 3, NULL) == pdPASS ? ESP_OK : ESP_FAIL;
}

esp_err_t aura_wifi_registrar_cb(aura_wifi_cb_t cb)
{
    for (int i = 0; i < MAX_CB; i++) {
        if (!s_cbs[i]) {
            s_cbs[i] = cb;
            return ESP_OK;
        }
    }
    return ESP_ERR_NO_MEM;
}

void aura_wifi_sim_pierde_principal(uint32_t segundos)
{
    s_sim_principal_hasta_us = segundos ? esp_timer_get_time() + (int64_t)segundos * 1000000LL : 0;
    if (s_ev) {
        xEventGroupSetBits(s_ev, BIT_REVISAR);
    }
}

uint32_t aura_wifi_sim_restante_s(void)
{
    int64_t falta = s_sim_principal_hasta_us - esp_timer_get_time();
    return falta > 0 ? (uint32_t)(falta / 1000000LL) : 0;
}

uint32_t aura_wifi_reintentos_principal(void)
{
    return s_reintentos_principal;
}

bool aura_wifi_conectado(void)
{
    return s_ev && (xEventGroupGetBits(s_ev) & BIT_IP);
}

bool aura_wifi_ip(esp_netif_ip_info_t *out)
{
    return aura_wifi_conectado() && esp_netif_get_ip_info(s_netif, out) == ESP_OK;
}

aura_red_t aura_wifi_red_activa(void)
{
    return s_red_activa;
}

const char *aura_wifi_red_nombre(aura_red_t red)
{
    switch (red) {
    case AURA_RED_PRINCIPAL: return "principal";
    case AURA_RED_RESPALDO:  return "respaldo";
    default:                 return "ninguna";
    }
}

int aura_wifi_rssi(void)
{
    wifi_ap_record_t ap;
    return (aura_wifi_conectado() && esp_wifi_sta_get_ap_info(&ap) == ESP_OK) ? ap.rssi : 0;
}

uint32_t aura_wifi_cambios_red(void)
{
    return s_cambios;
}
