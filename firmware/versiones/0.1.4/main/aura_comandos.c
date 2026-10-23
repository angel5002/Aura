/*
 * AURA - cola unica de comandos y autenticacion de la via local.
 */
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_ota_ops.h"
#include "esp_app_desc.h"
#include "mbedtls/md.h"

#include "aura_comandos.h"
#include "aura_pilas.h"
#include "aura_config.h"
#include "aura_tiempo.h"
#include "aura_wifi.h"
#include "aura_nube.h"
#include "web_serial_monitor.h"

static const char *TAG = "aura_cmd";

typedef struct {
    aura_origen_t origen;
    char id[32];
    char texto[192];
} item_cmd_t;

static QueueHandle_t s_cola;
static aura_cmd_cb_t s_al_terminar;
static int s_bloqueo_entrenamiento = -1;          /* origen que tiene un entrenamiento en curso */
static uint64_t s_ultimo_ctr;
static portMUX_TYPE s_mux_ctr = portMUX_INITIALIZER_UNLOCKED;

/* Comandos que se aceptan por la via local y la nube (whitelist). */
static const char *const PERMITIDOS[] = {
    "RESET_BASELINE", "TRAIN_START", "TRAIN_STOP", "SET_CFG", "SET_AMPLITUDE_LOG", "GET_CFG",
};

const char *aura_comandos_origen_nombre(aura_origen_t o)
{
    switch (o) {
    case AURA_ORIGEN_USB:   return "usb";
    case AURA_ORIGEN_LOCAL: return "local";
    case AURA_ORIGEN_NUBE:  return "nube";
    default:                return "?";
    }
}

static void primer_token(const char *texto, char *out, size_t len)
{
    size_t i = 0;
    while (texto[i] && texto[i] != ' ' && i + 1 < len) {
        out[i] = texto[i];
        i++;
    }
    out[i] = '\0';
}

static bool permitido(const char *cmd)
{
    for (size_t i = 0; i < sizeof(PERMITIDOS) / sizeof(PERMITIDOS[0]); i++) {
        if (strcmp(cmd, PERMITIDOS[i]) == 0) {
            return true;
        }
    }
    return false;
}

static void publicar(const aura_cmd_resultado_t *r)
{
    web_serial_monitor_ack_origen(r->cmd, r->ok, r->detalle, aura_comandos_origen_nombre(r->origen), r->id);
    if (s_al_terminar) {
        s_al_terminar(r);
    }
}

static volatile uint32_t s_rechazados;

uint32_t aura_comandos_rechazados(void)
{
    return s_rechazados;
}

void aura_comandos_rechazo(aura_origen_t origen, const char *id, const char *motivo)
{
    s_rechazados++;
    aura_cmd_resultado_t r = { .ok = false, .origen = origen };
    snprintf(r.id, sizeof(r.id), "%s", id ? id : "");
    snprintf(r.cmd, sizeof(r.cmd), "RECHAZADO");
    snprintf(r.detalle, sizeof(r.detalle), "%s", motivo);
    publicar(&r);
}

