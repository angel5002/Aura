/*
 * AURA - OTA local autenticada.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "lwip/sockets.h"
#include "mbedtls/sha256.h"

#include "aura_ota.h"
#include "aura_pilas.h"
#include "aura_wifi.h"
#include "aura_comandos.h"
#include "web_serial_monitor.h"

static const char *TAG = "aura_ota";
#define BLOQUE  4096

static void responder(int s, const char *txt)
{
    send(s, txt, strlen(txt), 0);
}

static void evento(const char *fase, const char *detalle)
{
    web_serial_monitor_emitir("{\"type\":\"ota\",\"fase\":\"%s\",\"detalle\":\"%s\"}", fase, detalle);
}

static int leer_linea(int s, char *buf, size_t cap)
{
    size_t n = 0;
    while (n + 1 < cap) {
        char c;
        int r = recv(s, &c, 1, 0);
        if (r <= 0) {
            return -1;
        }
        if (c == '\n') {
            break;
        }
        buf[n++] = c;
    }
    buf[n] = '\0';
    return (int)n;
}

static void atender(int s)
{
    struct timeval tv = { .tv_sec = 15, .tv_usec = 0 };
    setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

    char cab[320];
    if (leer_linea(s, cab, sizeof(cab)) <= 0) {
        return;
    }
    char sha_hex[65] = {0}, hmac_hex[65] = {0};
    uint64_t ctr = 0;
    uint32_t tamano = 0;
    if (sscanf(cab, "AURAOTA %" SCNu64 " %" SCNu32 " %64s %64s", &ctr, &tamano, sha_hex, hmac_hex) != 4) {
        responder(s, "ERROR cabecera\n");
        evento("rechazada", "cabecera invalida");
        return;
    }
    char firmado[96];
    snprintf(firmado, sizeof(firmado), "%" PRIu32 " %s", tamano, sha_hex);
    if (!aura_comandos_autenticar_ota(ctr, firmado, hmac_hex)) {
        responder(s, "ERROR autenticacion\n");
        evento("rechazada", "autenticacion fallida");
        ESP_LOGW(TAG, "OTA rechazada: autenticacion");
        return;
    }
    const esp_partition_t *actual = esp_ota_get_running_partition();
    esp_ota_img_states_t st;
    if (esp_ota_get_state_partition(actual, &st) == ESP_OK && st == ESP_OTA_IMG_PENDING_VERIFY) {
        responder(s, "ERROR la version actual aun no esta validada\n");
        evento("rechazada", "version actual pendiente de validar");
        return;
    }
    const esp_partition_t *destino = esp_ota_get_next_update_partition(NULL);
    if (!destino || tamano == 0 || tamano > destino->size) {
        responder(s, "ERROR tamano\n");
        evento("rechazada", "tamano invalido");
        return;
    }
    evento("inicio", destino->label);
    esp_ota_handle_t h;
    if (esp_ota_begin(destino, tamano, &h) != ESP_OK) {
        responder(s, "ERROR ota_begin\n");
        evento("error", "ota_begin");
        return;
    }
    responder(s, "LISTO\n");

    uint8_t *buf = malloc(BLOQUE);
    mbedtls_sha256_context sha;
    mbedtls_sha256_init(&sha);
    mbedtls_sha256_starts(&sha, 0);
    uint32_t recibido = 0;
    bool fallo = buf == NULL;
    while (!fallo && recibido < tamano) {
        int pedir = (tamano - recibido) < BLOQUE ? (int)(tamano - recibido) : BLOQUE;
        int r = recv(s, buf, pedir, 0);
        if (r <= 0) {
            fallo = true;
            break;
        }
        mbedtls_sha256_update(&sha, buf, r);
        if (esp_ota_write(h, buf, r) != ESP_OK) {
            fallo = true;
            break;
        }
        recibido += r;
    }
    uint8_t digest[32];
    mbedtls_sha256_finish(&sha, digest);
    mbedtls_sha256_free(&sha);
    free(buf);
    if (fallo) {
        esp_ota_abort(h);
        responder(s, "ERROR recepcion\n");
        evento("error", "recepcion incompleta");
        return;
    }
    char calc[65];
    for (int i = 0; i < 32; i++) {
        sprintf(calc + 2 * i, "%02x", digest[i]);
    }
    if (strcasecmp(calc, sha_hex) != 0) {
        esp_ota_abort(h);
        responder(s, "ERROR sha256\n");
        evento("rechazada", "sha256 no coincide");
        ESP_LOGW(TAG, "OTA rechazada: SHA-256 no coincide");
        return;
    }
    if (esp_ota_end(h) != ESP_OK) {
        responder(s, "ERROR imagen invalida\n");
        evento("rechazada", "imagen invalida (esp_ota_end)");
        return;
    }
    if (esp_ota_set_boot_partition(destino) != ESP_OK) {
        responder(s, "ERROR set_boot\n");
        evento("error", "set_boot_partition");
        return;
    }
    responder(s, "OK reiniciando\n");
    evento("ok", destino->label);
    ESP_LOGI(TAG, "OTA correcta en %s: reiniciando", destino->label);
    vTaskDelay(pdMS_TO_TICKS(1000));
    esp_restart();
}

static void tarea_ota(void *arg)
{
    (void)arg;
    int escucha = -1;
    while (true) {
        if (!aura_wifi_conectado()) {
            if (escucha >= 0) {
                close(escucha);
                escucha = -1;
            }
            vTaskDelay(pdMS_TO_TICKS(1000));
            continue;
        }
        if (escucha < 0) {
            escucha = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
            struct sockaddr_in dir = {
                .sin_family = AF_INET,
                .sin_port = htons(CONFIG_AURA_OTA_PUERTO),
                .sin_addr.s_addr = htonl(INADDR_ANY),
            };
            int si = 1;
            setsockopt(escucha, SOL_SOCKET, SO_REUSEADDR, &si, sizeof(si));
            if (escucha < 0 || bind(escucha, (struct sockaddr *)&dir, sizeof(dir)) != 0 || listen(escucha, 1) != 0) {
                if (escucha >= 0) {
                    close(escucha);
                }
                escucha = -1;
                vTaskDelay(pdMS_TO_TICKS(2000));
                continue;
            }
            struct timeval tv = { .tv_sec = 1, .tv_usec = 0 };
            setsockopt(escucha, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
        }
        struct sockaddr_in de;
        socklen_t dl = sizeof(de);
        int cli = accept(escucha, (struct sockaddr *)&de, &dl);
        if (cli >= 0) {
            atender(cli);
            shutdown(cli, SHUT_RDWR);
            close(cli);
        }
    }
}

esp_err_t aura_ota_iniciar(void)
{
    return xTaskCreate(tarea_ota, "aura_ota", AURA_PILA_OTA, NULL, 3, NULL) == pdPASS ? ESP_OK : ESP_FAIL;
}
