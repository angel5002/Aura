/*
 * AURA - telemetria.
 */
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "esp_heap_caps.h"
#include "esp_app_desc.h"
#include "esp_ota_ops.h"
#include "sdkconfig.h"

#include "aura_telemetria.h"
#include "aura_pilas.h"
#include "aura_salida.h"
#include "aura_local.h"
#include "aura_wifi.h"
#include "aura_tiempo.h"
#include "aura_sensing.h"
#include "aura_nube.h"
#include "aura_diag.h"
#include "web_serial_monitor.h"

#define PERIODO_MS   10000
#define MAX_DIFS     400

static portMUX_TYPE s_mux = portMUX_INITIALIZER_UNLOCKED;
static uint16_t s_difs[MAX_DIFS];
static int s_n_difs;
static uint32_t s_n_muestras;
static uint64_t s_ultimo_ts;
static aura_telemetria_t s_ultima;

const char *aura_telemetria_motivo_reinicio(void)
{
    switch (esp_reset_reason()) {
    case ESP_RST_POWERON:   return "encendido";
    case ESP_RST_EXT:       return "externo";
    case ESP_RST_SW:        return "software";
    case ESP_RST_PANIC:     return "panico";
    case ESP_RST_INT_WDT:   return "wdt_interrupcion";
    case ESP_RST_TASK_WDT:  return "wdt_tarea";
    case ESP_RST_WDT:       return "wdt";
    case ESP_RST_DEEPSLEEP: return "deep_sleep";
    case ESP_RST_BROWNOUT:  return "brownout";
    case ESP_RST_SDIO:      return "sdio";
    case ESP_RST_USB:       return "usb";
    case ESP_RST_JTAG:      return "jtag";
    default:                return "desconocido";
    }
}

void aura_telemetria_muestra(uint64_t ts_ms)
{
    portENTER_CRITICAL(&s_mux);
    if (s_ultimo_ts && ts_ms > s_ultimo_ts && s_n_difs < MAX_DIFS) {
        uint64_t d = ts_ms - s_ultimo_ts;
        s_difs[s_n_difs++] = (uint16_t)(d > 65535 ? 65535 : d);
    }
    s_ultimo_ts = ts_ms;
    s_n_muestras++;
    portEXIT_CRITICAL(&s_mux);
}

/* Tareas propias y su pila configurada. El nombre es el que guarda FreeRTOS (maximo 15 caracteres:
 * "web_serial_monitor" queda como "web_serial_moni"). */
static const struct {
    const char *nombre;
    uint32_t tam;
} TAREAS[] = {
    { "aura_wifi", AURA_PILA_WIFI }, { "aura_local", AURA_PILA_LOCAL }, { "aura_cmd", AURA_PILA_CMD },
    { "aura_ota", AURA_PILA_OTA }, { "aura_nube", AURA_PILA_NUBE }, { "aura_tel", AURA_PILA_TEL },
    { "web_serial_moni", AURA_PILA_MONITOR }, { "aura_diag", AURA_PILA_DIAG },
};

/* {"type":"pilas",...}: para cada tarea, tamano de pila y minimo libre historico (bytes; en IDF la pila
 * es de uint8_t, asi que uxTaskGetStackHighWaterMark devuelve bytes). -1 si la tarea no existe. */
static void emitir_pilas(uint32_t encendido_s)
{
    char json[640];
    size_t u = snprintf(json, sizeof(json), "{\"type\":\"pilas\",\"encendido_s\":%" PRIu32 ",\"tareas\":{", encendido_s);
    for (size_t i = 0; i < sizeof(TAREAS) / sizeof(TAREAS[0]) && u < sizeof(json); i++) {
        TaskHandle_t h = xTaskGetHandle(TAREAS[i].nombre);
        long libre = h ? (long)uxTaskGetStackHighWaterMark(h) : -1;
        u += snprintf(json + u, sizeof(json) - u, "%s\"%s\":{\"tam\":%" PRIu32 ",\"libre_min\":%ld}",
                      i ? "," : "", TAREAS[i].nombre, TAREAS[i].tam, libre);
    }
    if (u < sizeof(json)) {
        snprintf(json + u, sizeof(json) - u, "}}");
        web_serial_monitor_emitir("%s", json);
    }
}

static int cmp_u16(const void *a, const void *b)
{
    return (int)*(const uint16_t *)a - (int)*(const uint16_t *)b;
}

/* ---- memoria: minimo por intervalo e historico ----
 * El minimo de cada intervalo usa el monitor local de heap de IDF (heap_caps_monitor_local_minimum_free_size_*),
 * que se reinicia en cada informe. Mientras esta activo, esp_get_minimum_free_heap_size() devuelve el minimo
 * LOCAL, asi que el historico se lleva aqui: s_min_hist = minimo de los intervalos ya cerrados (incluido el
 * tramo desde el arranque hasta el primer informe). */
