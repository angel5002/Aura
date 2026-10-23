/*
 * AURA - via local por UDP.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>
#include <sys/time.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/ringbuf.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_mac.h"
#include "esp_app_desc.h"
#include "lwip/sockets.h"
#include "mbedtls/base64.h"

#include "aura_local.h"
#include "aura_pilas.h"
#include "aura_wifi.h"
#include "aura_tiempo.h"
#include "aura_comandos.h"

static const char *TAG = "aura_local";

#define COLA_BYTES        (CONFIG_AURA_LOCAL_COLA_KB * 1024)
#define LEASE_US          (30LL * 1000 * 1000)
#define ANUNCIO_US        (2LL * 1000 * 1000)
#define DGRAMA_MAX        2048
#define TAREA_PRIORIDAD   3

typedef struct {
    struct sockaddr_in dir;
    int64_t vence_us;
    bool activo;
} suscriptor_t;

static RingbufHandle_t s_cola;
static suscriptor_t s_subs[CONFIG_AURA_LOCAL_MAX_SUSCRIPTORES];
static volatile uint32_t s_seq, s_enviados, s_descartes, s_errores;
static int s_sock = -1;

void aura_local_encolar(aura_local_tipo_t tipo, const void *datos, size_t len)
{
    if (!s_cola) {
        return;
    }
    /* Item = 1 byte de tipo + datos. xRingbufferSendAcquire evita copiar dos veces. */
    uint8_t *item = NULL;
    if (xRingbufferSendAcquire(s_cola, (void **)&item, len + 1, 0) != pdTRUE || !item) {
        s_descartes++;
        return;
    }
    item[0] = (uint8_t)tipo;
    memcpy(item + 1, datos, len);
    xRingbufferSendComplete(s_cola, item);
}

static bool hay_suscriptores(void);

void *aura_local_reservar(aura_local_tipo_t tipo, size_t len)
{
    if (!s_cola || !hay_suscriptores()) {
        return NULL;        /* sin receptores no se gasta cola ni CPU en el CSI */
    }
    uint8_t *item = NULL;
    if (xRingbufferSendAcquire(s_cola, (void **)&item, len + 1, 0) != pdTRUE || !item) {
        s_descartes++;
        return NULL;
    }
    item[0] = (uint8_t)tipo;
    return item + 1;
}

void aura_local_confirmar(void *ptr)
{
    if (ptr) {
        xRingbufferSendComplete(s_cola, (uint8_t *)ptr - 1);
    }
}

void aura_local_stats(aura_local_stats_t *out)
{
    out->enviados = s_enviados;
    out->descartes_cola = s_descartes;
    out->errores_envio = s_errores;
    out->seq = s_seq;
    uint8_t n = 0;
    int64_t ahora = esp_timer_get_time();
    for (int i = 0; i < CONFIG_AURA_LOCAL_MAX_SUSCRIPTORES; i++) {
        if (s_subs[i].activo && s_subs[i].vence_us > ahora) {
            n++;
        }
    }
    out->suscriptores = n;
}

static void enviar_a_suscriptores(const char *buf, size_t len)
{
    int64_t ahora = esp_timer_get_time();
    for (int i = 0; i < CONFIG_AURA_LOCAL_MAX_SUSCRIPTORES; i++) {
        if (!s_subs[i].activo) {
            continue;
        }
        if (s_subs[i].vence_us <= ahora) {
            s_subs[i].activo = false;
            continue;
        }
        int r = sendto(s_sock, buf, len, MSG_DONTWAIT, (struct sockaddr *)&s_subs[i].dir, sizeof(s_subs[i].dir));
        if (r < 0) {
            s_errores++;
        } else {
            s_enviados++;
        }
    }
}

static bool hay_suscriptores(void)
{
    int64_t ahora = esp_timer_get_time();
    for (int i = 0; i < CONFIG_AURA_LOCAL_MAX_SUSCRIPTORES; i++) {
        if (s_subs[i].activo && s_subs[i].vence_us > ahora) {
            return true;
        }
    }
    return false;
}

