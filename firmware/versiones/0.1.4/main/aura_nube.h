/*
 * AURA - via nube (Firebase Realtime Database por REST, plan Spark).
 *
 * Autenticacion: cuenta propia del dispositivo (correo/contrasena en NVS) contra Identity Toolkit
 * (accounts:signInWithPassword) -> idToken (1 h) + refreshToken; se renueva a los 50 min con
 * securetoken.googleapis.com. La clave de servicio NUNCA esta en la placa.
 * TLS: esp_http_client + esp_crt_bundle (bundle completo); la verificacion no se puede desactivar.
 *
 * Escribe (como el UID de la placa):
 *   /sensores/<id>/estado    al cambiar el estado
 *   /sensores/<id>/latido    cada CONFIG_AURA_NUBE_LATIDO_S
 *   /sensores/<id>/comando   resultado de cada comando (con origen)
 *   /crudo/<id>/<t0_ms>      bloque cada CONFIG_AURA_NUBE_BLOQUE_S
 * Lee:
 *   /comandos/<id>           cada CONFIG_AURA_NUBE_CONSULTA_S (consulta periodica, conexion reutilizada)
 */
#pragma once

#include <stdint.h>
#include "esp_err.h"
#include "aura_comandos.h"

typedef enum {
    AURA_NUBE_SIN_CREDENCIALES = 0,
    AURA_NUBE_SIN_RED,
    AURA_NUBE_ESPERANDO_HORA,
    AURA_NUBE_AUTENTICANDO,
    AURA_NUBE_OPERANDO,
    AURA_NUBE_ESPERA_REINTENTO,
} aura_nube_estado_t;

typedef struct {
    aura_nube_estado_t estado;
    uint32_t tokens_obtenidos;   /* inicios de sesion completos */
    uint32_t renovaciones;       /* renovaciones con refreshToken */
    uint32_t errores;
    uint32_t escrituras;
    uint32_t comandos;
    int ultimo_http;
    uint32_t espera_s;           /* espera creciente actual tras errores (5 ... 300 s) */
    uint32_t tls_handshakes;     /* conexiones TLS completadas (auth + base, incluidas reconexiones) */
    uint32_t tokens_vencidos;    /* 401 "Auth token is expired": se renueva y se reintenta */
    uint32_t rechazos;           /* 4xx que no son token vencido (reglas o datos invalidos) */
    uint32_t bloques_rechazados; /* bloques /crudo rechazados y emitidos completos por USB/via local */
} aura_nube_stats_t;

/* Prueba D7a-sim: durante <segundos> se bloquean en la placa solo las conexiones a Firebase (auth y base);
 * el WiFi, la via local y SNTP siguen. 0 = cancelar. */
void aura_nube_sim_sin_internet(uint32_t segundos);
uint32_t aura_nube_sim_restante_s(void);

esp_err_t aura_nube_iniciar(void);
void aura_nube_stats(aura_nube_stats_t *out);
const char *aura_nube_estado_nombre(aura_nube_estado_t e);
/* Callback de aura_comandos: registra el resultado para confirmarlo en /sensores/<id>/comando. */
void aura_nube_resultado_comando(const aura_cmd_resultado_t *res);