static volatile uint32_t s_min_hist = UINT32_MAX;
static volatile uint32_t s_malloc_fallidos;
static volatile uint32_t s_malloc_fallido_max;
static volatile uint32_t s_malloc_fallido_caps;     /* caps de la asignacion fallida mas grande */

uint32_t aura_telemetria_minimo_historico(void)
{
    uint32_t local = esp_get_minimum_free_heap_size();
    return local < s_min_hist ? local : s_min_hist;
}

uint32_t aura_telemetria_minimo_intervalo(void)
{
    return esp_get_minimum_free_heap_size();
}

uint32_t aura_telemetria_bloque_max(void)
{
    return heap_caps_get_largest_free_block(MALLOC_CAP_DEFAULT);
}

/* Se llama DENTRO de la asignacion que fallo: solo cuenta (sin imprimir ni reservar memoria). */
static void al_fallar_malloc(size_t tam, uint32_t caps, const char *funcion)
{
    (void)funcion;
    s_malloc_fallidos++;
    if (tam > s_malloc_fallido_max) {
        s_malloc_fallido_max = tam;
        s_malloc_fallido_caps = caps;
    }
}

/* Cierra el intervalo: devuelve su minimo, lo acumula en el historico y reinicia el monitor local. */
static uint32_t cerrar_intervalo_memoria(void)
{
    uint32_t min_int = esp_get_minimum_free_heap_size();
    if (min_int < s_min_hist) {
        s_min_hist = min_int;
    }
    heap_caps_monitor_local_minimum_free_size_start();
    return min_int;
}

