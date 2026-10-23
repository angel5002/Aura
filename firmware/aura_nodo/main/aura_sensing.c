/*
 * AURA - deteccion con esp_wifi_sensing + captura de CSI crudo para la via local y la nube.
 */
#include <math.h>
#include <string.h>
#include <inttypes.h>

#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "esp_check.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_mac.h"
#include "esp_radar.h"

#include "aura_sensing.h"
#include "aura_wifi.h"
#include "aura_local.h"
#include "aura_tiempo.h"
#include "aura_telemetria.h"
#include "led_control.h"
#include "web_serial_monitor.h"

static const char *TAG = "aura_sensing";

static SemaphoreHandle_t s_mx;                 /* protege s_fsm */
static esp_wifi_sensing_fsm_handle_t s_fsm;
static uint8_t s_bssid[6];
static uint32_t s_gw;
static uint32_t s_recreaciones;
static volatile uint32_t s_csi_total;
static volatile bool s_hito_estable_pendiente;  /* emitir "memoria/detector_estable" al salir de CALIBRANDO */

/* estado derivado */
static portMUX_TYPE s_mux_estado = portMUX_INITIALIZER_UNLOCKED;
static aura_estado_info_t s_estado = { .estado = AURA_ESTADO_CALIBRANDO };
static int64_t s_ultimo_mov_us;

/* bloque /crudo en construccion */
static portMUX_TYPE s_mux_bloque = portMUX_INITIALIZER_UNLOCKED;
static aura_bloque_t s_bloque;
static double s_amp_suma[AURA_BLOQUE_MAX_SUBP], s_amp_suma2[AURA_BLOQUE_MAX_SUBP];

/* ---------------- captura de CSI ---------------- */

static void acumular_amplitud(const wifi_csi_filtered_info_t *info)
{
    /* valid_data: subportadoras validas (copiadas del buffer crudo por esp-radar) y multiplicadas en
     * el lugar por el factor de esp_csi_gain_ctrl. Pares de valores por subportadora. */
    bool es16 = info->data_type == WIFI_CSI_DATA_TYPE_INT16;
    int valores = es16 ? info->valid_len / 2 : info->valid_len;
    int subp = valores / 2;
    if (subp > AURA_BLOQUE_MAX_SUBP) {
        subp = AURA_BLOQUE_MAX_SUBP;
    }
    float amp[AURA_BLOQUE_MAX_SUBP];
    for (int k = 0; k < subp; k++) {
        float a = es16 ? info->valid_data_i16[2 * k] : info->valid_data[2 * k];
        float b = es16 ? info->valid_data_i16[2 * k + 1] : info->valid_data[2 * k + 1];
        amp[k] = sqrtf(a * a + b * b);
    }
    portENTER_CRITICAL(&s_mux_bloque);
    if (s_bloque.n_subp == 0 || s_bloque.n_subp == subp) {
        s_bloque.n_subp = subp;
        for (int k = 0; k < subp; k++) {
            s_amp_suma[k] += amp[k];
            s_amp_suma2[k] += (double)amp[k] * amp[k];
        }
        s_bloque.n_csi++;
    }
    portEXIT_CRITICAL(&s_mux_bloque);
}

