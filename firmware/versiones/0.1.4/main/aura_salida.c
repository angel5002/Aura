/*
 * AURA - salida central de lineas (USB + via local).
 */
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/semphr.h"
#include "esp_log.h"
#include "driver/usb_serial_jtag.h"
#include "driver/usb_serial_jtag_vfs.h"

#include "aura_salida.h"
#include "aura_local.h"

#define HMS_PREFIJO "HMS:"

static SemaphoreHandle_t s_mx_usb;
static volatile uint32_t s_hms_total;
static volatile uint32_t s_usb_descartes;

static bool usb_disponible(void)
{
    /* Con cargador o bateria externa no hay SOF y nunca se considera conectado:
     * asi la placa no gasta tiempo escribiendo a un USB sin host. */
    return usb_serial_jtag_is_connected();
}

static void usb_escribir(const char *datos, size_t len)
{
    if (!usb_disponible()) {
        return;
    }
    int n = usb_serial_jtag_write_bytes(datos, len, 0);   /* nunca bloquea */
    if (n < (int)len) {
        s_usb_descartes += len - (n > 0 ? n : 0);
    }
}

static int aura_vprintf(const char *fmt, va_list args)
{
    char linea[256];
    int n = vsnprintf(linea, sizeof(linea), fmt, args);
    if (n <= 0) {
        return n;
    }
    size_t len = (n < (int)sizeof(linea)) ? (size_t)n : sizeof(linea) - 1;
    usb_escribir(linea, len);
    return n;
}

esp_err_t aura_salida_init(void)
{
    s_mx_usb = xSemaphoreCreateMutex();
    usb_serial_jtag_driver_config_t cfg = USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();
    cfg.tx_buffer_size = 4096;
    cfg.rx_buffer_size = 1024;
    esp_err_t err = usb_serial_jtag_driver_install(&cfg);
    if (err != ESP_OK) {
        return err;
    }
    usb_serial_jtag_vfs_use_driver();
    esp_log_set_vprintf(aura_vprintf);
    return ESP_OK;
}

void aura_salida_hms_va(const char *fmt, va_list args)
{
    /* "HMS:" + cuerpo + '\n'. Estatico (no en la pila de quien llama) y protegido por s_mx_usb, que
     * ademas evita que se mezclen lineas de distintas tareas. */
    static char linea[sizeof(HMS_PREFIJO) - 1 + AURA_SALIDA_HMS_MAX + 2] = HMS_PREFIJO;
    const size_t pre = sizeof(HMS_PREFIJO) - 1;
    if (!s_mx_usb) {
        return;
    }
    xSemaphoreTake(s_mx_usb, portMAX_DELAY);
    int n = vsnprintf(linea + pre, AURA_SALIDA_HMS_MAX + 1, fmt, args);
    if (n > 0) {
        size_t len = (n > AURA_SALIDA_HMS_MAX) ? AURA_SALIDA_HMS_MAX : (size_t)n;
        while (len > 0 && (linea[pre + len - 1] == '\n' || linea[pre + len - 1] == '\r')) {
            len--;
        }
        s_hms_total++;
        linea[pre + len] = '\n';
        /* Una sola escritura: el buffer del driver acepta la linea entera o nada (antes salian
         * lineas "HMS:" vacias cuando el buffer se llenaba con el puerto cerrado). */
        usb_escribir(linea, pre + len + 1);
        aura_local_encolar(AURA_LOCAL_TIPO_HMS, linea + pre, len);
    }
    xSemaphoreGive(s_mx_usb);
}

int aura_salida_leer_usb(uint8_t *buf, size_t len)
{
    return usb_serial_jtag_read_bytes(buf, len, 0);
}

void aura_salida_stats(aura_salida_stats_t *out)
{
    out->hms_total = s_hms_total;
    out->usb_descartes = s_usb_descartes;
    out->usb_conectado = usb_disponible() ? 1 : 0;
}
