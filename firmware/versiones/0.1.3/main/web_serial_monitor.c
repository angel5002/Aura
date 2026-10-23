/*
 * SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 * AURA: modificado a partir de esp-csi/examples/esp-radar/wifi_sensing_demo/main/web_serial_monitor.c.
 *  - La salida pasa por aura_salida_hms_va() (USB sin bloquear + via local UDP) en vez de stdout.
 *  - La entrada se lee del driver USB Serial/JTAG que instala aura_salida; las lineas "HMSCMD ..." se
 *    encolan en aura_comandos (origen usb) y las "AURA ..." van a la consola de credenciales.
 *  - Los ack incluyen "origen" e "id"; el FSM se toma con aura_sensing_fsm_tomar() porque se recrea
 *    al cambiar de red.
 *  - Cada muestra del par alimenta aura_sensing_muestra() (estado, telemetria y nube).
 * El formato de los mensajes "sample", "config", "hello", "runtime" y "ack" se mantiene.
 */
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <inttypes.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "esp_log.h"
#include "esp_mac.h"
#include "esp_timer.h"
#include "sdkconfig.h"

#include "web_serial_monitor.h"
#include "aura_pilas.h"
#include "aura_salida.h"
#include "aura_comandos.h"
#include "aura_sensing.h"

#define WEB_SERIAL_COMMAND_PREFIX    "HMSCMD "
#define AURA_CONSOLE_PREFIX          "AURA "
#define WEB_SERIAL_TASK_STACK_SIZE   AURA_PILA_MONITOR
#define WEB_SERIAL_TASK_PRIORITY     4
#define WEB_SERIAL_LINE_BUF_SIZE     640
#define WEB_SERIAL_RX_POLL_BUF_SIZE  64
#define WEB_SERIAL_DEFAULT_PERIOD_MS 50

static const char *TAG = "web_serial_monitor";

typedef struct {
    bool initialized;
    bool stream_enabled;
    web_serial_monitor_peer_t peers[WEB_SERIAL_MONITOR_MAX_PEERS];
    size_t peer_num;
    uint32_t stream_period_ms;
    TaskHandle_t task;
    /* AURA: contexto del comando en ejecucion (lo usa send_ack) */
    const char *cmd_origen;
    const char *cmd_id;
    web_serial_monitor_resultado_t *cmd_res;
} web_serial_monitor_ctx_t;

static web_serial_monitor_ctx_t s_ctx = {0};

static const char *state_name(esp_wifi_sensing_fsm_process_state_t state)
{
    switch (state) {
    case ESP_WIFI_SENSING_FSM_PROCESS_IDLE:
        return "IDLE";
    case ESP_WIFI_SENSING_FSM_PROCESS_DEBOUNCE_ACTIVE:
        return "DEBOUNCE_ACTIVE";
    case ESP_WIFI_SENSING_FSM_PROCESS_ACTIVE:
        return "ACTIVE";
    case ESP_WIFI_SENSING_FSM_PROCESS_DEBOUNCE_INACTIVE:
        return "DEBOUNCE_INACTIVE";
    default:
        return "UNKNOWN";
    }
}

static const char *init_stage_name(esp_wifi_sensing_fsm_init_stage_t stage)
{
    switch (stage) {
    case ESP_WIFI_SENSING_FSM_INIT_STAGE_START:
        return "START";
    case ESP_WIFI_SENSING_FSM_INIT_STAGE_GOLD_FOUND:
        return "GOLD_FOUND";
    case ESP_WIFI_SENSING_FSM_INIT_STAGE_STABLE:
        return "STABLE";
    default:
        return "UNKNOWN";
    }
}

static const char *train_status_name(esp_wifi_sensing_fsm_train_status_t status)
{
    switch (status) {
    case ESP_WIFI_SENSING_FSM_TRAIN_STATUS_NONE:
        return "NONE";
    case ESP_WIFI_SENSING_FSM_TRAIN_STATUS_PROGRESS:
        return "PROGRESS";
    case ESP_WIFI_SENSING_FSM_TRAIN_STATUS_COMPLETE:
        return "COMPLETE";
    default:
        return "UNKNOWN";
    }
}