/* Corre en la tarea del WiFi: solo copiar y encolar, sin bloquear. */
static void csi_capturado(void *ctx, const wifi_csi_filtered_info_t *info)
{
    (void)ctx;
    if (!info || !info->raw_data) {
        return;
    }
    s_csi_total++;
    acumular_amplitud(info);

    size_t len = sizeof(aura_csi_registro_t) + info->raw_len + info->valid_len;
    aura_csi_registro_t *r = aura_local_reservar(AURA_LOCAL_TIPO_CSI, len);
    if (!r) {
        return;
    }
    r->seq_id = info->seq_id;
    r->t_us = aura_tiempo_unix_us();
    r->rx_ts_us = info->rx_ctrl_info.timestamp;
    r->rssi = info->rx_ctrl_info.rssi;
    r->noise_floor = info->rx_ctrl_info.noise_floor;
    r->channel = info->rx_ctrl_info.channel;
    r->agc_gain = info->rx_ctrl_info.agc_gain;
    r->fft_gain = info->rx_ctrl_info.fft_gain;
    r->rate = info->rx_ctrl_info.rate;
    r->rx_format = (uint8_t)info->rx_ctrl_info.rx_format;
    r->cwb = info->rx_ctrl_info.cwb;
    r->data_type = (uint8_t)info->data_type;
    r->compensacion = info->rx_gain_compensation;
    r->raw_len = info->raw_len;
    r->valid_len = info->valid_len;
    memcpy(r->datos, info->raw_data, info->raw_len);
    memcpy(r->datos + info->raw_len, info->valid_data, info->valid_len);
    aura_local_confirmar(r);
}

static void enganchar_csi(void)
{
    esp_radar_config_t cfg = ESP_RADAR_CONFIG_DEFAULT();
    if (esp_radar_get_config(&cfg) != ESP_OK) {
        ESP_LOGW(TAG, "no se pudo leer la configuracion de esp-radar");
        return;
    }
    if (cfg.csi_config.csi_filtered_cb == csi_capturado) {
        return;
    }
    cfg.csi_config.csi_filtered_cb = csi_capturado;
    cfg.csi_config.csi_filtered_cb_ctx = NULL;
    esp_err_t err = esp_radar_change_config(&cfg);
    ESP_LOGI(TAG, "captura de CSI crudo %s", err == ESP_OK ? "enganchada" : "NO enganchada");
}

void aura_sensing_reenganchar_csi(void)
{
    if (!s_mx) {
        return;
    }
    xSemaphoreTakeRecursive(s_mx, portMAX_DELAY);
    if (s_fsm) {
        enganchar_csi();
    }
    xSemaphoreGiveRecursive(s_mx);
}

/* ---------------- FSM ---------------- */

static void evento_movimiento(esp_wifi_sensing_fsm_handle_t handle, const uint8_t peer_mac[6],
                              esp_wifi_sensing_fsm_event_t event, uint32_t data, void *usr)
{
    (void)handle;
    (void)peer_mac;
    (void)data;
    (void)usr;
    if (event == ESP_WIFI_SENSING_FSM_EVENT_ACTIVE) {
        led_notify_ap_active();
    } else if (event == ESP_WIFI_SENSING_FSM_EVENT_INACTIVE) {
        led_notify_ap_inactive();
    }
}

static esp_err_t crear_fsm(const uint8_t bssid[6])
{
    esp_wifi_sensing_fsm_config_t cfg = DEFAULT_ESP_WIFI_SENSING_FSM_CONFIG();
    cfg.max_channel_num = 1;
    esp_wifi_sensing_fsm_handle_t fsm = NULL;
    ESP_RETURN_ON_ERROR(esp_wifi_sensing_fsm_create(&cfg, &fsm), TAG, "fsm_create");
    esp_err_t err = esp_wifi_sensing_fsm_add_channel(fsm, bssid);
    if (err == ESP_OK) {
        esp_wifi_sensing_fsm_register_event_cb(fsm, ESP_WIFI_SENSING_FSM_EVENT_ACTIVE, evento_movimiento, NULL);
        esp_wifi_sensing_fsm_register_event_cb(fsm, ESP_WIFI_SENSING_FSM_EVENT_INACTIVE, evento_movimiento, NULL);
        err = esp_wifi_sensing_fsm_control(fsm, ESP_WIFI_SENSING_FSM_CTRL_START, NULL);
    }
    if (err != ESP_OK) {
        esp_wifi_sensing_fsm_delete(fsm);
        return err;
    }
    if (esp_wifi_sensing_fsm_ping_router_start(fsm) != ESP_OK) {
        ESP_LOGW(TAG, "no se pudo iniciar el ping al router");
    }
    s_fsm = fsm;
    memcpy(s_bssid, bssid, 6);
    enganchar_csi();
    return ESP_OK;
}

