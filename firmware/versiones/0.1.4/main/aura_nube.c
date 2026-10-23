/*
 * AURA - via nube (Firebase REST).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <inttypes.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_http_client.h"
#include "esp_crt_bundle.h"
#include "esp_app_desc.h"
#include "cJSON.h"

#include "aura_nube.h"
#include "aura_pilas.h"
#include "aura_config.h"
#include "aura_wifi.h"
#include "aura_tiempo.h"
#include "aura_sensing.h"
#include "aura_telemetria.h"
#include "web_serial_monitor.h"

static const char *TAG = "aura_nube";

#define TAREA_PRIORIDAD   3
#define RESP_MAX          (CONFIG_AURA_NUBE_BUFFER_KB * 1024)
#define CUERPO_MAX        (CONFIG_AURA_NUBE_BUFFER_KB * 1024)
#define URL_MAX           2048
#define TOKEN_MAX         1600
#define REFRESH_MAX       600
#define RENOVAR_ANTES_US  (10LL * 60 * 1000000)    /* renovar 10 min antes de vencer (a los ~50 min) */
#define CMD_VIGENCIA_MS   (10LL * 60 * 1000)       /* comandos de mas de 10 min se rechazan */
#define MAX_PENDIENTES    6

typedef struct {
    char *buf;
    size_t cap;
    size_t len;
} respuesta_t;

static aura_nube_stats_t s_st;
static char *s_token;            /* idToken: NUNCA se imprime */
static char *s_refresh;          /* refreshToken: NUNCA se imprime */
static int64_t s_token_vence_us;
static char s_api_key[64];
static char s_db_url[160];
static esp_http_client_handle_t s_db;      /* conexion reutilizada con la base */
static char *s_url, *s_cuerpo, *s_resp;

static portMUX_TYPE s_mux_pend = portMUX_INITIALIZER_UNLOCKED;
static aura_cmd_resultado_t s_pend[MAX_PENDIENTES];
static int s_n_pend;
static volatile int64_t s_sim_hasta_us;     /* D7a-sim: hasta cuando se bloquean las conexiones a Firebase */
static bool s_sim_avisada;

void aura_nube_sim_sin_internet(uint32_t segundos)
{
    s_sim_hasta_us = segundos ? esp_timer_get_time() + (int64_t)segundos * 1000000LL : 0;
}

uint32_t aura_nube_sim_restante_s(void)
{
    int64_t falta = s_sim_hasta_us - esp_timer_get_time();
    return falta > 0 ? (uint32_t)(falta / 1000000LL) : 0;
}

/* true si la simulacion bloquea esta conexion: se comporta como un fallo de red (codigo -1). */
static bool sim_bloquea(void)
{
    bool activa = esp_timer_get_time() < s_sim_hasta_us;
    if (activa != s_sim_avisada) {
        s_sim_avisada = activa;
        ESP_LOGW(TAG, "SIM: conexiones a Firebase %s", activa ? "BLOQUEADAS" : "restablecidas");
    }
    return activa;
}

const char *aura_nube_estado_nombre(aura_nube_estado_t e)
{
    switch (e) {
    case AURA_NUBE_SIN_CREDENCIALES: return "sin_credenciales";
    case AURA_NUBE_SIN_RED:          return "sin_red";
    case AURA_NUBE_ESPERANDO_HORA:   return "esperando_hora";
    case AURA_NUBE_AUTENTICANDO:     return "autenticando";
    case AURA_NUBE_OPERANDO:         return "operando";
    case AURA_NUBE_ESPERA_REINTENTO: return "espera_reintento";
    default:                         return "?";
    }
}

void aura_nube_stats(aura_nube_stats_t *out)
{
    *out = s_st;
}

void aura_nube_resultado_comando(const aura_cmd_resultado_t *res)
{
    portENTER_CRITICAL(&s_mux_pend);
    if (s_n_pend < MAX_PENDIENTES) {
        s_pend[s_n_pend++] = *res;
    }
    portEXIT_CRITICAL(&s_mux_pend);
}

/* ---- marcas de diagnostico de memoria (TLS y sesion) ----
 * {"type":"tls","fase":"inicio|fin|fallo","destino":"auth|db",...}: "fin" = conexion TLS establecida
 * (HTTP_EVENT_ON_CONNECTED), con la duracion desde el inicio de la peticion. En la base, "inicio" solo se marca
 * al crear el cliente; una reconexion implicita del keep-alive aparece solo como "fin" con "reconexion":true. */