esp_err_t aura_comandos_encolar(aura_origen_t origen, const char *id, const char *texto)
{
    if (!s_cola || !texto) {
        return ESP_ERR_INVALID_STATE;
    }
    item_cmd_t it = { .origen = origen };
    snprintf(it.id, sizeof(it.id), "%s", id ? id : "");
    if (strlen(texto) >= sizeof(it.texto)) {
        aura_comandos_rechazo(origen, it.id, "comando demasiado largo");
        return ESP_ERR_INVALID_SIZE;
    }
    strcpy(it.texto, texto);
    if (xQueueSend(s_cola, &it, 0) != pdTRUE) {
        aura_comandos_rechazo(origen, it.id, "cola de comandos llena");
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}

#define SIM_MAX_S 3600

/* Comandos de simulacion para las pruebas D7a-sim y D7c-sim. SOLO por la via local autenticada (HMAC con
 * la clave local): se rechazan por USB y por la nube (las reglas de Firebase tampoco los admiten).
 *   SIM_SIN_INTERNET <seg>      bloquea en la placa solo las conexiones a Firebase
 *   SIM_PIERDE_PRINCIPAL <seg>  la red principal se considera no disponible
 * <seg> = 0 cancela. Cada uno queda en el ack, en un mensaje {"type":"sim"} y en la telemetria. */
static void ejecutar_sim(const item_cmd_t *it, aura_cmd_resultado_t *r)
{
    r->ok = false;
    if (it->origen != AURA_ORIGEN_LOCAL) {
        s_rechazados++;
        snprintf(r->detalle, sizeof(r->detalle), "solo por la via local autenticada");
    } else {
        const char *arg = strchr(it->texto, ' ');
        char *fin = NULL;
        long seg = arg ? strtol(arg + 1, &fin, 10) : -1;
        if (!arg || fin == arg + 1 || *fin != '\0' || seg < 0 || seg > SIM_MAX_S) {
            snprintf(r->detalle, sizeof(r->detalle), "uso: %s <0..%d s>", r->cmd, SIM_MAX_S);
        } else {
            if (strcmp(r->cmd, "SIM_SIN_INTERNET") == 0) {
                aura_nube_sim_sin_internet((uint32_t)seg);
            } else {
                aura_wifi_sim_pierde_principal((uint32_t)seg);
            }
            r->ok = true;
            snprintf(r->detalle, sizeof(r->detalle), "%s %ld s", seg ? "activa" : "cancelada", seg);
            ESP_LOGW(TAG, "%s %ld s (origen local)", r->cmd, seg);
            web_serial_monitor_emitir("{\"type\":\"sim\",\"cmd\":\"%s\",\"seg\":%ld,\"id\":\"%s\"}", r->cmd, seg, r->id);
        }
    }
    publicar(r);
}

static void ejecutar(const item_cmd_t *it)
{
    aura_cmd_resultado_t r = { .origen = it->origen };
    snprintf(r.id, sizeof(r.id), "%s", it->id);
    primer_token(it->texto, r.cmd, sizeof(r.cmd));

    if (strcmp(r.cmd, "SIM_SIN_INTERNET") == 0 || strcmp(r.cmd, "SIM_PIERDE_PRINCIPAL") == 0) {
        ejecutar_sim(it, &r);
        return;
    }
    if (it->origen != AURA_ORIGEN_USB && !permitido(r.cmd)) {
        r.ok = false;
        snprintf(r.detalle, sizeof(r.detalle), "comando no permitido por esta via");
        publicar(&r);
        return;
    }
    bool afecta_calibracion = strncmp(r.cmd, "TRAIN_", 6) == 0 || strcmp(r.cmd, "RESET_BASELINE") == 0;
    if (afecta_calibracion && s_bloqueo_entrenamiento >= 0 && s_bloqueo_entrenamiento != (int)it->origen) {
        r.ok = false;
        snprintf(r.detalle, sizeof(r.detalle), "entrenamiento en curso desde %s",
                 aura_comandos_origen_nombre((aura_origen_t)s_bloqueo_entrenamiento));
        publicar(&r);
        return;
    }

    ESP_LOGI(TAG, "comando %s desde %s (id %s)", r.cmd, aura_comandos_origen_nombre(it->origen), it->id);
    web_serial_monitor_resultado_t res = {0};
    web_serial_monitor_ejecutar(it->texto, aura_comandos_origen_nombre(it->origen), it->id, &res);
    r.ok = res.ok;
    snprintf(r.detalle, sizeof(r.detalle), "%s", res.detalle);

    if (strcmp(r.cmd, "TRAIN_START") == 0 && r.ok) {
        s_bloqueo_entrenamiento = it->origen;
    } else if ((strcmp(r.cmd, "TRAIN_STOP") == 0 || strcmp(r.cmd, "RESET_BASELINE") == 0) &&
               s_bloqueo_entrenamiento == (int)it->origen) {
        s_bloqueo_entrenamiento = -1;
    }
    if (s_al_terminar) {
        s_al_terminar(&r);   /* el ack HMS ya lo emitio web_serial_monitor con origen e id */
    }
}

static void tarea_comandos(void *arg)
{
    (void)arg;
    item_cmd_t it;
    while (true) {
        if (xQueueReceive(s_cola, &it, portMAX_DELAY) == pdTRUE) {
            ejecutar(&it);
        }
    }
}

esp_err_t aura_comandos_iniciar(aura_cmd_cb_t al_terminar)
{
    s_al_terminar = al_terminar;
    s_cola = xQueueCreate(8, sizeof(item_cmd_t));
    if (!s_cola) {
        return ESP_ERR_NO_MEM;
    }
    return xTaskCreate(tarea_comandos, "aura_cmd", AURA_PILA_CMD, NULL, 3, NULL) == pdPASS ? ESP_OK : ESP_FAIL;
}

/* ---------------- consola USB ---------------- */

static int hex_a_bytes(const char *hex, char *out, size_t cap)
{
    size_t n = strlen(hex);
    if (n % 2 || n / 2 >= cap) {
        return -1;
    }
    for (size_t i = 0; i < n / 2; i++) {
        unsigned v;
        if (sscanf(hex + 2 * i, "%2x", &v) != 1) {
            return -1;
        }
        out[i] = (char)v;
    }
    out[n / 2] = '\0';
    return (int)(n / 2);
}

void aura_comandos_consola(const char *linea)
{
    char copia[600];
    snprintf(copia, sizeof(copia), "%s", linea);
    char *guardar = NULL;
    strtok_r(copia, " ", &guardar);                       /* "AURA" */
    char *accion = strtok_r(NULL, " ", &guardar);
    char *clave = strtok_r(NULL, " ", &guardar);
    char *valor_hex = strtok_r(NULL, " ", &guardar);
    if (!accion) {
        memset(copia, 0, sizeof(copia));
        return;
    }
    if (strcmp(accion, "SET") == 0 && clave && valor_hex) {
        char valor[260];
        esp_err_t err = ESP_ERR_INVALID_ARG;
        if (hex_a_bytes(valor_hex, valor, sizeof(valor)) >= 0) {
            err = aura_config_guardar_por_nombre(clave, valor);
        }
        memset(valor, 0, sizeof(valor));
        web_serial_monitor_ack_origen("AURA_SET", err == ESP_OK, clave, "usb", "");
    } else if (strcmp(accion, "DEL") == 0 && clave) {
        esp_err_t err = aura_config_borrar_por_nombre(clave);
        web_serial_monitor_ack_origen("AURA_DEL", err == ESP_OK, clave, "usb", "");
    } else if (strcmp(accion, "LIST") == 0) {
        char json[400];
        aura_config_resumen_json(json, sizeof(json));
        web_serial_monitor_emitir("{\"type\":\"credenciales\",\"definidas\":%s}", json);
    } else if (strcmp(accion, "INFO") == 0) {
        const esp_partition_t *p = esp_ota_get_running_partition();
        esp_ota_img_states_t st = ESP_OTA_IMG_UNDEFINED;
        if (p) {
            esp_ota_get_state_partition(p, &st);
        }
        web_serial_monitor_emitir("{\"type\":\"info\",\"ver\":\"%s\",\"particion\":\"%s\",\"estado_ota\":%d,"
                                  "\"sensor\":\"%s\"}", esp_app_get_description()->version,
                                  p ? p->label : "?", (int)st, CONFIG_AURA_SENSOR_ID);
    } else if (strcmp(accion, "REBOOT") == 0) {
        web_serial_monitor_ack_origen("AURA_REBOOT", true, "reiniciando", "usb", "");
        vTaskDelay(pdMS_TO_TICKS(300));
        esp_restart();
    } else {
        web_serial_monitor_ack_origen("AURA", false, "accion desconocida", "usb", "");
    }
    memset(copia, 0, sizeof(copia));
}

/* ---------------- autenticacion ---------------- */

static bool comparar_hex_ct(const uint8_t *mac, size_t n, const char *hex)
{
    if (strlen(hex) != n * 2) {
        return false;
    }
    static const char *dig = "0123456789abcdef";
    uint8_t dif = 0;
    for (size_t i = 0; i < n; i++) {
        dif |= (uint8_t)(tolower((unsigned char)hex[2 * i]) ^ dig[mac[i] >> 4]);
        dif |= (uint8_t)(tolower((unsigned char)hex[2 * i + 1]) ^ dig[mac[i] & 0xF]);
    }
    return dif == 0;
}

static bool autenticar(uint64_t ctr, const char *texto, const char *hmac_hex)
{
    char clave[256];
    if (aura_config_leer(AURA_CFG_LOCAL_KEY, clave, sizeof(clave)) != ESP_OK) {
        ESP_LOGW(TAG, "sin clave local en NVS: comandos locales y OTA deshabilitados");
        return false;
    }
    char mensaje[256];
    int n = snprintf(mensaje, sizeof(mensaje), "%" PRIu64 " %s", ctr, texto);
    if (n <= 0 || n >= (int)sizeof(mensaje)) {
        memset(clave, 0, sizeof(clave));
        return false;
    }
    uint8_t mac[32];
    int err = mbedtls_md_hmac(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256),
                              (const unsigned char *)clave, strlen(clave),
                              (const unsigned char *)mensaje, n, mac);
    memset(clave, 0, sizeof(clave));
    if (err != 0 || !comparar_hex_ct(mac, sizeof(mac), hmac_hex)) {
        return false;
    }
    /* Anti repeticion: contador estrictamente creciente y, si hay hora, cercano a la hora real. */
    if (aura_tiempo_sincronizado()) {
        int64_t ahora_ms = aura_tiempo_unix_us() / 1000;
        int64_t dif = (int64_t)ctr - ahora_ms;
        if (dif > 120000 || dif < -120000) {
            ESP_LOGW(TAG, "comando con hora fuera de rango (%" PRId64 " ms)", dif);
            return false;
        }
    }
    bool ok = false;
    portENTER_CRITICAL(&s_mux_ctr);
    if (ctr > s_ultimo_ctr) {
        s_ultimo_ctr = ctr;
        ok = true;
    }
    portEXIT_CRITICAL(&s_mux_ctr);
    return ok;
}

bool aura_comandos_autenticar(uint64_t ctr, const char *texto, const char *hmac_hex)
{
    return autenticar(ctr, texto, hmac_hex);
}

bool aura_comandos_autenticar_ota(uint64_t ctr, const char *texto, const char *hmac_hex)
{
    char t[160];
    snprintf(t, sizeof(t), "OTA %s", texto);   /* dominio separado: una firma de comando no sirve para OTA */
    return autenticar(ctr, t, hmac_hex);
}