static void reiniciar_estado(void)
{
    portENTER_CRITICAL(&s_mux_estado);
    s_estado.estado = AURA_ESTADO_CALIBRANDO;
    s_estado.movimiento = false;
    s_estado.presencia = false;
    s_estado.presencia_entrenada = false;
    s_estado.alerta_quietud = false;
    s_estado.desde_us = esp_timer_get_time();
    portEXIT_CRITICAL(&s_mux_estado);
}

static void al_cambiar_red(bool conectado, const uint8_t bssid[6], uint32_t gw)
{
    if (!conectado) {
        led_set_wifi_connected(false);
        return;
    }
    led_set_wifi_connected(true);
    xSemaphoreTakeRecursive(s_mx, portMAX_DELAY);
    bool misma_red = s_fsm && memcmp(bssid, s_bssid, 6) == 0 && gw == s_gw;
    if (!misma_red) {
        if (s_fsm) {
            ESP_LOGW(TAG, "cambio de AP o de puerta de enlace: se recrea el detector (recalibra; "
                          "el entrenamiento de presencia se pierde)");
            esp_wifi_sensing_fsm_delete(s_fsm);
            s_fsm = NULL;
            s_recreaciones++;
        }
        s_gw = gw;
        reiniciar_estado();
        if (crear_fsm(bssid) == ESP_OK) {
            ESP_LOGI(TAG, "detector iniciado con el AP " MACSTR, MAC2STR(bssid));
            aura_telemetria_hito("detector_creado");
            s_hito_estable_pendiente = true;
            /* el monitor existe desde el arranque (app_main): aqui solo se actualiza la MAC del par AP */
            web_serial_monitor_actualizar_peer(0, bssid);
        } else {
            ESP_LOGE(TAG, "no se pudo iniciar el detector");
        }
    } else if (esp_wifi_sensing_fsm_ping_router_start(s_fsm) != ESP_OK) {
        /* misma red: el ping puede seguir activo; un error aqui no es grave */
        ESP_LOGD(TAG, "ping ya activo");
    }
    xSemaphoreGiveRecursive(s_mx);
}

esp_err_t aura_sensing_iniciar(void)
{
    s_mx = xSemaphoreCreateRecursiveMutex();
    if (!s_mx) {
        return ESP_ERR_NO_MEM;
    }
    reiniciar_estado();
    return aura_wifi_registrar_cb(al_cambiar_red);
}

esp_wifi_sensing_fsm_handle_t aura_sensing_fsm_tomar(void)
{
    /* Defensa: si se llama antes de aura_sensing_iniciar() no hay mutex ni detector. */
    if (!s_mx) {
        return NULL;
    }
    xSemaphoreTakeRecursive(s_mx, portMAX_DELAY);
    return s_fsm;
}

void aura_sensing_fsm_soltar(void)
{
    if (s_mx) {
        xSemaphoreGiveRecursive(s_mx);
    }
}

bool aura_sensing_activo(void)
{
    return s_fsm != NULL;
}

/* ---------------- estado derivado ---------------- */

const char *aura_sensing_estado_nombre(aura_estado_t e)
{
    switch (e) {
    case AURA_ESTADO_CALIBRANDO:              return "CALIBRANDO";
    case AURA_ESTADO_MOVIMIENTO:              return "MOVIMIENTO";
    case AURA_ESTADO_PRESENCIA_QUIETA:        return "PRESENCIA_QUIETA";
    case AURA_ESTADO_VACIA:                   return "VACIA";
    case AURA_ESTADO_SIN_PRESENCIA_ENTRENADA: return "SIN_MOVIMIENTO";
    default:                                  return "?";
    }
}