static const char *s_tls_destino = "?";
static int64_t s_tls_t0;
static bool s_db_nuevo;

static void marca_memoria(const char *tipo, const char *fase, const char *destino, const char *extra)
{
    web_serial_monitor_emitir("{\"type\":\"%s\",\"fase\":\"%s\",\"destino\":\"%s\",\"heap_libre\":%" PRIu32 ","
                              "\"heap_min_intervalo\":%" PRIu32 ",\"bloque_max\":%" PRIu32 ",\"encendido_ms\":%" PRIu32 "%s}",
                              tipo, fase, destino, esp_get_free_heap_size(), aura_telemetria_minimo_intervalo(),
                              aura_telemetria_bloque_max(), (uint32_t)(esp_timer_get_time() / 1000LL), extra ? extra : "");
}

static esp_err_t al_evento_http(esp_http_client_event_t *ev)
{
    if (ev->event_id == HTTP_EVENT_ON_CONNECTED) {
        s_st.tls_handshakes++;
        char extra[64];
        snprintf(extra, sizeof(extra), ",\"ms\":%" PRId64 ",\"reconexion\":%s",
                 (esp_timer_get_time() - s_tls_t0) / 1000, (strcmp(s_tls_destino, "db") == 0 && !s_db_nuevo) ? "true" : "false");
        marca_memoria("tls", "fin", s_tls_destino, extra);
        return ESP_OK;
    }
    respuesta_t *r = (respuesta_t *)ev->user_data;
    if (ev->event_id == HTTP_EVENT_ON_DATA && r && r->buf) {
        size_t libre = r->cap - 1 - r->len;
        size_t n = ev->data_len < (int)libre ? (size_t)ev->data_len : libre;
        memcpy(r->buf + r->len, ev->data, n);
        r->len += n;
        r->buf[r->len] = '\0';
    }
    return ESP_OK;
}

/* Peticion a un host de autenticacion (conexion de un solo uso). Devuelve el codigo HTTP o -1. */
static int peticion_auth(const char *url, const char *tipo, const char *cuerpo, respuesta_t *r)
{
    if (sim_bloquea()) {
        return -1;
    }
    esp_http_client_config_t cfg = {
        .url = url,
        .method = HTTP_METHOD_POST,
        .crt_bundle_attach = esp_crt_bundle_attach,
        .timeout_ms = 15000,
        .event_handler = al_evento_http,
        .user_data = r,
        .buffer_size = 2048,
        .buffer_size_tx = 1024,
    };
    esp_http_client_handle_t c = esp_http_client_init(&cfg);
    if (!c) {
        return -1;
    }
    esp_http_client_set_header(c, "Content-Type", tipo);
    esp_http_client_set_post_field(c, cuerpo, strlen(cuerpo));
    r->len = 0;
    r->buf[0] = '\0';
    s_tls_destino = "auth";
    s_tls_t0 = esp_timer_get_time();
    marca_memoria("tls", "inicio", "auth", NULL);
    esp_err_t err = esp_http_client_perform(c);
    int status = err == ESP_OK ? esp_http_client_get_status_code(c) : -1;
    esp_http_client_cleanup(c);
    if (err != ESP_OK) {
        char extra[64];
        snprintf(extra, sizeof(extra), ",\"error\":\"%s\"", esp_err_to_name(err));
        marca_memoria("tls", "fallo", "auth", extra);
    }
    return status;
}

static bool guardar_tokens(const char *json, const char *k_id, const char *k_refresh, const char *k_vence)
{
    cJSON *raiz = cJSON_Parse(json);
    if (!raiz) {
        return false;
    }
    const cJSON *id = cJSON_GetObjectItem(raiz, k_id);
    const cJSON *rf = cJSON_GetObjectItem(raiz, k_refresh);
    const cJSON *ve = cJSON_GetObjectItem(raiz, k_vence);
    bool ok = cJSON_IsString(id) && cJSON_IsString(rf) && strlen(id->valuestring) < TOKEN_MAX &&
              strlen(rf->valuestring) < REFRESH_MAX;
    if (ok) {
        strcpy(s_token, id->valuestring);
        strcpy(s_refresh, rf->valuestring);
        long seg = cJSON_IsString(ve) ? strtol(ve->valuestring, NULL, 10) : 3600;
        if (seg <= 0) {
            seg = 3600;
        }
        s_token_vence_us = esp_timer_get_time() + (int64_t)seg * 1000000LL;
    }
    cJSON_Delete(raiz);
    return ok;
}

