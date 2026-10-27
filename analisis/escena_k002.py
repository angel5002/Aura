"""Escena Three.js de K002: prepara los datos reales y sirve la pagina en 127.0.0.1 (solo esta PC).

    python escena_k002.py preparar              (datos de K002 -> datos/procesados/video_K002/escena/)
    python escena_k002.py servir --puerto 8765  (sirve esa carpeta y guarda las capturas que envia la pagina)

- Lee datos/crudos/K002_local.csv en solo lectura (t = 0 en el primer datagrama, como k002_cruces.py) y escribe
  datos_k002.js con: muestras del detector (t, motion_status, smooth, umbral de entrada), tasa de CSI por segundo y
  el primer positivo de cada cruce (criterio de K002). La plantilla analisis/escena_k002/index.html se copia al lado.
- La salida queda en datos/procesados (fuera de git): son datos de una prueba con una persona.
- POST /guardar?nombre=<archivo>.png guarda la imagen (PNG en base64) en datos/procesados/video_K002/capturas/.
- Video: la pagina (?video=<nombre>.mp4) envia cada cuadro a POST /video/cuadro; el servidor los pasa a ffmpeg por
  tuberia (H.264, 1920x1080, 30 fps) y al terminar escribe <nombre>.json con el resultado, junto al MP4.
- La figura usa el modelo "Animated Human" de Quaternius (CC0, poly.pizza/m/c3Ibh9I3udk), descargado con
  autorizacion de Deisy en escena/modelos/ (fuera de git). 'preparar' comprueba su SHA-256.
"""

import argparse
import base64
import csv
import hashlib
import json
import re
import shutil
import subprocess
import threading
import time
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from aura_proto import parsear_datagrama

RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "datos" / "crudos" / "K002_local.csv"
PLANTILLA = Path(__file__).resolve().parent / "escena_k002" / "index.html"
DESTINO = RAIZ / "datos" / "procesados" / "video_K002" / "escena"
CAPTURAS = RAIZ / "datos" / "procesados" / "video_K002" / "capturas"
MODELO = DESTINO / "modelos" / "quaternius_animated_human.glb"
VIDEOS = RAIZ / "datos" / "procesados" / "video_K002"
FFMPEG = Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe"
FPS = 30
MODELO_SHA256 = "ce4d543e82e455d5a1253798c9759f12b9eec74929ddbca464447eeaa3a42c5d"
CRUCES = [30 + 25 * k for k in range(10)]
ANTES_S, DESPUES_S = 3.0, 8.0


