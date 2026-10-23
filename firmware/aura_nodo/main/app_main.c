/*
 * SPDX-FileCopyrightText: 2026 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 * AURA nodo: reescrito a partir de esp-csi/examples/esp-radar/wifi_sensing_demo/main/app_main.c.
 * La deteccion (esp_wifi_sensing) corre siempre en la placa. Dos vias independientes:
 *   - local: UDP con todos los datos (aura_local.c) + OTA autenticada (aura_ota.c)
 *   - nube:  Firebase REST con cuenta de dispositivo (aura_nube.c)
 * Ninguna via depende de la otra. Credenciales en NVS (aura_config.c), nunca compiladas.
 */
#include <inttypes.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_event.h"
#include "esp_log.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "esp_heap_caps.h"
#include "esp_app_desc.h"

#include "led_control.h"
#include "web_serial_monitor.h"
#include "aura_config.h"
#include "aura_salida.h"
#include "aura_comandos.h"
#include "aura_local.h"
#include "aura_sensing.h"
#include "aura_tiempo.h"
#include "aura_wifi.h"
#include "aura_ota.h"
#include "aura_nube.h"
#include "aura_telemetria.h"
#include "aura_diag.h"

static const char *TAG = "aura_nodo";

#define AUTOPRUEBA_MIN_S  30

static void anunciar_arranque(void)
{
    const esp_partition_t *p = esp_ota_get_running_partition();
    esp_ota_img_states_t st = ESP_OTA_IMG_UNDEFINED;
    if (p) {
        esp_ota_get_state_partition(p, &st);
    }
    ESP_LOGI(TAG, "AURA nodo %s en %s (motivo de reinicio: %s)", esp_app_get_description()->version,
             p ? p->label : "?", aura_telemetria_motivo_reinicio());
    web_serial_monitor_emitir("{\"type\":\"arranque\",\"ver\":\"%s\",\"particion\":\"%s\",\"estado_ota\":%d,"
                              "\"motivo_reinicio\":\"%s\",\"sensor\":\"%s\"}",
                              esp_app_get_description()->version, p ? p->label : "?", (int)st,
                              aura_telemetria_motivo_reinicio(), CONFIG_AURA_SENSOR_ID);
}

#if !CONFIG_AURA_PRUEBA_ROLLBACK
/* Primera condicion de la autoprueba que NO se cumple ahora (NULL si se cumplen todas). */
static const char *autoprueba_falla(uint32_t *csi_ant)
{
    aura_sensing_stats_t se;
    aura_sensing_stats(&se);
    bool csi_nuevo = se.csi_total != *csi_ant;
    *csi_ant = se.csi_total;
    if (!aura_wifi_conectado()) {
        return "sin_ip";
    }
    if (!aura_sensing_activo()) {
        return "detector_no_iniciado";
    }
    if (!csi_nuevo) {
        return "sin_csi";
    }
    const char *falta = aura_telemetria_tarea_faltante();
    if (falta) {
        return falta;
    }
    if (esp_get_free_heap_size() < CONFIG_AURA_AUTOPRUEBA_HEAP_MIN_KB * 1024U) {
        return "memoria_baja";
    }
    return NULL;
}
#endif

/* Autoprueba de una imagen nueva (OTA). esp_ota_mark_app_valid_cancel_rollback() se llama SOLO al final,
 * cuando durante CONFIG_AURA_AUTOPRUEBA_VENTANA_S segundos seguidos (muestra cada 1 s) hay IP, el
 * detector existe y recibe CSI, existen todas las tareas propias y la memoria libre no baja del minimo,
 * y no antes de AUTOPRUEBA_MIN_S desde el arranque. Si no se logra en CONFIG_AURA_AUTOPRUEBA_MAX_S, se
 * reinicia sin validar y el cargador vuelve a la imagen anterior. */