static size_t formatear_csi(char *out, size_t cap, const aura_csi_registro_t *r)
{
    int n = snprintf(out, cap,
                     "{\"seq_id\":%" PRIu32 ",\"t_us\":%" PRId64 ",\"rx_ts_us\":%" PRIu32 ",\"rssi\":%d,"
                     "\"nf\":%d,\"canal\":%u,\"agc\":%u,\"fft\":%d,\"rate\":%u,\"rx_format\":%u,\"cwb\":%u,"
                     "\"tipo_dato\":%u,\"comp\":%.6f,\"raw_len\":%u,\"valid_len\":%u,\"raw\":\"",
                     r->seq_id, r->t_us, r->rx_ts_us, r->rssi, r->noise_floor, r->channel, r->agc_gain,
                     r->fft_gain, r->rate, r->rx_format, r->cwb, r->data_type, (double)r->compensacion,
                     r->raw_len, r->valid_len);
    if (n <= 0 || (size_t)n >= cap) {
        return 0;
    }
    size_t usado = n, olen = 0;
    if (mbedtls_base64_encode((unsigned char *)out + usado, cap - usado, &olen, r->datos, r->raw_len) != 0) {
        return 0;
    }
    usado += olen;
    n = snprintf(out + usado, cap - usado, "\",\"valid\":\"");
    if (n <= 0 || usado + n >= cap) {
        return 0;
    }
    usado += n;
    if (mbedtls_base64_encode((unsigned char *)out + usado, cap - usado, &olen, r->datos + r->raw_len, r->valid_len) != 0) {
        return 0;
    }
    usado += olen;
    n = snprintf(out + usado, cap - usado, "\"}");
    if (n <= 0 || usado + n >= cap) {
        return 0;
    }
    return usado + n;
}

static void procesar_item(const uint8_t *item, size_t len, char *dgrama)
{
    if (len < 1 || !hay_suscriptores()) {
        return;
    }
    uint32_t seq = ++s_seq;
    int64_t t_us = aura_tiempo_unix_us();
    const char *tipo = (item[0] == AURA_LOCAL_TIPO_CSI) ? "csi" : "hms";
    int cab = snprintf(dgrama, DGRAMA_MAX, "A1 %" PRIu32 " %" PRId64 " %s ", seq, t_us, tipo);
    if (cab <= 0) {
        return;
    }
    size_t cuerpo = 0;
    if (item[0] == AURA_LOCAL_TIPO_CSI) {
        cuerpo = formatear_csi(dgrama + cab, DGRAMA_MAX - cab, (const aura_csi_registro_t *)(item + 1));
    } else if (len - 1 < (size_t)(DGRAMA_MAX - cab)) {
        memcpy(dgrama + cab, item + 1, len - 1);
        cuerpo = len - 1;
    }
    if (cuerpo == 0) {
        return;
    }
    enviar_a_suscriptores(dgrama, cab + cuerpo);
}

static void suscribir(const struct sockaddr_in *de)
{
    int64_t ahora = esp_timer_get_time();
    int libre = -1;
    for (int i = 0; i < CONFIG_AURA_LOCAL_MAX_SUSCRIPTORES; i++) {
        if (s_subs[i].activo && s_subs[i].dir.sin_addr.s_addr == de->sin_addr.s_addr &&
                s_subs[i].dir.sin_port == de->sin_port) {
            s_subs[i].vence_us = ahora + LEASE_US;
            return;
        }
        if ((!s_subs[i].activo || s_subs[i].vence_us <= ahora) && libre < 0) {
            libre = i;
        }
    }
    if (libre >= 0) {
        s_subs[libre].dir = *de;
        s_subs[libre].vence_us = ahora + LEASE_US;
        s_subs[libre].activo = true;
        ESP_LOGI(TAG, "suscriptor %d: " IPSTR ":%u", libre, IP2STR((esp_ip4_addr_t *)&de->sin_addr.s_addr),
                 ntohs(de->sin_port));
    }
}

