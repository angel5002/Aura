/*
 * AURA - diagnostico de memoria: CPU por tarea, cola de lwIP y trafico que entra a la pila. Ver aura_diag.h.
 */
#include <stdio.h>
#include <string.h>
#include <inttypes.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "freertos/semphr.h"
#include "esp_heap_caps.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "lwip/opt.h"
#include "lwip/pbuf.h"
#include "lwip/netif.h"
#include "lwip/sys.h"
#include "lwip/stats.h"
#include "arch/sys_arch.h"
#include "sdkconfig.h"

#include "aura_diag.h"
#include "aura_pilas.h"
#include "web_serial_monitor.h"

#define MAX_TAREAS      40
#define MUESTREO_MS     20
#define PRE_MS          1000           /* instantanea de referencia previa al episodio */
#define FIN_ESTABLE_MS  500
#define UMBRAL_INI      (CONFIG_AURA_DIAG_UMBRAL_KB * 1024U)
#define UMBRAL_FIN      (UMBRAL_INI + 10 * 1024U)
#define PRIO_DIAG       (configMAX_PRIORITIES - 1)   /* = radar: comparte CPU por turnos con el */

/* ---------------- lwIP: envolturas (--wrap) ---------------- */

err_t __real_tcpip_input(struct pbuf *p, struct netif *inp);
err_t __real_sys_mbox_new(sys_mbox_t *mbox, int size);

static sys_mbox_t *s_mbox_tcpip;        /* &tcpip_mbox (static en tcpip.c) */

typedef struct {
    uint32_t uni, bcast, mcast;         /* tramas que entran a la pila por destino */
    uint32_t ipv4, ipv6, arp, otro;     /* por tipo */
    uint32_t descartes_cola;            /* tcpip_input != ERR_OK (cola llena o sin memoria) */
    uint32_t ip_r, ip_d, ip6_r, ip6_d, udp_r, udp_d, tcp_r, tcp_d, icmp_r, icmp_d, arp_r, arp_d;
} contadores_t;

static volatile contadores_t s_c;
static volatile uint32_t s_cola_max_int, s_cola_max_ep;

/* Emisores de broadcast del intervalo (tabla aproximada de los mas frecuentes; se reinicia en cada informe).
 * MAC de origen de la trama e IP (remitente ARP, u origen IPv4). Solo se informa si hay tormenta. */
#define N_EMISORES      8
#define UMBRAL_TORMENTA 300     /* broadcast por intervalo de 10 s */
typedef struct {
    uint8_t mac[6];
    uint8_t ip[4];
    uint32_t n;
} emisor_t;
static emisor_t s_emisores[N_EMISORES];

static void contar_emisor(const uint8_t *e, uint16_t tipo, uint16_t len)
{
    uint8_t ip[4] = {0};
    if (tipo == 0x0806 && len >= 42) {
        memcpy(ip, e + 28, 4);          /* ARP: IP del remitente */
    } else if (tipo == 0x0800 && len >= 34) {
        memcpy(ip, e + 26, 4);          /* IPv4: origen */
    }
    int menor = 0;
    for (int i = 0; i < N_EMISORES; i++) {
        if (s_emisores[i].n && memcmp(s_emisores[i].mac, e + 6, 6) == 0) {
            s_emisores[i].n++;
            if (ip[0] || ip[1] || ip[2] || ip[3]) {
                memcpy(s_emisores[i].ip, ip, 4);
            }
            return;
        }
        if (s_emisores[i].n < s_emisores[menor].n) {
            menor = i;
        }
    }
    /* entrada nueva: reemplaza a la menos frecuente (hereda su cuenta + 1, como en "Space-Saving") */
    memcpy(s_emisores[menor].mac, e + 6, 6);
    memcpy(s_emisores[menor].ip, ip, 4);
    s_emisores[menor].n++;
}

err_t __wrap_sys_mbox_new(sys_mbox_t *mbox, int size)
{
    err_t err = __real_sys_mbox_new(mbox, size);
    if (err == ERR_OK && !s_mbox_tcpip && size == TCPIP_MBOX_SIZE) {
        s_mbox_tcpip = mbox;            /* el primer buzon de ese tamano es el de tcpip_init() */
    }
    return err;
}

static uint32_t profundidad_cola(void)
{
    if (!s_mbox_tcpip || !*s_mbox_tcpip || !(*s_mbox_tcpip)->os_mbox) {
        return 0;
    }
    return uxQueueMessagesWaiting((*s_mbox_tcpip)->os_mbox);
}

