# AURA nodo: wifi_sensing (esp-csi) + vía local UDP + vía nube Firebase + OTA local.
# Derivado de esp-csi/examples/esp-radar/wifi_sensing_demo (Apache-2.0).
cmake_minimum_required(VERSION 3.16)
add_compile_options(-fdiagnostics-color=always)

# Versión que se graba en la imagen (esp_app_desc_t.version); se sube en cada entrega.
set(PROJECT_VER "0.1.3")

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(aura_nodo)
