idf_component_register(SRCS "app_main.c"
                            "led_control.c"
                            "web_serial_monitor.c"
                            "aura_config.c"
                            "aura_salida.c"
                            "aura_wifi.c"
                            "aura_sensing.c"
                            "aura_comandos.c"
                            "aura_local.c"
                            "aura_ota.c"
                            "aura_nube.c"
                            "aura_tiempo.c"
                            "aura_telemetria.c"
                            "aura_diag.c"
                       INCLUDE_DIRS "."
                       REQUIRES esp_wifi_sensing
                                driver
                                esp_driver_ledc
                                led_strip
                                esp_wifi
                                esp_netif
                                esp_event
                                nvs_flash
                       PRIV_REQUIRES esp_driver_usb_serial_jtag
                                     esp_http_client
                                     esp-tls
                                     mbedtls
                                     json
                                     app_update
                                     esp_timer
                                     lwip
                                     esp_system)

# Diagnostico (aura_diag.c): envolver dos funciones de lwIP para medir la cola de entrada de la tarea tcpip y las
# tramas que entran a la pila, sin modificar lwIP. Solo cuenta y llama a la funcion original.
target_link_libraries(${COMPONENT_LIB} INTERFACE "-Wl,--wrap=tcpip_input" "-Wl,--wrap=sys_mbox_new")