err_t __wrap_tcpip_input(struct pbuf *p, struct netif *inp)
{
    if (p && p->len >= 14) {
        const uint8_t *e = (const uint8_t *)p->payload;
        if (e[0] & 1) {
            bool bc = e[0] == 0xff && e[1] == 0xff && e[2] == 0xff && e[3] == 0xff && e[4] == 0xff && e[5] == 0xff;
            if (bc) {
                s_c.bcast++;
            } else {
                s_c.mcast++;
            }
        } else {
            s_c.uni++;
        }
        uint16_t tipo = (uint16_t)((e[12] << 8) | e[13]);
        if (e[0] == 0xff && e[1] == 0xff && e[2] == 0xff && e[3] == 0xff && e[4] == 0xff && e[5] == 0xff) {
            contar_emisor(e, tipo, p->len);
        }
        if (tipo == 0x0800) {
            s_c.ipv4++;
        } else if (tipo == 0x86DD) {
            s_c.ipv6++;
        } else if (tipo == 0x0806) {
            s_c.arp++;
        } else {
            s_c.otro++;
        }
    }
    err_t err = __real_tcpip_input(p, inp);
    if (err != ERR_OK) {
        s_c.descartes_cola++;
    }
    uint32_t d = profundidad_cola();
    if (d > s_cola_max_int) {
        s_cola_max_int = d;
    }
    if (d > s_cola_max_ep) {
        s_cola_max_ep = d;
    }
    return err;
}

static void leer_contadores(contadores_t *o)
{
    memcpy(o, (const void *)&s_c, sizeof(*o));
#if LWIP_STATS
    o->ip_r = lwip_stats.ip.recv;      o->ip_d = lwip_stats.ip.drop;
#if LWIP_IPV6 && IP6_STATS
    o->ip6_r = lwip_stats.ip6.recv;    o->ip6_d = lwip_stats.ip6.drop;
#endif
    o->udp_r = lwip_stats.udp.recv;    o->udp_d = lwip_stats.udp.drop;
    o->tcp_r = lwip_stats.tcp.recv;    o->tcp_d = lwip_stats.tcp.drop;
    o->icmp_r = lwip_stats.icmp.recv;  o->icmp_d = lwip_stats.icmp.drop;
    o->arp_r = lwip_stats.etharp.recv; o->arp_d = lwip_stats.etharp.drop;
#endif
}

/* Los contadores de lwIP son STAT_COUNTER (16 bits): la resta se hace en ese tipo para tolerar el desborde. */
#define D32(a, b, f)  ((uint32_t)((a)->f - (b)->f))
#define DST(a, b, f)  ((uint32_t)(STAT_COUNTER)((STAT_COUNTER)(a)->f - (STAT_COUNTER)(b)->f))

static int json_red(char *out, size_t cap, const contadores_t *a, const contadores_t *b)
{
    return snprintf(out, cap,
                    "\"entrada\":{\"uni\":%" PRIu32 ",\"bcast\":%" PRIu32 ",\"mcast\":%" PRIu32 ",\"ipv4\":%" PRIu32
                    ",\"ipv6\":%" PRIu32 ",\"arp\":%" PRIu32 ",\"otro\":%" PRIu32 ",\"descartes_cola\":%" PRIu32 "},"
                    "\"lwip\":{\"ip\":[%" PRIu32 ",%" PRIu32 "],\"ip6\":[%" PRIu32 ",%" PRIu32 "],\"udp\":[%" PRIu32 ",%" PRIu32
                    "],\"tcp\":[%" PRIu32 ",%" PRIu32 "],\"icmp\":[%" PRIu32 ",%" PRIu32 "],\"arp\":[%" PRIu32 ",%" PRIu32 "]}",
                    D32(a, b, uni), D32(a, b, bcast), D32(a, b, mcast), D32(a, b, ipv4), D32(a, b, ipv6), D32(a, b, arp),
                    D32(a, b, otro), D32(a, b, descartes_cola),
                    DST(a, b, ip_r), DST(a, b, ip_d), DST(a, b, ip6_r), DST(a, b, ip6_d), DST(a, b, udp_r), DST(a, b, udp_d),
                    DST(a, b, tcp_r), DST(a, b, tcp_d), DST(a, b, icmp_r), DST(a, b, icmp_d), DST(a, b, arp_r), DST(a, b, arp_d));
}

/* ---------------- CPU por tarea ---------------- */

typedef struct {
    TaskHandle_t h;
    uint32_t rt;
} marca_t;

