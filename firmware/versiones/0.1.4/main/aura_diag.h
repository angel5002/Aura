/*
 * AURA - diagnostico de la causa de las caidas de memoria (0.1.3, solo medicion; no cambia prioridades).
 *
 * - Uso de CPU por tarea (estadisticas de tiempo de ejecucion de FreeRTOS), incluidas tiT (tcpip de lwIP),
 *   wifi y las tareas del radar (csi_handle, csi_combine, prioridad 24).
 * - Cola de entrada de lwIP (buzon de la tarea tcpip): profundidad maxima y descartes por cola llena.
 * - Tramas que entran a la pila por destino (unicast / broadcast / multicast) y tipo (IPv4, IPv6, ARP), y las
 *   estadisticas de lwIP por protocolo (recibidas y descartadas).
 * Cada 10 s: {"type":"cpu"} y {"type":"pila_red"}. Si la memoria libre baja de CONFIG_AURA_DIAG_UMBRAL_KB, un
 * muestreador (cada 20 ms) sigue el episodio y al terminar emite {"type":"episodio"} con lo ocurrido desde
 * <= 1 s antes del inicio hasta el final.
 * La cola y las tramas se miden envolviendo tcpip_input y sys_mbox_new con --wrap del enlazador (CMakeLists).
 */
#pragma once

#include "esp_err.h"

esp_err_t aura_diag_iniciar(void);
/* Lo llama la telemetria en cada informe (cada 10 s). */
void aura_diag_intervalo(void);