static void tarea_telemetria(void *arg)
{
    (void)arg;
    uint16_t *copia = malloc(MAX_DIFS * sizeof(uint16_t));
    cerrar_intervalo_memoria();         /* historico = minimo desde el arranque; empieza el 1.er intervalo */
    TickType_t t = xTaskGetTickCount();
    uint32_t ciclo = 0;
    while (true) {
        vTaskDelayUntil(&t, pdMS_TO_TICKS(PERIODO_MS));
        if (++ciclo % 6 == 0) {     /* cada 60 s */
            emitir_pilas((uint32_t)(esp_timer_get_time() / 1000000LL));
        }
        int n;
        uint32_t muestras;
        portENTER_CRITICAL(&s_mux);
        n = s_n_difs;
        if (copia) {
            memcpy(copia, s_difs, n * sizeof(uint16_t));
        }
        muestras = s_n_muestras;
        s_n_difs = 0;
        s_n_muestras = 0;
        portEXIT_CRITICAL(&s_mux);

        uint32_t min_intervalo = cerrar_intervalo_memoria();
        aura_telemetria_t tel = {
            .heap_libre = esp_get_free_heap_size(),
            .heap_minimo = s_min_hist,
            .heap_min_intervalo = min_intervalo,
            .bloque_max = aura_telemetria_bloque_max(),
            .hms_por_s = muestras * 1000.0f / PERIODO_MS,
            .encendido_s = (uint32_t)(esp_timer_get_time() / 1000000LL),
            .motivo_reinicio = aura_telemetria_motivo_reinicio(),
        };
        if (copia && n > 0) {
            qsort(copia, n, sizeof(uint16_t), cmp_u16);
            tel.ts_mediana_ms = (n % 2) ? copia[n / 2] : (copia[n / 2 - 1] + copia[n / 2]) / 2.0f;
            int i95 = (int)(0.95f * (n - 1) + 0.5f);
            tel.ts_p95_ms = copia[i95];
        }
        s_ultima = tel;

        aura_salida_stats_t so;
        aura_local_stats_t lo;
        aura_sensing_stats_t se;
        aura_nube_stats_t nu;
        aura_estado_info_t est;
        aura_salida_stats(&so);
        aura_local_stats(&lo);
        aura_sensing_stats(&se);
        aura_nube_stats(&nu);
        aura_sensing_estado(&est);
        const esp_partition_t *part = esp_ota_get_running_partition();
        esp_ota_img_states_t st_ota = ESP_OTA_IMG_UNDEFINED;
        if (part) {
            esp_ota_get_state_partition(part, &st_ota);
        }
        web_serial_monitor_emitir(
            "{\"type\":\"telemetria\",\"heap_libre\":%" PRIu32 ",\"heap_minimo\":%" PRIu32 ","
            "\"heap_min_intervalo\":%" PRIu32 ",\"bloque_max\":%" PRIu32 ",\"malloc_fallidos\":%" PRIu32 ","
            "\"malloc_fallido_max\":%" PRIu32 ",\"malloc_fallido_caps\":\"0x%" PRIx32 "\",\"tls_handshakes\":%" PRIu32 ","
            "\"hms_por_s\":%.2f,"
            "\"ts_mediana_ms\":%.1f,\"ts_p95_ms\":%.1f,\"n_intervalos\":%d,\"motivo_reinicio\":\"%s\","
            "\"encendido_s\":%" PRIu32 ",\"ver\":\"%s\",\"red\":\"%s\",\"rssi\":%d,\"cambios_red\":%" PRIu32 ","
            "\"sntp\":%d,\"usb\":%" PRIu32 ",\"usb_descartes\":%" PRIu32 ",\"local_subs\":%u,\"local_seq\":%" PRIu32 ","
            "\"local_descartes\":%" PRIu32 ",\"local_errores\":%" PRIu32 ",\"csi_total\":%" PRIu32 ","
            "\"detector_recreado\":%" PRIu32 ",\"estado\":\"%s\",\"nube\":\"%s\",\"nube_tokens\":%" PRIu32 ","
            "\"nube_renovaciones\":%" PRIu32 ",\"nube_errores\":%" PRIu32 ",\"nube_escrituras\":%" PRIu32 ","
            "\"particion\":\"%s\",\"estado_ota\":%d,\"rx_buf\":%d,\"nube_espera_s\":%" PRIu32 ","
            "\"nube_http\":%d,\"reintentos_principal\":%" PRIu32 ",\"sim_sin_internet_s\":%" PRIu32 ","
            "\"sim_pierde_principal_s\":%" PRIu32 ",\"cmd_rechazados\":%" PRIu32 "}",
            tel.heap_libre, tel.heap_minimo, tel.heap_min_intervalo, tel.bloque_max, s_malloc_fallidos,
            s_malloc_fallido_max, s_malloc_fallido_caps, nu.tls_handshakes, (double)tel.hms_por_s, (double)tel.ts_mediana_ms,
            (double)tel.ts_p95_ms, n, tel.motivo_reinicio, tel.encendido_s, esp_app_get_description()->version,
            aura_wifi_red_nombre(aura_wifi_red_activa()), aura_wifi_rssi(), aura_wifi_cambios_red(),
            aura_tiempo_sincronizado() ? 1 : 0, so.usb_conectado, so.usb_descartes, lo.suscriptores, lo.seq,
            lo.descartes_cola, lo.errores_envio, se.csi_total, se.recreaciones,
            aura_sensing_estado_nombre(est.estado), aura_nube_estado_nombre(nu.estado), nu.tokens_obtenidos,
            nu.renovaciones, nu.errores, nu.escrituras, part ? part->label : "?", (int)st_ota,
            CONFIG_ESP_WIFI_DYNAMIC_RX_BUFFER_NUM, nu.espera_s, nu.ultimo_http, aura_wifi_reintentos_principal(),
            aura_nube_sim_restante_s(), aura_wifi_sim_restante_s(), aura_comandos_rechazados());
        aura_diag_intervalo();      /* {"type":"cpu"} y {"type":"pila_red"} del mismo intervalo */
    }
}

void aura_telemetria_hito(const char *momento)
{
    web_serial_monitor_emitir("{\"type\":\"memoria\",\"momento\":\"%s\",\"heap_libre\":%" PRIu32 ","
                              "\"heap_minimo\":%" PRIu32 ",\"heap_min_intervalo\":%" PRIu32 ",\"bloque_max\":%" PRIu32 ","
                              "\"encendido_ms\":%" PRIu32 "}",
                              momento, esp_get_free_heap_size(), aura_telemetria_minimo_historico(),
                              aura_telemetria_minimo_intervalo(), aura_telemetria_bloque_max(),
                              (uint32_t)(esp_timer_get_time() / 1000LL));
}

esp_err_t aura_telemetria_iniciar(void)
{
    heap_caps_register_failed_alloc_callback(al_fallar_malloc);
    return xTaskCreate(tarea_telemetria, "aura_tel", AURA_PILA_TEL, NULL, 3, NULL) == pdPASS ? ESP_OK : ESP_FAIL;
}

const char *aura_telemetria_tarea_faltante(void)
{
    for (size_t i = 0; i < sizeof(TAREAS) / sizeof(TAREAS[0]); i++) {
        if (!xTaskGetHandle(TAREAS[i].nombre)) {
            return TAREAS[i].nombre;
        }
    }
    return NULL;
}

void aura_telemetria_ultima(aura_telemetria_t *out)
{
    *out = s_ultima;
}