static bool iniciar_sesion(void)
{
    char email[128], pass[128];
    if (aura_config_leer(AURA_CFG_FB_EMAIL, email, sizeof(email)) != ESP_OK ||
            aura_config_leer(AURA_CFG_FB_PASS, pass, sizeof(pass)) != ESP_OK) {
        return false;
    }
    cJSON *o = cJSON_CreateObject();
    cJSON_AddStringToObject(o, "email", email);
    cJSON_AddStringToObject(o, "password", pass);
    cJSON_AddBoolToObject(o, "returnSecureToken", true);
    char *cuerpo = cJSON_PrintUnformatted(o);
    cJSON_Delete(o);
    memset(pass, 0, sizeof(pass));
    memset(email, 0, sizeof(email));
    if (!cuerpo) {
        return false;
    }
    snprintf(s_url, URL_MAX, "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=%s", s_api_key);
    respuesta_t r = { .buf = s_resp, .cap = RESP_MAX };
    marca_memoria("auth", "inicio", "login", NULL);
    int st = peticion_auth(s_url, "application/json", cuerpo, &r);
    memset(cuerpo, 0, strlen(cuerpo));
    free(cuerpo);
    s_st.ultimo_http = st;
    bool ok = st == 200 && guardar_tokens(s_resp, "idToken", "refreshToken", "expiresIn");
    memset(s_resp, 0, RESP_MAX);
    char extra[48];
    snprintf(extra, sizeof(extra), ",\"ok\":%s,\"http\":%d", ok ? "true" : "false", st);
    marca_memoria("auth", "fin", "login", extra);
    if (ok) {
        if (s_st.tokens_obtenidos++ == 0) {
            aura_telemetria_hito("nube_sesion");      /* justo despues del primer handshake con Firebase */
        }
        ESP_LOGI(TAG, "sesion iniciada (token valido ~60 min)");
    } else {
        ESP_LOGW(TAG, "no se pudo iniciar sesion (HTTP %d)", st);
    }
    return ok;
}

static bool renovar_token(void)
{
    if (!s_refresh[0]) {
        return false;
    }
    snprintf(s_cuerpo, CUERPO_MAX, "grant_type=refresh_token&refresh_token=%s", s_refresh);
    snprintf(s_url, URL_MAX, "https://securetoken.googleapis.com/v1/token?key=%s", s_api_key);
    respuesta_t r = { .buf = s_resp, .cap = RESP_MAX };
    marca_memoria("auth", "inicio", "renovacion", NULL);
    int st = peticion_auth(s_url, "application/x-www-form-urlencoded", s_cuerpo, &r);
    memset(s_cuerpo, 0, CUERPO_MAX);
    s_st.ultimo_http = st;
    bool ok = st == 200 && guardar_tokens(s_resp, "id_token", "refresh_token", "expires_in");
    memset(s_resp, 0, RESP_MAX);
    char extra[48];
    snprintf(extra, sizeof(extra), ",\"ok\":%s,\"http\":%d", ok ? "true" : "false", st);
    marca_memoria("auth", "fin", "renovacion", extra);
    if (ok) {
        s_st.renovaciones++;
        ESP_LOGI(TAG, "token renovado");
    } else {
        ESP_LOGW(TAG, "no se pudo renovar el token (HTTP %d)", st);
    }
    return ok;
}

/* Tipo del ultimo error de la base (lo usa publicar_bloque para decidir si reintenta o conserva el bloque). */
typedef enum { NUBE_OK = 0, NUBE_ERR_RED, NUBE_ERR_TOKEN, NUBE_ERR_RECHAZO } nube_error_t;
static nube_error_t s_ultimo_error;

static const char *nombre_error(nube_error_t e)
{
    switch (e) {
    case NUBE_ERR_RED:     return "red";
    case NUBE_ERR_TOKEN:   return "token_vencido";
    case NUBE_ERR_RECHAZO: return "rechazo";
    default:               return "ok";
    }
}

/* Copia 'src' a 'dst' apta para ir dentro de una cadena JSON: comillas y barras se escapan; control -> espacio. */
static size_t copiar_json(char *dst, size_t cap, const char *src, size_t n)
{
    size_t u = 0;
    for (size_t i = 0; i < n && src[i] && u + 2 < cap; i++) {
        char c = src[i];
        if (c == '"' || c == '\\') {
            dst[u++] = '\\';
            dst[u++] = c;
        } else {
            dst[u++] = (c < 0x20) ? ' ' : c;
        }
    }
    dst[u] = '\0';
    return u;
}

