"""Prepara las 4 fotos del video del equipo (todo local; las fotos son datos personales y nunca van a git).

    herramientas/recorte/.venv/Scripts/python.exe -I mockup/video/preparar_fotos_equipo.py recortar
    herramientas/recorte/.venv/Scripts/python.exe -I mockup/video/preparar_fotos_equipo.py igualar
    herramientas/recorte/.venv/Scripts/python.exe -I mockup/video/preparar_fotos_equipo.py hoja

- recortar: quita el fondo con rembg 2.0.86 y el modelo birefnet-portrait (modelo en herramientas/recorte/modelos;
  la foto no sale de la PC). Deja PNG con alfa en datos/procesados/video_equipo/recorte/.
- igualar: fondo blanco, mismo encuadre (cabeza y hombros: misma distancia entre ojos y misma altura de ojos, según
  datos/procesados/video_equipo/ojos.json, medido a mano sobre cada original), y brillo, contraste y temperatura de
  color de la cara llevados a un objetivo común (solo ajustes globales de color; sin filtros ni cambios de rasgos).
  Deja PNG cuadrados de 800 px en datos/procesados/video_equipo/fotos_listas/ y mide el verde cercano al de chroma.
- hoja: hoja de contacto ANTES / DESPUÉS con el nombre y el aviso de verde (datos/procesados/video_equipo/hoja_fotos.png).
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parents[2]
BASE = RAIZ / "datos" / "procesados" / "video_equipo"
FOTOS, RECORTE, LISTAS = BASE / "fotos", BASE / "recorte", BASE / "fotos_listas"
ORDEN = [("josue", "Josué Lovatón"), ("hideki", "Hideki Fukuhara"), ("angel", "Angel Vargas"), ("ida_luz", "Ida Luz Cumpa")]
LADO = 800                      # px del cuadrado final
OJOS_Y, ENTRE_OJOS = 0.43, 0.165   # altura de los ojos y distancia entre ojos, en fracción del lado
VERDE = (0x00, 0xB1, 0x40)       # verde de chroma del video


def archivo(nombre: str) -> Path:
    return next(FOTOS.glob(f"{nombre}.*"))


def recortar() -> None:
    os.environ["U2NET_HOME"] = str(RAIZ / "herramientas" / "recorte" / "modelos")
    import onnxruntime as ort
    from rembg import new_session, remove
    # birefnet-portrait pide bloques grandes: sin arena de memoria ni patrón y con 2 hilos para no quedarse sin RAM
    opciones = ort.SessionOptions()
    opciones.enable_cpu_mem_arena = False
    opciones.enable_mem_pattern = False
    opciones.intra_op_num_threads = opciones.inter_op_num_threads = 2
    sesion = new_session("birefnet-portrait", sess_opts=opciones)
    RECORTE.mkdir(parents=True, exist_ok=True)
    for nombre, _ in ORDEN:
        img = Image.open(archivo(nombre)).convert("RGB")
        salida = remove(img, session=sesion)          # RGBA, alfa suave del modelo (sin alpha matting extra)
        salida.save(RECORTE / f"{nombre}.png")
        a = np.asarray(salida)[..., 3]
        print(nombre, img.size, "alfa: opaco", round(float((a > 250).mean()), 3), "parcial", round(float(((a > 5) & (a <= 250)).mean()), 3))


def cbcr(rgb: np.ndarray) -> np.ndarray:
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    return np.stack([128 - 0.168736 * r - 0.331264 * g + 0.5 * b, 128 + 0.5 * r - 0.418688 * g - 0.081312 * b], -1)


def verde_cercano(rgb: np.ndarray, mascara: np.ndarray) -> dict:
    """Píxeles de la persona cuyo color (CbCr, como lo mira un keyer) cae cerca del verde de chroma."""
    d = np.linalg.norm(cbcr(rgb.astype(float)) - cbcr(np.array(VERDE, float)), axis=-1)
    m = mascara > 128
    total = int(m.sum())
    return {"riesgo_alto_px": int((d[m] < 40).sum()), "riesgo_medio_px": int(((d[m] >= 40) & (d[m] < 60)).sum()),
            "persona_px": total, "dist_min": round(float(d[m].min()), 1)}


def igualar() -> None:
    ojos = json.loads((BASE / "ojos.json").read_text(encoding="utf-8"))
    LISTAS.mkdir(parents=True, exist_ok=True)
    caras, imagenes = {}, {}
    for nombre, _ in ORDEN:
        rgba = Image.open(RECORTE / f"{nombre}.png").convert("RGBA")
        (xi, yi), (xd, yd) = ojos[nombre]["izq"], ojos[nombre]["der"]
        esc = (ENTRE_OJOS * LADO) / np.hypot(xd - xi, yd - yi)
        cx, cy = (xi + xd) / 2, (yi + yd) / 2
        # escala y traslada para que el punto medio de los ojos quede en (LADO/2, OJOS_Y·LADO); sin rotar
        w, h = rgba.size
        g = rgba.resize((round(w * esc), round(h * esc)), Image.LANCZOS)
        lienzo = Image.new("RGBA", (LADO, LADO), (255, 255, 255, 0))
        ox, oy = round(LADO / 2 - cx * esc), round(OJOS_Y * LADO - cy * esc)
        lienzo.paste(g, (ox, oy), g)
        imagenes[nombre] = lienzo
        # zona de la cara (para color): rectángulo alrededor de los ojos y la nariz, solo píxeles de la persona
        a = np.asarray(lienzo).astype(float)
        y0, y1 = int(OJOS_Y * LADO - 0.06 * LADO), int(OJOS_Y * LADO + 0.16 * LADO)
        x0, x1 = int(LADO / 2 - 0.1 * LADO), int(LADO / 2 + 0.1 * LADO)
        zona = a[y0:y1, x0:x1]
        caras[nombre] = zona[zona[..., 3] > 250][:, :3]
    # objetivo común: media de las 4 caras en luminancia, contraste y balance (r/g, b/g)
    lum = {n: c @ [0.2126, 0.7152, 0.0722] for n, c in caras.items()}
    obj_l, obj_s = np.mean([v.mean() for v in lum.values()]), np.mean([v.std() for v in lum.values()])
    obj_rg = np.mean([c[:, 0].mean() / c[:, 1].mean() for c in caras.values()])
    obj_bg = np.mean([c[:, 2].mean() / c[:, 1].mean() for c in caras.values()])
    informe = {}
    for nombre, _ in ORDEN:
        c = caras[nombre]
        a = np.asarray(imagenes[nombre]).astype(float)
        rgb, alfa = a[..., :3], a[..., 3:] / 255
        # temperatura: ganancias por canal hacia el balance común, a mitad de camino (corrige el tinte sin uniformar la piel)
        kr = 1 + 0.5 * (obj_rg / (c[:, 0].mean() / c[:, 1].mean()) - 1)
        kb = 1 + 0.5 * (obj_bg / (c[:, 2].mean() / c[:, 1].mean()) - 1)
        rgb = rgb * [kr, 1, kb]
        # brillo y contraste (lineal en luminancia, a mitad de camino del objetivo)
        l = c @ [0.2126, 0.7152, 0.0722]
        s = 1 + 0.5 * (obj_s / l.std() - 1)
        m = l.mean() * kr * 0.2126 + l.mean() * 0.7152 + l.mean() * kb * 0.0722
        rgb = (rgb - m) * s + m + 0.5 * (obj_l - l.mean())
        rgb = np.clip(rgb, 0, 255)
        final = rgb * alfa + 255 * (1 - alfa)            # sobre blanco
        Image.fromarray(final.round().astype(np.uint8)).save(LISTAS / f"{nombre}.png")
        informe[nombre] = {"escala": round(float(LADO * ENTRE_OJOS / np.hypot(*np.subtract(ojos[nombre]["der"], ojos[nombre]["izq"]))), 3),
                           "ganancia_r": round(float(kr), 3), "ganancia_b": round(float(kb), 3), "contraste": round(float(s), 3),
                           "brillo_cara_antes": round(float(l.mean()), 1),
                           "verde": verde_cercano(final, a[..., 3])}
    (BASE / "informe_fotos.json").write_text(json.dumps(informe, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(informe, indent=2, ensure_ascii=False))


def hoja() -> None:
    informe = json.loads((BASE / "informe_fotos.json").read_text(encoding="utf-8"))
    T, M = 360, 24
    fuente = ImageFont.truetype("arial.ttf", 20)
    chica = ImageFont.truetype("arial.ttf", 16)
    lienzo = Image.new("RGB", (M + 4 * (T + M), 2 * (T + 110) + M), (32, 36, 44))
    d = ImageDraw.Draw(lienzo)
    for k, (nombre, rotulo) in enumerate(ORDEN):
        x = M + k * (T + M)
        antes = Image.open(archivo(nombre)).convert("RGB")
        antes.thumbnail((T, T), Image.LANCZOS)
        caja = Image.new("RGB", (T, T), (60, 64, 72)); caja.paste(antes, ((T - antes.width) // 2, (T - antes.height) // 2))
        lienzo.paste(caja, (x, M))
        d.text((x, M + T + 8), f"{k + 1} · {rotulo} · ANTES", fill=(230, 233, 238), font=fuente)
        despues = Image.open(LISTAS / f"{nombre}.png").convert("RGB").resize((T, T), Image.LANCZOS)
        y = M + T + 110
        lienzo.paste(despues, (x, y))
        d.text((x, y + T + 8), f"{k + 1} · {rotulo} · DESPUÉS", fill=(230, 233, 238), font=fuente)
        v = informe[nombre]["verde"]
        aviso = (f"VERDE: {v['riesgo_alto_px']} px cerca del chroma" if v["riesgo_alto_px"]
                 else f"sin verde de chroma (mín. {v['dist_min']})")
        color = (255, 120, 100) if v["riesgo_alto_px"] else ((240, 190, 90) if v["riesgo_medio_px"] else (120, 220, 150))
        d.text((x, y + T + 36), aviso, fill=color, font=chica)
        if v["riesgo_medio_px"]:
            d.text((x, y + T + 58), f"{v['riesgo_medio_px']} px a distancia media", fill=(240, 190, 90), font=chica)
    lienzo.save(BASE / "hoja_fotos.png")
    print(BASE / "hoja_fotos.png")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    {"recortar": recortar, "igualar": igualar, "hoja": hoja}[sys.argv[1]]()