typedef struct {
    marca_t m[MAX_TAREAS];
    int n;
    uint32_t total;
} instantanea_t;

static SemaphoreHandle_t s_mx;              /* protege s_estado (uxTaskGetSystemState) */
static TaskStatus_t s_estado[MAX_TAREAS];

static void tomar(instantanea_t *o)
{
    xSemaphoreTake(s_mx, portMAX_DELAY);
    uint32_t total = 0;
    UBaseType_t n = uxTaskGetSystemState(s_estado, MAX_TAREAS, &total);
    o->n = (int)n;
    o->total = total;
    for (UBaseType_t i = 0; i < n; i++) {
        o->m[i].h = s_estado[i].xHandle;
        o->m[i].rt = s_estado[i].ulRunTimeCounter;
    }
    xSemaphoreGive(s_mx);
}

static bool clave(const char *n)
{
    static const char *const K[] = { "tiT", "wifi", "csi_handle", "csi_combine", "IDLE", "aura_nube",
                                     "esp_wifi_sensing_fsm", "web_serial_moni" };
    for (size_t i = 0; i < sizeof(K) / sizeof(K[0]); i++) {
        if (strncmp(n, K[i], configMAX_TASK_NAME_LEN - 1) == 0) {
            return true;
        }
    }
    return false;
}

/* "[["tarea",prio,%cpu],...]" entre la instantanea 'base' y ahora. Incluye las tareas clave y las de >= 0,5 %. */
static int json_cpu(char *out, size_t cap, const instantanea_t *base, uint32_t *ventana_us)
{
    xSemaphoreTake(s_mx, portMAX_DELAY);
    uint32_t total = 0;
    UBaseType_t n = uxTaskGetSystemState(s_estado, MAX_TAREAS, &total);
    uint32_t dt = total - base->total;
    *ventana_us = dt;
    int u = snprintf(out, cap, "[");
    bool primero = true;
    for (UBaseType_t i = 0; i < n && u < (int)cap - 48; i++) {
        uint32_t rt0 = 0;
        for (int j = 0; j < base->n; j++) {
            if (base->m[j].h == s_estado[i].xHandle) {
                rt0 = base->m[j].rt;
                break;
            }
        }
        uint32_t d = s_estado[i].ulRunTimeCounter - rt0;
        float pct = dt ? 100.0f * (float)d / (float)dt : 0.0f;
        if (pct >= 0.5f || clave(s_estado[i].pcTaskName)) {
            u += snprintf(out + u, cap - u, "%s[\"%s\",%u,%.1f]", primero ? "" : ",", s_estado[i].pcTaskName,
                          (unsigned)s_estado[i].uxCurrentPriority, (double)pct);
            primero = false;
        }
    }
    xSemaphoreGive(s_mx);
    u += snprintf(out + u, cap - u, "]");
    return u;
}

/* ---------------- informe cada 10 s ---------------- */

static instantanea_t s_base_int;
static contadores_t s_cont_int;
static contadores_t s_cont_prev_bcast;

/* {"type":"tormenta","bcast":N,"top":[["mac","ip",n],...]} con los 3 emisores de broadcast mas frecuentes. */
static void emitir_tormenta(uint32_t bcast)
{
    emisor_t t[N_EMISORES];
    memcpy(t, s_emisores, sizeof(t));
    memset(s_emisores, 0, sizeof(s_emisores));
    if (bcast < UMBRAL_TORMENTA) {
        return;
    }
    char top[220];
    int u = snprintf(top, sizeof(top), "[");
    for (int k = 0; k < 3; k++) {
        int mejor = -1;
        for (int i = 0; i < N_EMISORES; i++) {
            if (t[i].n && (mejor < 0 || t[i].n > t[mejor].n)) {
                mejor = i;
            }
        }
        if (mejor < 0) {
            break;
        }
        const emisor_t *x = &t[mejor];
        u += snprintf(top + u, sizeof(top) - u, "%s[\"%02x:%02x:%02x:%02x:%02x:%02x\",\"%u.%u.%u.%u\",%" PRIu32 "]",
                      k ? "," : "", x->mac[0], x->mac[1], x->mac[2], x->mac[3], x->mac[4], x->mac[5],
                      x->ip[0], x->ip[1], x->ip[2], x->ip[3], x->n);
        t[mejor].n = 0;
    }
    snprintf(top + u, sizeof(top) - u, "]");
    web_serial_monitor_emitir("{\"type\":\"tormenta\",\"bcast\":%" PRIu32 ",\"top\":%s}", bcast, top);
}