/* {"type":"nube_error"}: ruta, codigo HTTP, tipo y cuerpo de la respuesta (mensajes de Firebase como
 * "Permission denied" o "Auth token is expired"; nunca lleva el token, que va en la URL y no se registra). */
static void emitir_error_nube(const char *op, const char *ruta, int st, const char *cuerpo)
{
    char c[200];
    copiar_json(c, sizeof(c), cuerpo, 160);
    ESP_LOGW(TAG, "%s %s -> HTTP %d (%s)", op, ruta, st, nombre_error(s_ultimo_error));
    web_serial_monitor_emitir("{\"type\":\"nube_error\",\"op\":\"%s\",\"ruta\":\"%s\",\"http\":%d,\"tipo\":\"%s\","
                              "\"cuerpo\":\"%s\"}", op, ruta, st, nombre_error(s_ultimo_error), c);
}

/* Un bloque /crudo rechazado por las reglas NO se descarta en silencio: se emite completo por USB y por la via
 * local en partes {"type":"bloque_rechazado","ruta","parte","de","datos"} (datos = trozo del JSON escapado). */
static void conservar_bloque_rechazado(const char *ruta, const char *cuerpo)
{
    static char trozo[1000];
    size_t total = strlen(cuerpo);
    const size_t PASO = 450;            /* escapado ocupa como maximo el doble */
    int de = (int)((total + PASO - 1) / PASO);
    for (int i = 0; i < de; i++) {
        copiar_json(trozo, sizeof(trozo), cuerpo + i * PASO, PASO);
        web_serial_monitor_emitir("{\"type\":\"bloque_rechazado\",\"ruta\":\"%s\",\"parte\":%d,\"de\":%d,\"datos\":\"%s\"}",
                                  ruta, i + 1, de, trozo);
    }
    s_st.bloques_rechazados++;
}

static void cerrar_db(void)
{
    if (s_db) {
        esp_http_client_cleanup(s_db);
        s_db = NULL;
    }
}

/* Peticion a la base reutilizando la conexion. ruta sin ".json". Devuelve el codigo HTTP o -1. */
static int peticion_db(esp_http_client_method_t metodo, const char *ruta, const char *cuerpo, respuesta_t *r)
{
    bool escritura = metodo != HTTP_METHOD_GET;
    if (sim_bloquea()) {
        cerrar_db();            /* como un corte real: la conexion abierta deja de servir */
        s_st.ultimo_http = -1;
        s_st.errores++;
        s_ultimo_error = NUBE_ERR_RED;
        return -1;
    }
    snprintf(s_url, URL_MAX, "%s%s.json?auth=%s%s", s_db_url, ruta, s_token, escritura ? "&print=silent" : "");
    /* Escrituras: con print=silent la respuesta correcta viene vacia; si hay error, su cuerpo queda aqui. */
    static char s_err_cuerpo[192];
    static respuesta_t r_err = { .buf = s_err_cuerpo, .cap = sizeof(s_err_cuerpo) };
    respuesta_t *dest = r ? r : &r_err;
    if (!s_db) {
        esp_http_client_config_t cfg = {
            .url = s_url,
            .crt_bundle_attach = esp_crt_bundle_attach,
            .timeout_ms = 10000,
            .keep_alive_enable = true,
            .event_handler = al_evento_http,
            .user_data = dest,
            .buffer_size = 2048,
            .buffer_size_tx = URL_MAX + 256,
        };
        s_db = esp_http_client_init(&cfg);
        if (!s_db) {
            return -1;
        }
        s_db_nuevo = true;
        marca_memoria("tls", "inicio", "db", NULL);
    } else {
        esp_http_client_set_url(s_db, s_url);
        esp_http_client_set_user_data(s_db, dest);
    }
    esp_http_client_set_method(s_db, metodo);
    if (cuerpo) {
        esp_http_client_set_header(s_db, "Content-Type", "application/json");
        esp_http_client_set_post_field(s_db, cuerpo, strlen(cuerpo));
    } else {
        esp_http_client_set_post_field(s_db, NULL, 0);
    }
    if (dest->buf) {
        dest->len = 0;
        dest->buf[0] = '\0';
    }
    s_tls_destino = "db";
    s_tls_t0 = esp_timer_get_time();
    esp_err_t err = esp_http_client_perform(s_db);
    s_db_nuevo = false;
    int st = -1;
    if (err == ESP_OK) {
        st = esp_http_client_get_status_code(s_db);
    } else if (err == ESP_ERR_NOT_SUPPORTED && esp_http_client_get_status_code(s_db) == 401) {
        /* esp_http_client corta en un 401 sin cabecera WWW-Authenticate (asi responde Firebase) antes de leer el
         * cuerpo: se lee aqui para saber si es un token vencido o un rechazo de reglas. */
        st = 401;
        char tmp[128];
        esp_http_client_read_response(s_db, tmp, sizeof(tmp));   /* el cuerpo llega a 'dest' por el evento */
    }
    s_st.ultimo_http = st;
    s_ultimo_error = NUBE_OK;
    if (st < 0) {
        char extra[64];
        snprintf(extra, sizeof(extra), ",\"error\":\"%s\"", esp_err_to_name(err));
        marca_memoria("tls", "fallo", "db", extra);
    }
    if (st >= 200 && st < 300) {
        if (escritura) {
            if (s_st.escrituras++ == 0) {
                aura_telemetria_hito("nube_primera_escritura");   /* pico con la sesion TLS de la base */
            }
        }
        return st;
    }
    s_st.errores++;
    const char *cuerpo_err = (dest->buf && dest->len) ? dest->buf : "";
    if (st < 0 || st >= 500) {
        s_ultimo_error = NUBE_ERR_RED;                  /* se reintenta */
    } else if (st == 401 && strstr(cuerpo_err, "expired")) {
        s_ultimo_error = NUBE_ERR_TOKEN;                /* renovar y reintentar */
        s_st.tokens_vencidos++;
        s_token_vence_us = 0;
    } else {
        s_ultimo_error = NUBE_ERR_RECHAZO;              /* reglas o datos: reintentar no sirve */
        s_st.rechazos++;
    }
    emitir_error_nube(escritura ? "escritura" : "lectura", ruta, st, cuerpo_err);
    cerrar_db();        /* tras un error la conexion puede quedar a medio leer: se reabre en la proxima peticion */
    return st;
}