static void desuscribir(const struct sockaddr_in *de)
{
    for (int i = 0; i < CONFIG_AURA_LOCAL_MAX_SUSCRIPTORES; i++) {
        if (s_subs[i].activo && s_subs[i].dir.sin_addr.s_addr == de->sin_addr.s_addr &&
                s_subs[i].dir.sin_port == de->sin_port) {
            s_subs[i].activo = false;
        }
    }
}

static void procesar_entrada(char *msg, int len, const struct sockaddr_in *de)
{
    msg[len] = '\0';
    while (len > 0 && (msg[len - 1] == '\n' || msg[len - 1] == '\r')) {
        msg[--len] = '\0';
    }
    if (strncmp(msg, "SUB", 3) == 0) {
        suscribir(de);
    } else if (strncmp(msg, "UNSUB", 5) == 0) {
        desuscribir(de);
    } else if (strncmp(msg, "TIEMPO ", 7) == 0) {
        char resp[96];
        int n = snprintf(resp, sizeof(resp), "TIEMPO %s %" PRId64 " %d", msg + 7, aura_tiempo_unix_us(),
                         aura_tiempo_sincronizado() ? 1 : 0);
        sendto(s_sock, resp, n, MSG_DONTWAIT, (const struct sockaddr *)de, sizeof(*de));
    } else if (strncmp(msg, "CMD ", 4) == 0) {
        /* "CMD <ctr> <hmac_hex> <texto>" */
        char *p = msg + 4;
        char *fin_ctr = strchr(p, ' ');
        if (!fin_ctr) {
            return;
        }
        *fin_ctr = '\0';
        char *hmac = fin_ctr + 1;
        char *fin_hmac = strchr(hmac, ' ');
        if (!fin_hmac) {
            return;
        }
        *fin_hmac = '\0';
        const char *texto = fin_hmac + 1;
        uint64_t ctr = strtoull(p, NULL, 10);
        char id[24];
        snprintf(id, sizeof(id), "%" PRIu64, ctr);
        if (aura_comandos_autenticar(ctr, texto, hmac)) {
            aura_comandos_encolar(AURA_ORIGEN_LOCAL, id, texto);
        } else {
            aura_comandos_rechazo(AURA_ORIGEN_LOCAL, id, "autenticacion fallida");
        }
    }
}

static void enviar_anuncio(int sock_anuncio)
{
    esp_netif_ip_info_t ip;
    if (!aura_wifi_ip(&ip)) {
        return;
    }
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_WIFI_STA);
    char msg[256];
    int n = snprintf(msg, sizeof(msg),
                     "AURA-ANUNCIO {\"id\":\"%s\",\"ip\":\"" IPSTR "\",\"puerto\":%d,\"ota\":%d,\"ver\":\"%s\","
                     "\"mac\":\"" MACSTR "\"}",
                     CONFIG_AURA_SENSOR_ID, IP2STR(&ip.ip), CONFIG_AURA_UDP_PUERTO, CONFIG_AURA_OTA_PUERTO,
                     esp_app_get_description()->version, MAC2STR(mac));
    struct sockaddr_in dst = {
        .sin_family = AF_INET,
        .sin_port = htons(CONFIG_AURA_ANUNCIO_PUERTO),
        .sin_addr.s_addr = htonl(INADDR_BROADCAST),
    };
    sendto(sock_anuncio, msg, n, MSG_DONTWAIT, (struct sockaddr *)&dst, sizeof(dst));
}