def preparar() -> int:
    t, mov, suave, entrada, csi_t = [], [], [], [], []
    t0 = None
    with open(ENTRADA, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        next(r, None)
        for fila in r:
            d = parsear_datagrama(fila[1]) if len(fila) > 1 else None
            if d is None:
                continue
            tt = float(fila[0])
            t0 = tt if t0 is None else t0
            if d.tipo == "csi":
                csi_t.append(tt - t0)
            elif '"type":"sample"' in d.cuerpo:
                m = json.loads(d.cuerpo)
                t.append(round(tt - t0, 3))
                mov.append(1 if m.get("motion_status") else 0)
                suave.append(round(m.get("smooth_scaled", 0) / 1e6, 4))
                entrada.append(round(m.get("enter_level_scaled", 0) / 1e6, 4))
    n_seg = int(max(csi_t)) + 1 if csi_t else 0
    tasa = [0] * n_seg
    for x in csi_t:
        tasa[int(x)] += 1
    primeros = []
    for tc in CRUCES:
        p = next((ti for ti, mi in zip(t, mov) if mi and tc - ANTES_S <= ti <= tc + DESPUES_S), None)
        primeros.append(p)
    datos = {"t": t, "mov": mov, "suave": suave, "entrada": entrada, "tasa_csi": tasa, "cruces": CRUCES,
             "primer_positivo": primeros, "fuente": "datos/crudos/K002_local.csv"}
    DESTINO.mkdir(parents=True, exist_ok=True)
    (DESTINO / "datos_k002.js").write_text("window.DATOS_K002 = " + json.dumps(datos, separators=(",", ":")) + ";\n",
                                           encoding="utf-8")
    shutil.copy2(PLANTILLA, DESTINO / "index.html")
    print(f"{len(t)} muestras, {len(csi_t)} CSI en {n_seg} s; detectados {sum(p is not None for p in primeros)}/10")
    if not MODELO.exists():
        print(f"AVISO: falta el modelo de la figura ({MODELO}); la escena no se dibuja sin el")
    elif hashlib.sha256(MODELO.read_bytes()).hexdigest() != MODELO_SHA256:
        print(f"AVISO: el SHA-256 de {MODELO.name} no coincide con el descargado el 27/10/2026")
    print(f"Escena en {DESTINO}")
    return 0


class Video:
    """Un solo video a la vez: ffmpeg recibe los PNG por la entrada estandar, en el orden en que llegan."""
    candado = threading.Lock()
    proc = None
    ruta = None
    esperados = 0
    recibidos = 0
    inicio = 0.0


def responder(h, codigo: int, texto: str = "ok"):
    h.send_response(codigo)
    h.end_headers()
    h.wfile.write(texto.encode("utf-8"))


class Manejador(SimpleHTTPRequestHandler):
    def do_POST(self):
        u = urlparse(self.path)
        if u.path.startswith("/video/"):
            return self.video(u)
        nombre = parse_qs(u.query).get("nombre", [""])[0]
        if u.path != "/guardar" or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}\.png", nombre):
            self.send_error(400, "ruta o nombre no validos")
            return
        largo = int(self.headers.get("Content-Length", 0))
        cuerpo = self.rfile.read(largo).decode("ascii")
        if not cuerpo.startswith("data:image/png;base64,"):
            self.send_error(400, "se espera un PNG en base64")
            return
        CAPTURAS.mkdir(parents=True, exist_ok=True)
        (CAPTURAS / nombre).write_bytes(base64.b64decode(cuerpo.split(",", 1)[1]))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def video(self, u):
        largo = int(self.headers.get("Content-Length", 0))
        cuerpo = self.rfile.read(largo) if largo else b""
        with Video.candado:
            if u.path == "/video/inicio":
                q = parse_qs(u.query)
                nombre = q.get("nombre", [""])[0]
                if Video.proc is not None or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}\.mp4", nombre):
                    return responder(self, 400, "video en curso o nombre no valido")
                Video.ruta = VIDEOS / nombre
                Video.esperados, Video.recibidos, Video.inicio = int(q.get("cuadros", ["0"])[0]), 0, time.time()
                Video.ruta.with_suffix(".json").unlink(missing_ok=True)
                registro = open(Video.ruta.with_suffix(".ffmpeg.log"), "w", encoding="utf-8")
                Video.proc = subprocess.Popen(
                    [str(FFMPEG), "-y", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "png", "-i", "-",
                     "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                     "-movflags", "+faststart", str(Video.ruta)],
                    stdin=subprocess.PIPE, stdout=registro, stderr=registro)
                print(f"video: inicio {Video.ruta.name} ({Video.esperados} cuadros)", flush=True)
                return responder(self, 200)
            if Video.proc is None:
                return responder(self, 409, "no hay video en curso")
            if u.path == "/video/cuadro":
                texto = cuerpo.decode("ascii")
                if not texto.startswith("data:image/png;base64,"):
                    return responder(self, 400, "se espera un PNG en base64")
                try:
                    Video.proc.stdin.write(base64.b64decode(texto.split(",", 1)[1]))
                except OSError as e:
                    return responder(self, 500, f"ffmpeg no acepta el cuadro: {e}")
                Video.recibidos += 1
                if Video.recibidos % 150 == 0:
                    print(f"video: {Video.recibidos}/{Video.esperados} cuadros", flush=True)
                return responder(self, 200)
            if u.path == "/video/fin":
                Video.proc.stdin.close()
                rc = Video.proc.wait()
                res = {"mp4": str(Video.ruta), "returncode": rc, "cuadros_recibidos": Video.recibidos,
                       "cuadros_esperados": Video.esperados, "segundos_de_render": round(time.time() - Video.inicio, 1)}
                Video.ruta.with_suffix(".json").write_text(json.dumps(res, indent=2), encoding="utf-8")
                print(f"video: fin {res}", flush=True)
                Video.proc = None
                return responder(self, 200 if rc == 0 else 500, json.dumps(res))
            return responder(self, 404, "ruta no valida")

    def log_message(self, fmt, *args):
        pass


def servir(puerto: int) -> int:
    if not (DESTINO / "index.html").exists():
        print("ERROR: primero 'preparar'")
        return 1
    servidor = ThreadingHTTPServer(("127.0.0.1", puerto), partial(Manejador, directory=str(DESTINO)))
    print(f"Sirviendo {DESTINO} en http://127.0.0.1:{puerto}/ (capturas en {CAPTURAS})", flush=True)
    servidor.serve_forever()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Escena Three.js de K002 (datos reales; solo 127.0.0.1).")
    sub = ap.add_subparsers(dest="orden", required=True)
    sub.add_parser("preparar")
    s = sub.add_parser("servir")
    s.add_argument("--puerto", type=int, default=8765)
    a = ap.parse_args()
    return preparar() if a.orden == "preparar" else servir(a.puerto)


if __name__ == "__main__":
    sys.exit(main())