static int64_t ms_unix(int64_t us)
{
    return us > 0 ? us / 1000 : 0;
}

/* Devuelve true si la base acepto la escritura. */
static bool publicar_estado(const aura_estado_info_t *e)
{
    int64_t desde = 0;
    int64_t ahora_unix = aura_tiempo_unix_us();
    if (ahora_unix) {
        desde = ms_unix(ahora_unix - (esp_timer_get_time() - e->desde_us));
    }
    /* presencia explicita: sin entrenamiento valido (arranque, cambio de red) es "no_disponible";
     * NUNCA "vacia" si no esta entrenada. Las reglas .validate de Firebase exigen lo mismo. */
    const char *presencia = !e->presencia_entrenada ? "no_disponible" : (e->presencia ? "presente" : "vacia");
    snprintf(s_cuerpo, CUERPO_MAX,
             "{\"estado\":\"%s\",\"mov\":%s,\"presencia\":\"%s\",\"entrenada\":%s,\"alerta\":%s,\"desde\":%" PRId64 ","
             "\"t\":{\".sv\":\"timestamp\"}}",
             aura_sensing_estado_nombre(e->estado), e->movimiento ? "true" : "false",
             presencia, e->presencia_entrenada ? "true" : "false",
             e->alerta_quietud ? "true" : "false", desde);
    char ruta[64];
    snprintf(ruta, sizeof(ruta), "/sensores/%s/estado", CONFIG_AURA_SENSOR_ID);
    int st = peticion_db(HTTP_METHOD_PUT, ruta, s_cuerpo, NULL);
    return st >= 200 && st < 300;
}

static void publicar_latido(void)
{
    aura_telemetria_t t;
    aura_telemetria_ultima(&t);
    snprintf(s_cuerpo, CUERPO_MAX,
             "{\"t\":{\".sv\":\"timestamp\"},\"up\":%" PRIu32 ",\"heap\":%" PRIu32 ",\"heap_min\":%" PRIu32 ","
             "\"red\":\"%s\",\"rssi\":%d,\"ver\":\"%s\",\"renov\":%" PRIu32 ",\"hms_s\":%.1f,\"ts_p95\":%.1f,"
             "\"reinicio\":\"%s\"}",
             t.encendido_s, t.heap_libre, t.heap_minimo, aura_wifi_red_nombre(aura_wifi_red_activa()),
             aura_wifi_rssi(), esp_app_get_description()->version, s_st.renovaciones, (double)t.hms_por_s,
             (double)t.ts_p95_ms, aura_telemetria_motivo_reinicio());
    char ruta[64];
    snprintf(ruta, sizeof(ruta), "/sensores/%s/latido", CONFIG_AURA_SENSOR_ID);
    peticion_db(HTTP_METHOD_PUT, ruta, s_cuerpo, NULL);
}

