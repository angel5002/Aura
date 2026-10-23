/*
 * AURA - deteccion (esp_wifi_sensing) con un solo canal: el AP al que esta conectada la placa.
 * Se quitaron los canales MAC_1/MAC_2 del ejemplo (sin transmisores nunca salian de START).
 *
 * Al pasar a otra red (respaldo) cambia el AP y la puerta de enlace: esp_wifi_sensing guarda la
 * puerta de enlace en cache, asi que el detector se RECREA (vuelve a calibrar y el entrenamiento de
 * presencia se pierde hasta un nuevo TRAIN_START/TRAIN_STOP).
 */
#pragma once

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#include "esp_wifi_sensing.h"

typedef enum {
    AURA_ESTADO_CALIBRANDO = 0,
    AURA_ESTADO_MOVIMIENTO,
    AURA_ESTADO_PRESENCIA_QUIETA,
    AURA_ESTADO_VACIA,
    AURA_ESTADO_SIN_PRESENCIA_ENTRENADA,   /* estable, sin movimiento, presencia no entrenada */
} aura_estado_t;

typedef struct {
    aura_estado_t estado;
    bool movimiento;            /* con retencion CONFIG_AURA_RETENCION_MOV_S */
    bool presencia;             /* solo valida si presencia_entrenada */
    bool presencia_entrenada;   /* umbrales validos Y presencia lista; si no, la presencia es "no_disponible" */
    int64_t desde_us;           /* esp_timer: desde cuando esta en este estado */
    uint32_t cambios;           /* contador de cambios de estado */
    bool alerta_quietud;        /* PRESENCIA_QUIETA durante >= CONFIG_AURA_QUIETUD_MIN */
} aura_estado_info_t;

esp_err_t aura_sensing_iniciar(void);

/* Acceso al FSM protegido por mutex recursivo (el FSM puede recrearse). Devuelve NULL si no existe. */
esp_wifi_sensing_fsm_handle_t aura_sensing_fsm_tomar(void);
void aura_sensing_fsm_soltar(void);

/* Llamado por web_serial_monitor con cada muestra del canal AP. */
void aura_sensing_muestra(uint64_t ts_ms, bool movimiento, bool presencia, bool presencia_lista,
                          bool presencia_entrenada, float jitter, float wander, bool estable);

/* Vuelve a registrar la captura de CSI en esp-radar (tras cambios de configuracion del radar). */
void aura_sensing_reenganchar_csi(void);

void aura_sensing_estado(aura_estado_info_t *out);
const char *aura_sensing_estado_nombre(aura_estado_t e);
bool aura_sensing_activo(void);   /* hay detector corriendo */

/* --- Bloques para /crudo (los consume aura_nube) --- */
#define AURA_BLOQUE_MAX_MUESTRAS  512
#define AURA_BLOQUE_MAX_SUBP      64

typedef struct {
    int64_t t0_us, t1_us;                       /* hora UNIX (0 si no hay SNTP) */
    uint16_t n_jitter;
    uint16_t jitter_x1e4[AURA_BLOQUE_MAX_MUESTRAS];   /* jitter * 10000, saturado a 65535 */
    uint16_t n_mov, n_pres;                     /* muestras con movimiento / presencia */
    uint32_t n_csi;                             /* paquetes CSI acumulados */
    uint8_t n_subp;                             /* subportadoras validas */
    float amp_media[AURA_BLOQUE_MAX_SUBP];
    float amp_desv[AURA_BLOQUE_MAX_SUBP];
} aura_bloque_t;

/* Cierra el bloque actual (copia a out) y empieza uno nuevo. */
void aura_sensing_tomar_bloque(aura_bloque_t *out);

typedef struct {
    uint32_t csi_total;
    uint32_t recreaciones;
} aura_sensing_stats_t;
void aura_sensing_stats(aura_sensing_stats_t *out);