static const char *train_action_name(esp_wifi_sensing_fsm_train_action_t action)
{
    switch (action) {
    case ESP_WIFI_SENSING_FSM_TRAIN_ACTION_IDLE:
        return "IDLE";
    case ESP_WIFI_SENSING_FSM_TRAIN_ACTION_WAIT_BUFFER:
        return "WAIT_BUFFER";
    case ESP_WIFI_SENSING_FSM_TRAIN_ACTION_DISCARD_OUTLIER:
        return "DISCARD_OUTLIER";
    case ESP_WIFI_SENSING_FSM_TRAIN_ACTION_COLLECT_SAMPLE:
        return "COLLECT_SAMPLE";
    case ESP_WIFI_SENSING_FSM_TRAIN_ACTION_ACCUMULATE_BACKGROUND:
        return "ACCUMULATE_BACKGROUND";
    default:
        return "UNKNOWN";
    }
}

static const web_serial_monitor_peer_t *find_peer_by_name_or_mac(const char *token)
{
    if (!token) {
        return NULL;
    }
    for (size_t i = 0; i < s_ctx.peer_num; i++) {
        const web_serial_monitor_peer_t *peer = &s_ctx.peers[i];
        if (strcmp(token, peer->name) == 0) {
            return peer;
        }
        char mac_str[18] = {0};
        snprintf(mac_str, sizeof(mac_str), MACSTR, MAC2STR(peer->mac));
        if (strcasecmp(token, mac_str) == 0) {
            return peer;
        }
    }
    return NULL;
}

/* AURA: formatea el JSON (fmt puede terminar en "\n") y lo entrega a aura_salida_hms_va(). */
static void write_line_va(const char *fmt, va_list args)
{
    /* AURA: el buffer de la linea ya no va en la pila de quien llama (con 1400 B ahi, aura_tel quedaba
     * con 732 B libres, 23/10/2026): aura_salida formatea en un buffer estatico y escribe de una vez. */
    aura_salida_hms_va(fmt, args);
}