static void autoprueba(void)
{
    const esp_partition_t *p = esp_ota_get_running_partition();
    esp_ota_img_states_t st;
    if (!p || esp_ota_get_state_partition(p, &st) != ESP_OK || st != ESP_OTA_IMG_PENDING_VERIFY) {
        return;     /* imagen grabada por USB o ya validada */
    }
#if CONFIG_AURA_PRUEBA_ROLLBACK
    ESP_LOGW(TAG, "PRUEBA D8(d): esta imagen NO se marcara como valida; reinicio en %d s", AUTOPRUEBA_MIN_S);
    web_serial_monitor_emitir("{\"type\":\"ota\",\"fase\":\"prueba_rollback\",\"detalle\":\"reinicio sin validar\"}");
    vTaskDelay(pdMS_TO_TICKS(AUTOPRUEBA_MIN_S * 1000));
    esp_restart();
#else
    web_serial_monitor_emitir("{\"type\":\"ota\",\"fase\":\"autoprueba\",\"detalle\":\"pendiente de validar\"}");
    uint32_t csi_ant = 0;
    uint32_t seguidos = 0, heap_min_ventana = UINT32_MAX;
    const char *ultima_falla = "inicio";
    while (seguidos < CONFIG_AURA_AUTOPRUEBA_VENTANA_S ||
           esp_timer_get_time() < (int64_t)AUTOPRUEBA_MIN_S * 1000000LL) {
        vTaskDelay(pdMS_TO_TICKS(1000));
        const char *falla = autoprueba_falla(&csi_ant);
        if (falla) {
            seguidos = 0;
            heap_min_ventana = UINT32_MAX;
            ultima_falla = falla;
        } else {
            seguidos++;
            uint32_t h = esp_get_free_heap_size();
            heap_min_ventana = h < heap_min_ventana ? h : heap_min_ventana;
        }
        if (CONFIG_AURA_AUTOPRUEBA_MAX_S > 0 &&
            esp_timer_get_time() >= (int64_t)CONFIG_AURA_AUTOPRUEBA_MAX_S * 1000000LL) {
            ESP_LOGE(TAG, "autoprueba no superada en %d s (%s): reinicio sin validar", CONFIG_AURA_AUTOPRUEBA_MAX_S,
                     ultima_falla);
            web_serial_monitor_emitir("{\"type\":\"ota\",\"fase\":\"autoprueba_fallida\",\"detalle\":\"%s\"}",
                                      ultima_falla);
            vTaskDelay(pdMS_TO_TICKS(500));
            esp_restart();
        }
    }
    if (esp_ota_mark_app_valid_cancel_rollback() == ESP_OK) {
        ESP_LOGI(TAG, "imagen validada tras %" PRIu32 " s de autoprueba (se cancela la vuelta atras)", seguidos);
        web_serial_monitor_emitir("{\"type\":\"ota\",\"fase\":\"validada\",\"detalle\":\"%s\",\"ventana_s\":%" PRIu32 ","
                                  "\"heap_min_ventana\":%" PRIu32 ",\"encendido_s\":%" PRIu32 "}",
                                  p->label, seguidos, heap_min_ventana,
                                  (uint32_t)(esp_timer_get_time() / 1000000LL));
    }
#endif
}

/* Modulos opcionales: si no pueden iniciarse (p. ej. falta RAM) la placa sigue funcionando sin ellos,
 * en vez de reiniciarse en bucle. Se avisa por registro y con un mensaje HMS. */
static void opcional(const char *modulo, esp_err_t err)
{
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "%s no se inicio (%s): la placa sigue sin esa funcion", modulo, esp_err_to_name(err));
        web_serial_monitor_emitir("{\"type\":\"modulo_no_iniciado\",\"modulo\":\"%s\",\"error\":\"%s\","
                                  "\"heap_libre\":%" PRIu32 "}", modulo, esp_err_to_name(err),
                                  esp_get_free_heap_size());
    }
}

void app_main(void)
{
    opcional("salida_usb", aura_salida_init());   /* USB sin bloqueos y ESP_LOG redirigido */
    ESP_ERROR_CHECK(aura_config_init());          /* NVS: credenciales (imprescindible) */
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    opcional("led", led_init());
    led_set_wifi_connected(false);

    ESP_ERROR_CHECK(aura_comandos_iniciar(aura_nube_resultado_comando));
    /* El detector crea su mutex aqui y DEBE ir antes del monitor: la tarea del monitor llama a
     * aura_sensing_fsm_tomar() en cuanto arranca (error del 24/10: assert pxMutex NULL en bucle). */
    ESP_ERROR_CHECK(aura_sensing_iniciar());      /* registra callbacks antes de arrancar el WiFi */
    /* El monitor (lectura de comandos USB y salida HMS) arranca SIEMPRE, aunque no haya red: sin el,
     * no se podrian cargar las credenciales por USB en una placa recien grabada. La MAC del AP se
     * completa al conectar (aura_sensing.c). */
    web_serial_monitor_peer_t pares[1] = { { .name = "AP" } };
    web_serial_monitor_config_t mcfg = {
        .peers = pares,
        .peer_num = 1,
        .stream_period_ms = CONFIG_ESP_WIFI_SENSING_WEB_SERIAL_STREAM_PERIOD_MS,
    };
    ESP_ERROR_CHECK(web_serial_monitor_init(&mcfg));
    opcional("via_local", aura_local_iniciar());
    opcional("sntp", aura_tiempo_iniciar());
    ESP_ERROR_CHECK(aura_wifi_iniciar());
    opcional("ota_local", aura_ota_iniciar());
    opcional("via_nube", aura_nube_iniciar());
    opcional("telemetria", aura_telemetria_iniciar());
    opcional("diagnostico", aura_diag_iniciar());   /* 0.1.3: CPU por tarea, cola de lwIP, episodios */

    anunciar_arranque();
    autoprueba();
}