void aura_diag_intervalo(void)
{
    if (!s_mx) {
        return;
    }
    static char cpu[760];
    static char red[420];
    uint32_t ventana_us = 0;
    json_cpu(cpu, sizeof(cpu), &s_base_int, &ventana_us);
    tomar(&s_base_int);
    web_serial_monitor_emitir("{\"type\":\"cpu\",\"ventana_ms\":%" PRIu32 ",\"t\":%s}", ventana_us / 1000, cpu);
    contadores_t c;
    leer_contadores(&c);
    json_red(red, sizeof(red), &c, &s_cont_int);
    s_cont_int = c;
    uint32_t cola_max = s_cola_max_int;
    s_cola_max_int = 0;
    web_serial_monitor_emitir("{\"type\":\"pila_red\",\"cola\":%" PRIu32 ",\"cola_max\":%" PRIu32 ",\"cola_tam\":%d,%s}",
                              profundidad_cola(), cola_max, TCPIP_MBOX_SIZE, red);
    emitir_tormenta(D32(&c, &s_cont_prev_bcast, bcast));
    s_cont_prev_bcast = c;
}

/* ---------------- episodios ---------------- */

static instantanea_t s_pre, s_base_ep;
static contadores_t s_cont_pre, s_cont_ep;

static void tarea_diag(void *arg)
{
    (void)arg;
    bool en_ep = false;
    int64_t t_pre = 0, t_ini = 0, t_estable = 0;
    uint32_t libre_min = 0, bloque_min = 0;
    static char cpu[640];
    static char red[420];
    while (true) {
        vTaskDelay(pdMS_TO_TICKS(MUESTREO_MS));
        int64_t ahora = esp_timer_get_time();
        uint32_t libre = esp_get_free_heap_size();
        if (!en_ep) {
            if (ahora - t_pre >= PRE_MS * 1000LL) {
                tomar(&s_pre);
                leer_contadores(&s_cont_pre);
                t_pre = ahora;
            }
            if (libre < UMBRAL_INI) {
                en_ep = true;
                t_ini = ahora;
                t_estable = 0;
                s_base_ep = s_pre;              /* referencia: <= 1 s antes del inicio */
                s_cont_ep = s_cont_pre;
                s_cola_max_ep = profundidad_cola();
                libre_min = libre;
                bloque_min = heap_caps_get_largest_free_block(MALLOC_CAP_DEFAULT);
            }
            continue;
        }
        if (libre < libre_min) {
            libre_min = libre;
        }
        uint32_t bloque = heap_caps_get_largest_free_block(MALLOC_CAP_DEFAULT);
        if (bloque < bloque_min) {
            bloque_min = bloque;
        }
        if (libre >= UMBRAL_FIN) {
            if (!t_estable) {
                t_estable = ahora;
            }
        } else {
            t_estable = 0;
        }
        bool termina = t_estable && ahora - t_estable >= FIN_ESTABLE_MS * 1000LL;
        bool largo = ahora - t_ini >= 20 * 1000000LL;        /* informar igual si dura mucho */
        if (termina || largo) {
            uint32_t ventana_us = 0;
            json_cpu(cpu, sizeof(cpu), &s_base_ep, &ventana_us);
            contadores_t c;
            leer_contadores(&c);
            json_red(red, sizeof(red), &c, &s_cont_ep);
            web_serial_monitor_emitir("{\"type\":\"episodio\",\"inicio_ms\":%" PRIu32 ",\"dur_ms\":%" PRIu32 ","
                                      "\"terminado\":%s,\"libre_min\":%" PRIu32 ",\"bloque_min\":%" PRIu32 ","
                                      "\"cola_max\":%" PRIu32 ",\"ventana_ms\":%" PRIu32 ",\"cpu\":%s,%s}",
                                      (uint32_t)(t_ini / 1000), (uint32_t)((ahora - t_ini) / 1000),
                                      termina ? "true" : "false", libre_min, bloque_min, s_cola_max_ep,
                                      ventana_us / 1000, cpu, red);
            en_ep = false;
            t_pre = 0;
        }
    }
}

esp_err_t aura_diag_iniciar(void)
{
    s_mx = xSemaphoreCreateMutex();
    if (!s_mx) {
        return ESP_ERR_NO_MEM;
    }
    tomar(&s_base_int);
    leer_contadores(&s_cont_int);
    return xTaskCreate(tarea_diag, "aura_diag", AURA_PILA_DIAG, NULL, PRIO_DIAG, NULL) == pdPASS ? ESP_OK : ESP_FAIL;
}