static void write_line(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
static void write_line(const char *fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    write_line_va(fmt, args);
    va_end(args);
}

void web_serial_monitor_emitir(const char *fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    write_line_va(fmt, args);
    va_end(args);
}

void web_serial_monitor_ack_origen(const char *cmd, bool ok, const char *detalle, const char *origen, const char *id)
{
    write_line("{\"type\":\"ack\",\"cmd\":\"%s\",\"ok\":%s,\"detail\":\"%s\",\"origen\":\"%s\",\"id\":\"%s\"}\n",
               cmd ? cmd : "", ok ? "true" : "false", detalle ? detalle : "", origen ? origen : "",
               id ? id : "");
}

static void send_error(const char *message)
{
    if (!message) {
        return;
    }
    write_line("{\"type\":\"error\",\"message\":\"%s\"}\n", message);
}

static void send_ack(const char *cmd, bool ok, const char *detail)
{
    /* AURA: guarda el resultado para quien ejecuto el comando y agrega origen/id */
    if (s_ctx.cmd_res) {
        s_ctx.cmd_res->ok = ok;
        snprintf(s_ctx.cmd_res->detalle, sizeof(s_ctx.cmd_res->detalle), "%s", detail ? detail : "");
    }
    web_serial_monitor_ack_origen(cmd, ok, detail, s_ctx.cmd_origen ? s_ctx.cmd_origen : "usb",
                                  s_ctx.cmd_id ? s_ctx.cmd_id : "");
}

static void send_runtime_config(esp_wifi_sensing_fsm_handle_t fsm)
{
    bool enabled = false;
    if (esp_wifi_sensing_fsm_get_amplitude_log_enabled(fsm, &enabled) != ESP_OK) {
        return;
    }
    write_line("{\"type\":\"runtime\",\"amplitude_log_enabled\":%s}\n", enabled ? "true" : "false");
}

static void send_hello(esp_wifi_sensing_fsm_handle_t fsm)
{
    char peers_json[256] = {0};
    size_t used = 0;
    for (size_t i = 0; i < s_ctx.peer_num; i++) {
        char item[48] = {0};
        snprintf(item, sizeof(item), "%s\"%s\"", (i == 0) ? "" : ",", s_ctx.peers[i].name);
        size_t item_len = strlen(item);
        if ((used + item_len + 1) >= sizeof(peers_json)) {
            break;
        }
        memcpy(peers_json + used, item, item_len);
        used += item_len;
        peers_json[used] = '\0';
    }

    bool enabled = false;
    (void)esp_wifi_sensing_fsm_get_amplitude_log_enabled(fsm, &enabled);
    write_line(
        "{\"type\":\"hello\",\"transport\":\"aura\",\"target\":\"%s\",\"stream_period_ms\":%" PRIu32 ",\"amplitude_log_enabled\":%s,\"peers\":[%s]}\n",
        CONFIG_IDF_TARGET,
        s_ctx.stream_period_ms,
        enabled ? "true" : "false",
        peers_json);
}

static void send_channel_config(esp_wifi_sensing_fsm_handle_t fsm, const web_serial_monitor_peer_t *peer)
{
    if (!peer) {
        return;
    }
    esp_wifi_sensing_fsm_channel_config_t cfg = {0};
    if (esp_wifi_sensing_fsm_get_channel_config(fsm, peer->mac, &cfg) != ESP_OK) {
        return;
    }
    write_line(
        "{\"type\":\"config\",\"peer\":\"%s\",\"mac\":\"" MACSTR "\",\"sensitivity\":%.6f,"
        "\"presence_sensitivity\":%.6f,"
        "\"active_jitter_min\":%.6f,"
        "\"active_filter_ms\":%" PRIu32 "}\n",
        peer->name,
        MAC2STR(peer->mac),
        cfg.sensitivity,
        cfg.presence_sensitivity,
        cfg.active_jitter_min,
        cfg.active_filter_ms);
}

static void send_all_configs(esp_wifi_sensing_fsm_handle_t fsm)
{
    for (size_t i = 0; i < s_ctx.peer_num; i++) {
        send_channel_config(fsm, &s_ctx.peers[i]);
    }
}

static void send_channel_sample(esp_wifi_sensing_fsm_handle_t fsm, const web_serial_monitor_peer_t *peer)
{
    if (!peer) {
        return;
    }
    esp_wifi_sensing_fsm_channel_diag_t diag = {0};
    if (esp_wifi_sensing_fsm_get_channel_diag(fsm, peer->mac, &diag) != ESP_OK) {
        return;
    }
    esp_wifi_sensing_fsm_state_t motion_state = ESP_WIFI_SENSING_FSM_STATE_INACTIVE;
    if (esp_wifi_sensing_fsm_get_state(fsm, peer->mac, &motion_state) != ESP_OK) {
        return;
    }
    uint64_t ts_ms = (uint64_t)(esp_timer_get_time() / 1000ULL);

    write_line(
        "{\"type\":\"sample\",\"ts_ms\":%" PRIu64 ",\"peer\":\"%s\",\"mac\":\"" MACSTR "\","
        "\"motion_status\":%s,\"motion_state\":%d,"
        "\"jitter_value\":%.6f,"
        "\"wander_value\":%.6f,"
        "\"presence_ready\":%s,\"presence_wander_average\":%.6f,\"presence_someone_threshold\":%.6f,\"presence_someone_status\":%s,"
        "\"train_wander_threshold\":%.6f,\"train_jitter_threshold\":%.6f,\"train_thresholds_valid\":%s,"
        "\"train_status\":%d,\"train_status_name\":\"%s\",\"train_last_action\":%d,\"train_last_action_name\":\"%s\","
        "\"train_sample_count\":%" PRIu32 ",\"train_background_count\":%" PRIu32 ","
        "\"train_background_avg\":%.6f,\"train_last_basis_wander\":%.6f,"
        "\"smooth_scaled\":%" PRIu32 ",\"enter_level_scaled\":%" PRIu32 ",\"exit_level_scaled\":%" PRIu32 ","
        "\"state\":%d,\"state_name\":\"%s\",\"init_stage\":%d,\"init_stage_name\":\"%s\"}\n",
        ts_ms,
        peer->name,
        MAC2STR(peer->mac),
        (motion_state == ESP_WIFI_SENSING_FSM_STATE_ACTIVE) ? "true" : "false",
        (int)motion_state,
        diag.jitter_value,
        diag.wander_value,
        diag.presence_ready ? "true" : "false",
        diag.presence_wander_average,
        diag.presence_someone_threshold,
        diag.presence_someone_status ? "true" : "false",
        diag.train_wander_threshold,
        diag.train_jitter_threshold,
        diag.train_thresholds_valid ? "true" : "false",
        (int)diag.train_status,
        train_status_name(diag.train_status),
        (int)diag.train_last_action,
        train_action_name(diag.train_last_action),
        diag.train_sample_count,
        diag.train_background_count,
        diag.train_background_avg,
        diag.train_last_basis_wander,
        diag.smooth_scaled,
        diag.enter_level_scaled,
        diag.exit_level_scaled,
        (int)diag.state,
        state_name(diag.state),
        (int)diag.init_stage,
        init_stage_name(diag.init_stage));

    /* AURA: alimentar estado, telemetria y bloques de la nube */
    aura_sensing_muestra(ts_ms, motion_state == ESP_WIFI_SENSING_FSM_STATE_ACTIVE,
                         diag.presence_someone_status, diag.presence_ready, diag.train_thresholds_valid,
                         diag.jitter_value, diag.wander_value,
                         diag.init_stage == ESP_WIFI_SENSING_FSM_INIT_STAGE_STABLE);
}

static void apply_cfg_value(esp_wifi_sensing_fsm_channel_config_t *cfg, const char *key, const char *value)
{
    if (!cfg || !key || !value) {
        return;
    }
    if (strcmp(key, "motion_sensitivity") == 0) {
        cfg->sensitivity = strtof(value, NULL);
    } else if (strcmp(key, "presence_sensitivity") == 0) {
        cfg->presence_sensitivity = strtof(value, NULL);
    } else if (strcmp(key, "active_jitter_min") == 0) {
        cfg->active_jitter_min = strtof(value, NULL);
    } else if (strcmp(key, "active_filter_ms") == 0) {
        cfg->active_filter_ms = (uint32_t)strtoul(value, NULL, 10);
    }
}

static void handle_set_cfg(esp_wifi_sensing_fsm_handle_t fsm, char *args)
{
    char *saveptr = NULL;
    char *peer_token = strtok_r(args, " ", &saveptr);
    if (!peer_token) {
        send_ack("SET_CFG", false, "missing peer");
        return;
    }
    const web_serial_monitor_peer_t *peer = find_peer_by_name_or_mac(peer_token);
    if (!peer) {
        send_ack("SET_CFG", false, "peer not found");
        return;
    }
    esp_wifi_sensing_fsm_channel_config_t cfg = {0};
    if (esp_wifi_sensing_fsm_get_channel_config(fsm, peer->mac, &cfg) != ESP_OK) {
        send_ack("SET_CFG", false, "get cfg failed");
        return;
    }
    char *token = NULL;
    while ((token = strtok_r(NULL, " ", &saveptr)) != NULL) {
        char *sep = strchr(token, '=');
        if (!sep) {
            continue;
        }
        *sep = '\0';
        apply_cfg_value(&cfg, token, sep + 1);
    }
    if (esp_wifi_sensing_fsm_set_channel_config(fsm, peer->mac, &cfg) != ESP_OK) {
        send_ack("SET_CFG", false, "set cfg failed");
        return;
    }
    send_ack("SET_CFG", true, peer->name);
    send_channel_config(fsm, peer);
}

static const char *arg_after(const char *cmd, size_t prefix_len)
{
    const char *arg = cmd + prefix_len;
    while (*arg == ' ') {
        arg++;
    }
    return arg;
}

/* cmd = texto sin el prefijo "HMSCMD " */
static void handle_command(char *cmd, esp_wifi_sensing_fsm_handle_t fsm)
{
    if (!fsm) {
        send_ack(cmd, false, "detector no iniciado (sin red)");
        return;
    }
    if (strcmp(cmd, "HELLO") == 0) {
        send_hello(fsm);
        send_runtime_config(fsm);
        send_all_configs(fsm);
        send_ack("HELLO", true, "hello");
        return;
    }
    if (strcmp(cmd, "START_STREAM") == 0) {
        s_ctx.stream_enabled = true;
        send_ack("START_STREAM", true, "stream enabled");
        return;
    }
    if (strcmp(cmd, "STOP_STREAM") == 0) {
        s_ctx.stream_enabled = false;
        send_ack("STOP_STREAM", true, "stream disabled");
        return;
    }
    if (strcmp(cmd, "FSM_START") == 0) {
        esp_err_t err = esp_wifi_sensing_fsm_control(fsm, ESP_WIFI_SENSING_FSM_CTRL_START, NULL);
        send_ack("FSM_START", err == ESP_OK, esp_err_to_name(err));
        return;
    }
    if (strcmp(cmd, "FSM_STOP") == 0) {
        esp_err_t err = esp_wifi_sensing_fsm_control(fsm, ESP_WIFI_SENSING_FSM_CTRL_STOP, NULL);
        send_ack("FSM_STOP", err == ESP_OK, esp_err_to_name(err));
        return;
    }
    if (strcmp(cmd, "RESET_BASELINE") == 0) {
        esp_err_t err = esp_wifi_sensing_fsm_control(fsm, ESP_WIFI_SENSING_FSM_CTRL_RESET_BASELINE, NULL);
        send_ack("RESET_BASELINE", err == ESP_OK, esp_err_to_name(err));
        return;
    }
    if (strncmp(cmd, "GET_CFG", 7) == 0) {
        const char *arg = arg_after(cmd, 7);
        if (*arg == '\0' || strcmp(arg, "ALL") == 0) {
            send_all_configs(fsm);
            send_ack("GET_CFG", true, "all");
            return;
        }
        const web_serial_monitor_peer_t *peer = find_peer_by_name_or_mac(arg);
        if (!peer) {
            send_ack("GET_CFG", false, "peer not found");
            return;
        }
        send_channel_config(fsm, peer);
        send_ack("GET_CFG", true, peer->name);
        return;
    }
    if (strcmp(cmd, "GET_RUNTIME") == 0) {
        send_runtime_config(fsm);
        send_ack("GET_RUNTIME", true, "runtime");
        return;
    }
    if (strncmp(cmd, "SET_AMPLITUDE_LOG ", 18) == 0) {
        const char *value = cmd + 18;
        bool enabled = false;
        if ((strcmp(value, "1") == 0) || (strcasecmp(value, "true") == 0) || (strcasecmp(value, "on") == 0)) {
            enabled = true;
        } else if ((strcmp(value, "0") == 0) || (strcasecmp(value, "false") == 0) || (strcasecmp(value, "off") == 0)) {
            enabled = false;
        } else {
            send_ack("SET_AMPLITUDE_LOG", false, "invalid value");
            return;
        }
        esp_err_t err = esp_wifi_sensing_fsm_set_amplitude_log_enabled(fsm, enabled);
        send_ack("SET_AMPLITUDE_LOG", err == ESP_OK, esp_err_to_name(err));
        if (err == ESP_OK) {
            send_runtime_config(fsm);
            send_hello(fsm);
        }
        return;
    }
    if (strncmp(cmd, "SET_CFG ", 8) == 0) {
        handle_set_cfg(fsm, cmd + 8);
        return;
    }
    if (strncmp(cmd, "TRAIN_START ", 12) == 0) {
        const web_serial_monitor_peer_t *peer = find_peer_by_name_or_mac(arg_after(cmd, 12));
        if (!peer) {
            send_ack("TRAIN_START", false, "peer not found");
            return;
        }
        esp_err_t err = esp_wifi_sensing_fsm_train_start(fsm, peer->mac);
        send_ack("TRAIN_START", err == ESP_OK, esp_err_to_name(err));
        return;
    }
    if (strncmp(cmd, "TRAIN_STOP ", 11) == 0) {
        const web_serial_monitor_peer_t *peer = find_peer_by_name_or_mac(arg_after(cmd, 11));
        if (!peer) {
            send_ack("TRAIN_STOP", false, "peer not found");
            return;
        }
        float wander_th = 0.0f;
        float jitter_th = 0.0f;
        esp_err_t err = esp_wifi_sensing_fsm_train_stop(fsm, peer->mac, &wander_th, &jitter_th);
        if (err == ESP_OK) {
            char detail[96] = {0};
            snprintf(detail, sizeof(detail), "%s wander=%.4f jitter=%.4f", peer->name, wander_th, jitter_th);
            send_ack("TRAIN_STOP", true, detail);
        } else {
            send_ack("TRAIN_STOP", false, esp_err_to_name(err));
        }
        return;
    }
    if (strncmp(cmd, "TRAIN_REMOVE ", 13) == 0) {
        const web_serial_monitor_peer_t *peer = find_peer_by_name_or_mac(arg_after(cmd, 13));
        if (!peer) {
            send_ack("TRAIN_REMOVE", false, "peer not found");
            return;
        }
        esp_err_t err = esp_wifi_sensing_fsm_train_remove(fsm, peer->mac);
        send_ack("TRAIN_REMOVE", err == ESP_OK, esp_err_to_name(err));
        return;
    }
    send_error("unknown command");
    if (s_ctx.cmd_res) {
        s_ctx.cmd_res->ok = false;
        snprintf(s_ctx.cmd_res->detalle, sizeof(s_ctx.cmd_res->detalle), "unknown command");
    }
}

void web_serial_monitor_ejecutar(const char *texto, const char *origen, const char *id,
                                 web_serial_monitor_resultado_t *res)
{
    char cmd[WEB_SERIAL_LINE_BUF_SIZE];
    snprintf(cmd, sizeof(cmd), "%s", texto);
    esp_wifi_sensing_fsm_handle_t fsm = aura_sensing_fsm_tomar();
    s_ctx.cmd_origen = origen;
    s_ctx.cmd_id = id;
    s_ctx.cmd_res = res;
    handle_command(cmd, fsm);
    s_ctx.cmd_origen = NULL;
    s_ctx.cmd_id = NULL;
    s_ctx.cmd_res = NULL;
    aura_sensing_fsm_soltar();
    /* SET_AMPLITUDE_LOG cambia la configuracion de esp-radar: re-enganchar la captura de CSI */
    if (res && res->ok && strncmp(texto, "SET_AMPLITUDE_LOG", 17) == 0) {
        aura_sensing_reenganchar_csi();
    }
}

/* AURA: lineas que llegan por USB */
static void process_line(char *line)
{
    size_t n = strlen(line);
    if (strncmp(line, WEB_SERIAL_COMMAND_PREFIX, strlen(WEB_SERIAL_COMMAND_PREFIX)) == 0) {
        aura_comandos_encolar(AURA_ORIGEN_USB, "", line + strlen(WEB_SERIAL_COMMAND_PREFIX));
    } else if (strncmp(line, AURA_CONSOLE_PREFIX, strlen(AURA_CONSOLE_PREFIX)) == 0) {
        aura_comandos_consola(line);
    }
    memset(line, 0, n);   /* puede contener credenciales en hexadecimal */
}

static void poll_rx(void)
{
    static char line_buf[WEB_SERIAL_LINE_BUF_SIZE] = {0};
    static size_t line_len = 0;
    uint8_t rx_buf[WEB_SERIAL_RX_POLL_BUF_SIZE];
    int n = aura_salida_leer_usb(rx_buf, sizeof(rx_buf));
    for (int i = 0; i < n; i++) {
        char ch = (char)rx_buf[i];
        if (ch == '\r') {
            continue;
        }
        if (ch == '\n') {
            line_buf[line_len] = '\0';
            process_line(line_buf);
            line_len = 0;
            continue;
        }
        if (line_len < (WEB_SERIAL_LINE_BUF_SIZE - 1)) {
            line_buf[line_len++] = ch;
        } else {
            line_len = 0;
        }
    }
    memset(rx_buf, 0, sizeof(rx_buf));
}

static void web_serial_monitor_task(void *arg)
{
    (void)arg;
    int64_t last_stream_us = 0;
    bool hello_sent = false;

    while (true) {
        poll_rx();

        esp_wifi_sensing_fsm_handle_t fsm = aura_sensing_fsm_tomar();
        if (fsm) {
            if (!hello_sent) {
                send_hello(fsm);
                send_runtime_config(fsm);
                send_all_configs(fsm);
                hello_sent = true;
            }
            int64_t now_us = esp_timer_get_time();
            if (s_ctx.stream_enabled &&
                    (last_stream_us == 0 || (now_us - last_stream_us) >= ((int64_t)s_ctx.stream_period_ms * 1000LL))) {
                last_stream_us = now_us;
                for (size_t i = 0; i < s_ctx.peer_num; i++) {
                    send_channel_sample(fsm, &s_ctx.peers[i]);
                }
            }
        } else {
            hello_sent = false;     /* al recrearse el detector se vuelve a enviar hello/config */
        }
        aura_sensing_fsm_soltar();

        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

void web_serial_monitor_actualizar_peer(size_t indice, const uint8_t mac[6])
{
    if (indice < s_ctx.peer_num) {
        memcpy(s_ctx.peers[indice].mac, mac, 6);
    }
}

esp_err_t web_serial_monitor_init(const web_serial_monitor_config_t *config)
{
    if (!config || !config->peers || config->peer_num == 0 ||
            config->peer_num > WEB_SERIAL_MONITOR_MAX_PEERS) {
        return ESP_ERR_INVALID_ARG;
    }
    if (s_ctx.initialized) {
        return ESP_ERR_INVALID_STATE;
    }
    memset(&s_ctx, 0, sizeof(s_ctx));
    s_ctx.initialized = true;
    s_ctx.stream_enabled = true;
    s_ctx.peer_num = config->peer_num;
    s_ctx.stream_period_ms = (config->stream_period_ms > 0) ? config->stream_period_ms : WEB_SERIAL_DEFAULT_PERIOD_MS;
    memcpy(s_ctx.peers, config->peers, config->peer_num * sizeof(web_serial_monitor_peer_t));

    BaseType_t ok = xTaskCreate(web_serial_monitor_task,
                                "web_serial_monitor",
                                WEB_SERIAL_TASK_STACK_SIZE,
                                NULL,
                                WEB_SERIAL_TASK_PRIORITY,
                                &s_ctx.task);
    if (ok != pdPASS) {
        memset(&s_ctx, 0, sizeof(s_ctx));
        return ESP_FAIL;
    }
    ESP_LOGI(TAG, "monitor iniciado: salida USB + via local, periodo %" PRIu32 " ms", s_ctx.stream_period_ms);
    return ESP_OK;
}