static void tarea_local(void *arg)
{
    (void)arg;
    char *dgrama = malloc(DGRAMA_MAX);
    char *entrada = malloc(512);
    if (!dgrama || !entrada) {
        ESP_LOGE(TAG, "sin memoria para buffers");
        vTaskDelete(NULL);
        return;
    }
    int64_t prox_anuncio = 0;
    int sock_anuncio = -1;
    while (true) {
        if (s_sock < 0) {
            if (!aura_wifi_conectado()) {
                vTaskDelay(pdMS_TO_TICKS(500));
                /* sin red: vaciar la cola para no acumular datos viejos */
                size_t len;
                void *it;
                while ((it = xRingbufferReceive(s_cola, &len, 0)) != NULL) {
                    vRingbufferReturnItem(s_cola, it);
                }
                continue;
            }
            s_sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
            sock_anuncio = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
            struct sockaddr_in loc = {
                .sin_family = AF_INET,
                .sin_port = htons(CONFIG_AURA_UDP_PUERTO),
                .sin_addr.s_addr = htonl(INADDR_ANY),
            };
            int si = 1;
            if (s_sock < 0 || sock_anuncio < 0 ||
                    bind(s_sock, (struct sockaddr *)&loc, sizeof(loc)) != 0 ||
                    setsockopt(sock_anuncio, SOL_SOCKET, SO_BROADCAST, &si, sizeof(si)) != 0) {
                ESP_LOGW(TAG, "no se pudo abrir el socket UDP; reintento en 2 s");
                if (s_sock >= 0) {
                    close(s_sock);
                }
                if (sock_anuncio >= 0) {
                    close(sock_anuncio);
                }
                s_sock = sock_anuncio = -1;
                vTaskDelay(pdMS_TO_TICKS(2000));
                continue;
            }
            ESP_LOGI(TAG, "via local activa en UDP %d (anuncios en %d)", CONFIG_AURA_UDP_PUERTO,
                     CONFIG_AURA_ANUNCIO_PUERTO);
        }

        /* 1) Entrada: suscripciones, hora y comandos (espera corta). */
        fd_set rd;
        FD_ZERO(&rd);
        FD_SET(s_sock, &rd);
        struct timeval tv = { .tv_sec = 0, .tv_usec = 10000 };
        if (select(s_sock + 1, &rd, NULL, NULL, &tv) > 0 && FD_ISSET(s_sock, &rd)) {
            struct sockaddr_in de;
            socklen_t dl = sizeof(de);
            int n = recvfrom(s_sock, entrada, 511, MSG_DONTWAIT, (struct sockaddr *)&de, &dl);
            if (n > 0) {
                procesar_entrada(entrada, n, &de);
            }
        }

        /* 2) Salida: vaciar la cola. */
        size_t len;
        uint8_t *item;
        int lote = 0;
        while (lote < 64 && (item = xRingbufferReceive(s_cola, &len, 0)) != NULL) {
            procesar_item(item, len, dgrama);
            vRingbufferReturnItem(s_cola, item);
            lote++;
        }

        /* 3) Anuncio periodico. */
        int64_t ahora = esp_timer_get_time();
        if (ahora >= prox_anuncio) {
            enviar_anuncio(sock_anuncio);
            prox_anuncio = ahora + ANUNCIO_US;
        }

        /* 4) Si se perdio la red, cerrar y volver a esperar. */
        if (!aura_wifi_conectado()) {
            close(s_sock);
            close(sock_anuncio);
            s_sock = sock_anuncio = -1;
            memset(s_subs, 0, sizeof(s_subs));
            ESP_LOGW(TAG, "red perdida: via local en espera");
        }
    }
}

esp_err_t aura_local_iniciar(void)
{
    s_cola = xRingbufferCreate(COLA_BYTES, RINGBUF_TYPE_NOSPLIT);
    if (!s_cola) {
        return ESP_ERR_NO_MEM;
    }
    BaseType_t ok = xTaskCreate(tarea_local, "aura_local", AURA_PILA_LOCAL, NULL, TAREA_PRIORIDAD, NULL);
    return ok == pdPASS ? ESP_OK : ESP_FAIL;
}
