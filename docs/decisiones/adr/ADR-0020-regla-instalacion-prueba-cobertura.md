# ADR-0020: Regla de instalación y prueba de cobertura como dirección

- **Estado:** Aceptada (2026-10-26)
- **Fecha:** 2026-10-26
- **Decide:** Deisy
- **Equipo donde se tomó:** conversación de diseño; registrada en la PC principal
- **Relacionadas:** reemplaza (en parte) a ADR-0014; ADR-0021

## Contexto
Medir distancias entre placas en cada instalación es irreal. L001 mostró además que un enlace sobre una mesa no
puede cruzarse (registrado en la laptop de campo, pendiente de copiar al repo).

## Decisión
No exigir medición de distancias. Regla de instalación: transmisor y placa a **2–3 m**, **misma altura** (~1 m) y
**zona de interés entre ambos equipos**. La **prueba de cobertura** (caminata corta → buena / débil / reubicar) es
la dirección de trabajo. La geometría se guarda solo como metadato (RSSI siempre).

## Alternativas consideradas
| Alternativa | Por qué no |
|---|---|
| Medir con cinta en cada sesión | Inviable fuera del laboratorio. |
| Modelo 3D de la habitación por fotos | No aporta a la detección (los objetos fijos no generan cambios; resolución ~7,5 m a 20 MHz). Útil solo para simulación futura. |

## Consecuencias
- Varias placas receptoras reducen la dependencia de la posición.
- La prueba de cobertura está por diseñar e implementar; hasta entonces solo rige la regla de instalación.
- La estimación de distancia con FTM queda aparte, por evaluar (ADR-0021).

## Evidencia
- Wang et al., zonas de Fresnel, UbiComp 2016, DOI 10.1145/2971648.2971744.
- L001: registrado en la laptop de campo, pendiente de copiar al repo.

## Cómo revertir
Volver a registrar distancias medidas en el protocolo.