void aura_sensing_muestra(uint64_t ts_ms, bool movimiento, bool presencia, bool presencia_lista,
                          bool presencia_entrenada, float jitter, float wander, bool estable)
{
    (void)wander;
    int64_t ahora = esp_timer_get_time();
    aura_telemetria_muestra(ts_ms);

    if (movimiento) {
        s_ultimo_mov_us = ahora;
    }
    bool mov_ret = s_ultimo_mov_us && (ahora - s_ultimo_mov_us) < (int64_t)CONFIG_AURA_RETENCION_MOV_S * 1000000LL;
    bool pres_valida = presencia_entrenada && presencia_lista;

    aura_estado_t nuevo;
    if (!estable) {
        nuevo = AURA_ESTADO_CALIBRANDO;
    } else if (mov_ret) {
        nuevo = AURA_ESTADO_MOVIMIENTO;
    } else if (!pres_valida) {
        nuevo = AURA_ESTADO_SIN_PRESENCIA_ENTRENADA;
    } else if (presencia) {
        nuevo = AURA_ESTADO_PRESENCIA_QUIETA;
    } else {
        nuevo = AURA_ESTADO_VACIA;
    }

    portENTER_CRITICAL(&s_mux_estado);
    if (nuevo != s_estado.estado) {
        s_estado.estado = nuevo;
        s_estado.desde_us = ahora;
        s_estado.cambios++;
    }
    s_estado.movimiento = mov_ret;
    s_estado.presencia = pres_valida && presencia;
    /* "entrenada" = presencia UTILIZABLE (umbrales de entrenamiento validos y presencia lista). Es la
     * misma condicion que permite los estados VACIA y PRESENCIA_QUIETA; sin ella -> "no_disponible". */
    s_estado.presencia_entrenada = pres_valida;
    s_estado.alerta_quietud = (nuevo == AURA_ESTADO_PRESENCIA_QUIETA) &&
                              (ahora - s_estado.desde_us) >= (int64_t)CONFIG_AURA_QUIETUD_MIN * 60000000LL;
    portEXIT_CRITICAL(&s_mux_estado);
    if (estable && s_hito_estable_pendiente) {
        s_hito_estable_pendiente = false;
        aura_telemetria_hito("detector_estable");
    }

    portENTER_CRITICAL(&s_mux_bloque);
    if (s_bloque.n_jitter < AURA_BLOQUE_MAX_MUESTRAS) {
        float j = jitter * 10000.0f;
        s_bloque.jitter_x1e4[s_bloque.n_jitter++] = (uint16_t)(j < 0 ? 0 : (j > 65535 ? 65535 : j));
    }
    if (mov_ret) {
        s_bloque.n_mov++;
    }
    if (pres_valida && presencia) {
        s_bloque.n_pres++;
    }
    portEXIT_CRITICAL(&s_mux_bloque);
}

void aura_sensing_estado(aura_estado_info_t *out)
{
    portENTER_CRITICAL(&s_mux_estado);
    *out = s_estado;
    portEXIT_CRITICAL(&s_mux_estado);
}

void aura_sensing_tomar_bloque(aura_bloque_t *out)
{
    int64_t ahora = aura_tiempo_unix_us();
    portENTER_CRITICAL(&s_mux_bloque);
    *out = s_bloque;
    out->t1_us = ahora;
    for (int k = 0; k < out->n_subp; k++) {
        if (out->n_csi > 0) {
            double m = s_amp_suma[k] / out->n_csi;
            double v = s_amp_suma2[k] / out->n_csi - m * m;
            out->amp_media[k] = (float)m;
            out->amp_desv[k] = (float)(v > 0 ? sqrt(v) : 0);
        }
    }
    memset(&s_bloque, 0, sizeof(s_bloque));
    memset(s_amp_suma, 0, sizeof(s_amp_suma));
    memset(s_amp_suma2, 0, sizeof(s_amp_suma2));
    s_bloque.t0_us = ahora;
    portEXIT_CRITICAL(&s_mux_bloque);
}

void aura_sensing_stats(aura_sensing_stats_t *out)
{
    out->csi_total = s_csi_total;
    out->recreaciones = s_recreaciones;
}