static size_t lista_u16(char *out, size_t cap, const uint16_t *v, int n)
{
    size_t u = 0;
    for (int i = 0; i < n && u + 8 < cap; i++) {
        u += snprintf(out + u, cap - u, "%s%u", i ? "," : "", v[i]);
    }
    return u;
}

static size_t lista_f(char *out, size_t cap, const float *v, int n)
{
    size_t u = 0;
    for (int i = 0; i < n && u + 12 < cap; i++) {
        u += snprintf(out + u, cap - u, "%s%.1f", i ? "," : "", (double)v[i]);
    }
    return u;
}

static void publicar_bloque(void)
{
    static aura_bloque_t b;     /* ~2,6 KB: fuera de la pila */
    static bool pendiente;      /* el bloque anterior fallo por red o token: se reintenta antes de tomar otro */
    if (!pendiente) {
        aura_sensing_tomar_bloque(&b);
        if (b.t0_us == 0 || b.t1_us == 0 || b.n_jitter == 0) {
            return;     /* sin hora o sin muestras: no se publica */
        }
    }
    size_t u = snprintf(s_cuerpo, CUERPO_MAX,
                        "{\"t0\":%" PRId64 ",\"t1\":%" PRId64 ",\"n\":%u,\"mov\":%u,\"pres\":%u,\"ncsi\":%" PRIu32 ","
                        "\"nsub\":%u,\"jit\":\"",
                        ms_unix(b.t0_us), ms_unix(b.t1_us), b.n_jitter, b.n_mov, b.n_pres, b.n_csi, b.n_subp);
    u += lista_u16(s_cuerpo + u, CUERPO_MAX - u - 400, b.jitter_x1e4, b.n_jitter);
    u += snprintf(s_cuerpo + u, CUERPO_MAX - u, "\",\"am\":\"");
    u += lista_f(s_cuerpo + u, CUERPO_MAX - u - 200, b.amp_media, b.n_subp);
    u += snprintf(s_cuerpo + u, CUERPO_MAX - u, "\",\"ad\":\"");
    u += lista_f(s_cuerpo + u, CUERPO_MAX - u - 20, b.amp_desv, b.n_subp);
    snprintf(s_cuerpo + u, CUERPO_MAX - u, "\"}");
    char ruta[80];
    snprintf(ruta, sizeof(ruta), "/crudo/%s/%" PRId64, CONFIG_AURA_SENSOR_ID, ms_unix(b.t0_us));
    int st = peticion_db(HTTP_METHOD_PUT, ruta, s_cuerpo, NULL);
    if (st >= 200 && st < 300) {
        pendiente = false;
    } else if (s_ultimo_error == NUBE_ERR_RECHAZO) {
        conservar_bloque_rechazado(ruta, s_cuerpo);      /* reintentar no sirve: se emite completo y se cuenta */
        pendiente = false;
    } else {
        pendiente = true;                                /* red o token vencido: mismo bloque en el proximo ciclo */
    }
}

static void confirmar_comandos(void)
{
    aura_cmd_resultado_t copia[MAX_PENDIENTES];
    int n;
    portENTER_CRITICAL(&s_mux_pend);
    n = s_n_pend;
    memcpy(copia, s_pend, n * sizeof(aura_cmd_resultado_t));
    s_n_pend = 0;
    portEXIT_CRITICAL(&s_mux_pend);
    char ruta[64];
    snprintf(ruta, sizeof(ruta), "/sensores/%s/comando", CONFIG_AURA_SENSOR_ID);
    for (int i = 0; i < n; i++) {
        cJSON *o = cJSON_CreateObject();
        cJSON_AddStringToObject(o, "id", copia[i].id);
        cJSON_AddStringToObject(o, "cmd", copia[i].cmd);
        cJSON_AddBoolToObject(o, "ok", copia[i].ok);
        cJSON_AddStringToObject(o, "detalle", copia[i].detalle);
        cJSON_AddStringToObject(o, "origen", aura_comandos_origen_nombre(copia[i].origen));
        cJSON *t = cJSON_AddObjectToObject(o, "t");
        cJSON_AddStringToObject(t, ".sv", "timestamp");
        char *txt = cJSON_PrintUnformatted(o);
        cJSON_Delete(o);
        if (txt) {
            peticion_db(HTTP_METHOD_PUT, ruta, txt, NULL);
            free(txt);
        }
    }
}

