/*
 * AURA - configuracion y credenciales en NVS.
 */
#include <string.h>
#include <stdio.h>

#include "esp_log.h"
#include "nvs.h"
#include "nvs_flash.h"

#include "aura_config.h"

static const char *TAG = "aura_config";
static const char *NS_CRED = "aura_cred";
static const char *NS_ESTADO = "aura_estado";

static const char *const NOMBRES[AURA_CFG_NUM] = {
    [AURA_CFG_WIFI1_SSID] = "wifi1_ssid",
    [AURA_CFG_WIFI1_PASS] = "wifi1_pass",
    [AURA_CFG_WIFI2_SSID] = "wifi2_ssid",
    [AURA_CFG_WIFI2_PASS] = "wifi2_pass",
    [AURA_CFG_FB_API_KEY] = "fb_api_key",
    [AURA_CFG_FB_DB_URL]  = "fb_db_url",
    [AURA_CFG_FB_EMAIL]   = "fb_email",
    [AURA_CFG_FB_PASS]    = "fb_pass",
    [AURA_CFG_LOCAL_KEY]  = "local_key",
};

static int indice_por_nombre(const char *nombre)
{
    for (int i = 0; i < AURA_CFG_NUM; i++) {
        if (strcmp(nombre, NOMBRES[i]) == 0) {
            return i;
        }
    }
    return -1;
}

esp_err_t aura_config_init(void)
{
    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        /* Solo ocurre si la particion cambia de formato: se pierde el contenido y hay que recargar credenciales. */
        ESP_LOGW(TAG, "NVS sin paginas libres o de otra version: se borra y hay que recargar credenciales");
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    return err;
}

static esp_err_t leer_ns(const char *ns, const char *nombre, char *buf, size_t len)
{
    nvs_handle_t h;
    esp_err_t err = nvs_open(ns, NVS_READONLY, &h);
    if (err != ESP_OK) {
        return (err == ESP_ERR_NVS_NOT_FOUND) ? ESP_ERR_NOT_FOUND : err;
    }
    size_t n = len;
    err = nvs_get_str(h, nombre, buf, &n);
    nvs_close(h);
    if (err == ESP_ERR_NVS_NOT_FOUND) {
        return ESP_ERR_NOT_FOUND;
    }
    return err;
}

static esp_err_t guardar_ns(const char *ns, const char *nombre, const char *valor)
{
    nvs_handle_t h;
    esp_err_t err = nvs_open(ns, NVS_READWRITE, &h);
    if (err != ESP_OK) {
        return err;
    }
    err = nvs_set_str(h, nombre, valor);
    if (err == ESP_OK) {
        err = nvs_commit(h);
    }
    nvs_close(h);
    return err;
}

esp_err_t aura_config_leer(aura_cfg_clave_t clave, char *buf, size_t len)
{
    if (clave >= AURA_CFG_NUM || !buf || len == 0) {
        return ESP_ERR_INVALID_ARG;
    }
    buf[0] = '\0';
    esp_err_t err = leer_ns(NS_CRED, NOMBRES[clave], buf, len);
    if (err == ESP_OK && buf[0] == '\0') {
        return ESP_ERR_NOT_FOUND;
    }
    return err;
}

bool aura_config_definida(aura_cfg_clave_t clave)
{
    char tmp[256];
    bool ok = aura_config_leer(clave, tmp, sizeof(tmp)) == ESP_OK;
    memset(tmp, 0, sizeof(tmp));
    return ok;
}

esp_err_t aura_config_guardar_por_nombre(const char *nombre, const char *valor)
{
    int i = indice_por_nombre(nombre);
    if (i < 0 || !valor) {
        return ESP_ERR_INVALID_ARG;
    }
    if (strlen(valor) > 255) {
        return ESP_ERR_INVALID_SIZE;
    }
    esp_err_t err = guardar_ns(NS_CRED, NOMBRES[i], valor);
    /* Solo el nombre de la clave, nunca el valor. */
    ESP_LOGI(TAG, "clave %s %s", NOMBRES[i], err == ESP_OK ? "guardada" : "NO guardada");
    return err;
}

esp_err_t aura_config_borrar_por_nombre(const char *nombre)
{
    int i = indice_por_nombre(nombre);
    if (i < 0) {
        return ESP_ERR_INVALID_ARG;
    }
    nvs_handle_t h;
    esp_err_t err = nvs_open(NS_CRED, NVS_READWRITE, &h);
    if (err != ESP_OK) {
        return err;
    }
    err = nvs_erase_key(h, NOMBRES[i]);
    if (err == ESP_OK) {
        err = nvs_commit(h);
    } else if (err == ESP_ERR_NVS_NOT_FOUND) {
        err = ESP_OK;
    }
    nvs_close(h);
    return err;
}

void aura_config_resumen_json(char *out, size_t len)
{
    size_t usado = snprintf(out, len, "{");
    for (int i = 0; i < AURA_CFG_NUM && usado < len; i++) {
        usado += snprintf(out + usado, len - usado, "%s\"%s\":%s", i ? "," : "", NOMBRES[i],
                          aura_config_definida((aura_cfg_clave_t)i) ? "true" : "false");
    }
    if (usado < len) {
        snprintf(out + usado, len - usado, "}");
    }
}

esp_err_t aura_config_leer_str(const char *nombre, char *buf, size_t len)
{
    buf[0] = '\0';
    return leer_ns(NS_ESTADO, nombre, buf, len);
}

esp_err_t aura_config_guardar_str(const char *nombre, const char *valor)
{
    return guardar_ns(NS_ESTADO, nombre, valor);
}
