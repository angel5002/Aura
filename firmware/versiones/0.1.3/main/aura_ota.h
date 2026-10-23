/*
 * AURA - OTA local autenticada por TCP (puerto CONFIG_AURA_OTA_PUERTO).
 *
 * Protocolo (una conexion por actualizacion):
 *   PC -> placa:  "AURAOTA <ctr> <tamano> <sha256_hex> <hmac_hex>\n"  y luego <tamano> bytes de la imagen .bin
 *                 hmac = HMAC-SHA256(clave_local, "<ctr> OTA <tamano> <sha256_hex>")
 *   placa -> PC:  "OK ...\n" o "ERROR <motivo>\n"
 * La placa calcula el SHA-256 mientras recibe y NO activa la imagen si no coincide con la cabecera
 * autenticada; esp_ota_end() valida ademas el formato de la imagen. La imagen nueva arranca en estado
 * PENDING_VERIFY y solo se marca valida tras la autoprueba (app_main.c); si no, el cargador vuelve
 * a la version anterior en el siguiente reinicio.
 * Limitacion (prototipo): sin secure boot ni cifrado de flash.
 */
#pragma once

#include "esp_err.h"

esp_err_t aura_ota_iniciar(void);