static int cmp_str(const void *a, const void *b)
{
    return strcmp(*(const char *const *)a, *(const char *const *)b);
}

static void consultar_comandos(char *ultimo_id, size_t cap_id)
{
    char ruta[64];
    snprintf(ruta, sizeof(ruta), "/comandos/%s", CONFIG_AURA_SENSOR_ID);
    respuesta_t r = { .buf = s_resp, .cap = RESP_MAX };
    if (peticion_db(HTTP_METHOD_GET, ruta, NULL, &r) != 200 || r.len == 0 || strcmp(s_resp, "null") == 0) {
        return;
    }
    cJSON *raiz = cJSON_Parse(s_resp);
    if (!cJSON_IsObject(raiz)) {
        cJSON_Delete(raiz);
        return;
    }
    /* Ordenar por id (los push id de Firebase son cronologicos) y ejecutar solo los nuevos. */
    const char *ids[16];
    int n = 0;
    cJSON *it;
    cJSON_ArrayForEach(it, raiz) {
        if (n < 16 && it->string && strcmp(it->string, ultimo_id) > 0) {
            ids[n++] = it->string;
        }
    }
    qsort(ids, n, sizeof(ids[0]), cmp_str);
    int64_t ahora_ms = ms_unix(aura_tiempo_unix_us());
    for (int i = 0; i < n; i++) {
        const cJSON *c = cJSON_GetObjectItem(raiz, ids[i]);
        const cJSON *cmd = cJSON_GetObjectItem(c, "cmd");
        const cJSON *t = cJSON_GetObjectItem(c, "t");
        snprintf(ultimo_id, cap_id, "%s", ids[i]);
        aura_config_guardar_str("nube_ult_cmd", ultimo_id);   /* no re-ejecutar tras un reinicio */
        s_st.comandos++;
        if (!cJSON_IsString(cmd)) {
            aura_comandos_rechazo(AURA_ORIGEN_NUBE, ids[i], "comando mal formado");
            continue;
        }
        if (ahora_ms && cJSON_IsNumber(t) && ahora_ms - (int64_t)t->valuedouble > CMD_VIGENCIA_MS) {
            aura_comandos_rechazo(AURA_ORIGEN_NUBE, ids[i], "comando vencido (>10 min)");
            continue;
        }
        aura_comandos_encolar(AURA_ORIGEN_NUBE, ids[i], cmd->valuestring);
    }
    cJSON_Delete(raiz);
}

static bool cargar_credenciales(void)
{
    if (aura_config_leer(AURA_CFG_FB_API_KEY, s_api_key, sizeof(s_api_key)) != ESP_OK ||
            aura_config_leer(AURA_CFG_FB_DB_URL, s_db_url, sizeof(s_db_url)) != ESP_OK ||
            !aura_config_definida(AURA_CFG_FB_EMAIL) || !aura_config_definida(AURA_CFG_FB_PASS)) {
        return false;
    }
    size_t n = strlen(s_db_url);
    if (n && s_db_url[n - 1] == '/') {
        s_db_url[n - 1] = '\0';
    }
    return true;
}

static void tarea_nube(void *arg)
{
    (void)arg;
    int espera_s = 5;
    char ultimo_id[40] = "";
    aura_config_leer_str("nube_ult_cmd", ultimo_id, sizeof(ultimo_id));
    int64_t prox_latido = 0, prox_bloque = 0, prox_consulta = 0;
    aura_estado_t ultimo_estado = (aura_estado_t)-1;
    bool ultima_alerta = false;

    while (true) {
        if (!cargar_credenciales()) {
            s_st.estado = AURA_NUBE_SIN_CREDENCIALES;
            vTaskDelay(pdMS_TO_TICKS(30000));
            continue;
        }
        if (!aura_wifi_conectado()) {
            s_st.estado = AURA_NUBE_SIN_RED;
            cerrar_db();
            vTaskDelay(pdMS_TO_TICKS(1000));
            continue;
        }
        if (!aura_tiempo_sincronizado()) {
            /* TLS verifica la vigencia de los certificados: sin hora no se puede validar. */
            s_st.estado = AURA_NUBE_ESPERANDO_HORA;
            vTaskDelay(pdMS_TO_TICKS(1000));
            continue;
        }
        int64_t ahora = esp_timer_get_time();
        if (!s_token[0] || ahora > s_token_vence_us - RENOVAR_ANTES_US) {
            s_st.estado = AURA_NUBE_AUTENTICANDO;
            /* Cerrar la sesion TLS con la base antes de abrir la de autenticacion: asi nunca hay dos
             * sesiones TLS a la vez (evita sumar ~20-30 KB al pico de RAM). */
            cerrar_db();
            bool ok = (s_token[0] && renovar_token()) || iniciar_sesion();
            if (!ok) {
                s_token[0] = '\0';
                s_st.errores++;
                s_st.estado = AURA_NUBE_ESPERA_REINTENTO;
                s_st.espera_s = espera_s;
                vTaskDelay(pdMS_TO_TICKS(espera_s * 1000));
                espera_s = espera_s * 2 > 300 ? 300 : espera_s * 2;   /* 5, 10, 20 ... 300 s */
                continue;
            }
            espera_s = 5;
            ultimo_estado = (aura_estado_t)-1;     /* republicar el estado con la sesion nueva */
        }
        s_st.estado = AURA_NUBE_OPERANDO;
        uint32_t errores_antes = s_st.errores;

        aura_estado_info_t e;
        aura_sensing_estado(&e);
        if (e.estado != ultimo_estado || e.alerta_quietud != ultima_alerta) {
            /* Solo se da por publicado si la base lo acepto: un cambio durante un corte se reenvia al volver. */
            if (publicar_estado(&e)) {
                ultimo_estado = e.estado;
                ultima_alerta = e.alerta_quietud;
            }
        }
        confirmar_comandos();
        ahora = esp_timer_get_time();
        if (ahora >= prox_latido) {
            publicar_latido();
            prox_latido = ahora + (int64_t)CONFIG_AURA_NUBE_LATIDO_S * 1000000LL;
        }
        if (ahora >= prox_bloque) {
            if (prox_bloque) {
                publicar_bloque();
            } else {
                aura_bloque_t *descartar = malloc(sizeof(aura_bloque_t));
                if (descartar) {      /* primer ciclo: empezar un bloque limpio */
                    aura_sensing_tomar_bloque(descartar);
                    free(descartar);
                }
            }
            prox_bloque = ahora + (int64_t)CONFIG_AURA_NUBE_BLOQUE_S * 1000000LL;
        }
        if (ahora >= prox_consulta) {
            consultar_comandos(ultimo_id, sizeof(ultimo_id));
            prox_consulta = ahora + (int64_t)CONFIG_AURA_NUBE_CONSULTA_S * 1000000LL;
        }

        if (s_st.errores > errores_antes + 2) {
            /* varios errores seguidos: esperar con espera creciente sin bloquear el resto del sistema */
            cerrar_db();
            s_st.estado = AURA_NUBE_ESPERA_REINTENTO;
            s_st.espera_s = espera_s;
            vTaskDelay(pdMS_TO_TICKS(espera_s * 1000));
            espera_s = espera_s * 2 > 300 ? 300 : espera_s * 2;
        } else {
            if (s_st.errores == errores_antes) {
                espera_s = 5;       /* ciclo sin errores: la proxima falla vuelve a empezar en 5 s */
                s_st.espera_s = 0;
            }
            vTaskDelay(pdMS_TO_TICKS(500));
        }
    }
}

esp_err_t aura_nube_iniciar(void)
{
    s_token = calloc(1, TOKEN_MAX);
    s_refresh = calloc(1, REFRESH_MAX);
    s_url = malloc(URL_MAX);
    s_cuerpo = malloc(CUERPO_MAX);
    s_resp = malloc(RESP_MAX);
    if (!s_token || !s_refresh || !s_url || !s_cuerpo || !s_resp) {
        return ESP_ERR_NO_MEM;
    }
    /* Ningun componente debe imprimir URLs (llevan ?auth=<token>): solo advertencias. */
    esp_log_level_set("HTTP_CLIENT", ESP_LOG_WARN);
    esp_log_level_set("esp-tls", ESP_LOG_WARN);
    esp_log_level_set("esp-tls-mbedtls", ESP_LOG_WARN);
    esp_log_level_set("transport_base", ESP_LOG_WARN);
    return xTaskCreate(tarea_nube, "aura_nube", AURA_PILA_NUBE, NULL, TAREA_PRIORIDAD, NULL) == pdPASS ? ESP_OK : ESP_FAIL;
}
