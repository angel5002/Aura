"""Visor de AURA: panel en vivo y reproduccion sincronizada para montar el video.

Panel: mapa de calor de la amplitud por subportadora (CSI), señal suavizada del detector con sus
umbrales de entrada/salida (smooth_scaled, enter_level_scaled, exit_level_scaled de los mensajes
"sample") y el estado (MOVIMIENTO / PRESENCIA_QUIETA / VACIA / CALIBRANDO), con la fuente de datos.

Modos:
  En vivo:      python visor.py --vivo [--ip IP] [--id-sesion V001] [--nube]
                Usa la via local; si no llegan datos en 10 s y se dio --nube, consulta Firebase con TU
                cuenta de usuario (nunca la clave de servicio) cada 5 s.
  Reproduccion: python visor.py --reproducir C:\\aura\\datos\\crudos\\L001_local.csv [--exportar DIR --fps 10]
                Reconstruye el panel desde el archivo; con --exportar escribe un PNG por cuadro, con la
                hora UNIX (ms, SNTP de la placa) en el nombre y en la imagen, para alinearlo con el video.
                Tambien acepta una captura USB de capturar.py (lineas "HMS:"): usa la hora de la PC que
                capturo y muestra la señal del detector y el estado (por USB no llega el CSI crudo).
"""

import argparse
import csv
import json
import sys
import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import matplotlib
import numpy as np

from aura_proto import decodificar_csi, parsear_datagrama

RAIZ = Path(__file__).resolve().parent.parent
VENTANA_S = 20.0
COLORES = {"MOVIMIENTO": "#d62728", "PRESENCIA_QUIETA": "#ff7f0e", "VACIA": "#2ca02c",
           "CALIBRANDO": "#7f7f7f", "SIN_MOVIMIENTO": "#1f77b4", "SIN DATOS": "#000000"}


class Estado:
    """Acumula lo necesario para dibujar el panel (ultimos VENTANA_S segundos).

    Por defecto la PRESENCIA se muestra como "no disponible" y el estado solo distingue CALIBRANDO / MOVIMIENTO /
    SIN_MOVIMIENTO: sin entrenamiento valido (salon nunca vacio) o con el umbral entrenado inutil (S002, 24/10/2026)
    la presencia no es fiable. --con-presencia vuelve a mostrar PRESENCIA_QUIETA / VACIA si hay entrenamiento."""

    con_presencia = False

    def __init__(self):
        self.amp = deque()          # (t, vector amplitud)
        self.senal = deque()        # (t, smooth, enter, exit)
        self.estado = "SIN DATOS"
        self.fuente = "-"
        self.t_ultimo = None
        self.mov = False
        self.pres = False
        self.pres_valida = False
        self.lock = threading.Lock()

    def agregar_datagrama(self, t_pc: float, d):
        t = d.t_us / 1e6 if d.t_us else t_pc
        try:
            cuerpo = json.loads(d.cuerpo)
        except json.JSONDecodeError:
            return
        with self.lock:
            self.fuente = getattr(d, "fuente", "local")
            self.t_ultimo = t
            if d.tipo == "csi":
                c = decodificar_csi(cuerpo)
                if len(c["amplitud"]):
                    self.amp.append((t, c["amplitud"]))
            elif cuerpo.get("type") == "sample":
                self.senal.append((t, cuerpo.get("smooth_scaled", 0), cuerpo.get("enter_level_scaled", 0),
                                   cuerpo.get("exit_level_scaled", 0)))
                self.mov = bool(cuerpo.get("motion_status"))
                self.pres = bool(cuerpo.get("presence_someone_status"))
                self.pres_valida = self.con_presencia and bool(cuerpo.get("train_thresholds_valid"))
                if cuerpo.get("init_stage_name") != "STABLE":
                    self.estado = "CALIBRANDO"
                elif self.mov:
                    self.estado = "MOVIMIENTO"
                elif not self.pres_valida:
                    self.estado = "SIN_MOVIMIENTO"
                else:
                    self.estado = "PRESENCIA_QUIETA" if self.pres else "VACIA"
            elif cuerpo.get("type") == "telemetria" and cuerpo.get("estado"):
                pass  # el estado de la placa (con retencion) llega cada 10 s; el panel usa las muestras
            self._recortar(t)

    def agregar_nube(self, estado: dict, bloque: dict | None):
        with self.lock:
            self.fuente = "nube"
            self.estado = estado.get("estado", "SIN DATOS")
            if not self.con_presencia and self.estado in ("PRESENCIA_QUIETA", "VACIA"):
                self.estado = "SIN_MOVIMIENTO"
            self.mov = bool(estado.get("mov"))
            self.pres = estado.get("presencia") == "presente"     # "no_disponible" nunca cuenta como vacia
            self.pres_valida = self.con_presencia and estado.get("presencia") in ("presente", "vacia")
            self.t_ultimo = time.time()
            if bloque and bloque.get("jit"):
                jit = [int(x) / 1e4 for x in bloque["jit"].split(",") if x]
                t0, t1 = bloque["t0"] / 1000, bloque["t1"] / 1000
                for i, j in enumerate(jit):
                    self.senal.append((t0 + (t1 - t0) * i / max(len(jit), 1), j, np.nan, np.nan))
            self._recortar(self.t_ultimo)

    def _recortar(self, t):
        while self.amp and self.amp[0][0] < t - VENTANA_S:
            self.amp.popleft()
        while self.senal and self.senal[0][0] < t - VENTANA_S:
            self.senal.popleft()


class Panel:
    def __init__(self, interactivo: bool, rotulo: str | None = None):
        if not interactivo:
            matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        self.plt = plt
        self.fig, (self.ax_calor, self.ax_senal) = plt.subplots(2, 1, figsize=(11, 7), height_ratios=[1.3, 1])
        self.titulo = self.fig.suptitle("AURA", fontsize=13, x=0.40)
        if rotulo:
            self.fig.text(0.5, 0.005, rotulo, ha="center", va="bottom", fontsize=10, style="italic", color="#444444")
        # Indicador grande (para proyectar): estado y movimiento; y la ultima marca de teclado (E/S/M)
        self.indicador = self.fig.text(0.99, 0.985, "", ha="right", va="top", fontsize=15, weight="bold",
                                       color="white", bbox=dict(boxstyle="round", facecolor="#7f7f7f"))
        self.txt_marca = self.fig.text(0.01, 0.985, "", ha="left", va="top", fontsize=10, color="#333333")

    def dibujar(self, e: Estado, t_ref: float | None = None):
        with e.lock:
            amp = list(e.amp)
            senal = list(e.senal)
            estado, fuente, t_ult, mov = e.estado, e.fuente, e.t_ultimo, e.mov
            pres = ("SÍ" if e.pres else "no") if e.pres_valida else "no disponible"
        self.indicador.set_text(f"{estado}\nmovimiento: {'SÍ' if mov else 'no'}\npresencia: {pres}")
        self.indicador.get_bbox_patch().set_facecolor(COLORES.get(estado, "#7f7f7f"))
        t_ref = t_ref or t_ult or time.time()
        self.ax_calor.clear()
        self.ax_senal.clear()
        if amp:
            n = max(len(a) for _, a in amp)
            m = np.full((n, len(amp)), np.nan)
            for j, (_, a) in enumerate(amp):
                m[: len(a), j] = a
            ts = [t - t_ref for t, _ in amp]
            self.ax_calor.imshow(m, aspect="auto", origin="lower", cmap="viridis",
                                 extent=[ts[0], ts[-1] if ts[-1] > ts[0] else ts[0] + 1e-3, 0, n])
        self.ax_calor.set_ylabel("Subportadora")
        self.ax_calor.set_title("Amplitud CSI (subportadoras validas)" if fuente != "USB"
                                else "Amplitud CSI: no disponible en captura USB (solo por la via local)")
        if senal:
            s = np.array(senal, dtype=float)
            t = s[:, 0] - t_ref
            self.ax_senal.plot(t, s[:, 1], color="k", lw=1, label="señal suavizada")
            if np.isfinite(s[:, 2]).any():
                self.ax_senal.plot(t, s[:, 2], "--", color="#d62728", lw=1, label="umbral de entrada")
                self.ax_senal.plot(t, s[:, 3], ":", color="#2ca02c", lw=1, label="umbral de salida")
            self.ax_senal.legend(loc="upper left", fontsize=8)
        self.ax_senal.set_xlim(-VENTANA_S, 0)
        self.ax_calor.set_xlim(-VENTANA_S, 0)
        self.ax_senal.set_xlabel("Segundos (0 = ahora)")
        hora = datetime.fromtimestamp(t_ref).strftime("%H:%M:%S.%f")[:-3] if t_ref else "-"
        self.titulo.set_text(f"AURA  |  {estado}  |  fuente: {fuente}  |  {hora}")
        self.titulo.set_color(COLORES.get(estado, "#000000"))

    def guardar(self, ruta: Path):
        self.fig.savefig(ruta, dpi=90)


class LineaUSB:
    """Una linea "HMS:{...}" de una captura USB (capturar.py) con la misma forma que un datagrama A1.
    Por USB no llega el CSI crudo: el panel muestra la señal del detector y el estado, sin mapa de calor."""

    def __init__(self, cuerpo: str):
        self.tipo, self.cuerpo, self.t_us, self.seq, self.fuente = "hms", cuerpo, 0, 0, "USB"


ROTULO_REPRODUCCION = "Reproducción de datos registrados durante la grabación"


def reproducir(archivo: Path, exportar: Path | None, fps: float, desde: float | None, hasta: float | None,
               rotulo: str | None = ROTULO_REPRODUCCION) -> int:
    filas = []
    with open(archivo, newline="", encoding="utf-8") as f:
        r = csv.reader(f)
        next(r)
        for fila in r:
            if len(fila) < 2:
                continue
            t_pc, linea = fila[0], fila[1]
            if linea.startswith("HMS:"):            # captura USB: la hora es la de la PC que capturo
                d = LineaUSB(linea[4:])
            else:
                d = parsear_datagrama(linea)
            if d:
                filas.append((d.t_us / 1e6 if d.t_us else float(t_pc), float(t_pc), d))
    if not filas:
        print("ERROR: el archivo no tiene datagramas A1 ni lineas HMS de una captura USB.")
        return 1
    filas.sort(key=lambda x: (x[0], x[2].seq))      # orden por hora de la placa y luego por secuencia
    t0 = max(filas[0][0], desde or filas[0][0])
    t1 = min(filas[-1][0], hasta or filas[-1][0])
    e = Estado()
    panel = Panel(interactivo=exportar is None, rotulo=rotulo)
    if exportar:
        exportar.mkdir(parents=True, exist_ok=True)
    i = 0
    n_cuadros = 0
    t = t0
    while t <= t1:
        while i < len(filas) and filas[i][0] <= t:
            e.agregar_datagrama(filas[i][1], filas[i][2])
            i += 1
        panel.dibujar(e, t_ref=t)
        if exportar:
            panel.guardar(exportar / f"cuadro_{int(t * 1000)}.png")
        else:
            panel.plt.pause(1 / fps)
        n_cuadros += 1
        t += 1 / fps
    print(f"Reproduccion: {len(filas)} datagramas, {n_cuadros} cuadros"
          + (f" en {exportar}" if exportar else ""))
    return 0


def vivo(ip: str | None, id_sesion: str, usar_nube: bool, puerto: str | None = None,
         segundos: float | None = None, png: Path | None = None) -> int:
    import receptor_local as rl
    e = Estado()
    sin_ventana = png is not None
    if not sin_ventana:
        # Las teclas de marca no deben disparar atajos de matplotlib ('s' = guardar, 'q' = cerrar)
        for k, v in (("keymap.save", ["ctrl+s"]), ("keymap.quit", ["ctrl+w"]), ("keymap.quit_all", [])):
            matplotlib.rcParams[k] = v
    panel = Panel(interactivo=not sin_ventana)
    rl.DIR_CRUDOS.mkdir(parents=True, exist_ok=True)
    ultimo_local = [0.0]

    def al_local(t, d):
        ultimo_local[0] = t
        e.agregar_datagrama(t, d)

    ip_directa = ip is not None
    if not ip and not puerto:
        ip = (rl.descubrir(15) or {}).get("ip")
    if ip:
        destino = rl.DIR_CRUDOS / f"{id_sesion}_local.csv"
        # Con --ip: sin descubrimiento y sin bind() (no hace falta regla de firewall ni administrador)
        hilo = threading.Thread(target=rl.recibir, args=(ip, rl.PUERTO_DATOS, destino, 10 ** 9),
                                kwargs={"al_recibir": al_local, "silencioso": True, "nombre": id_sesion,
                                        "bind_explicito": not ip_directa}, daemon=True)
        hilo.start()
        print(f"Via local: {ip} (grabando en {destino})")
    parar = threading.Event()
    if puerto:
        threading.Thread(target=leer_usb_en_vivo, args=(puerto, id_sesion, e, ultimo_local, parar),
                         daemon=True).start()
        print(f"USB: {puerto} (grabando en {rl.DIR_CRUDOS / (id_sesion + '.csv')})")
    marcas = rl.DIR_CRUDOS / f"{id_sesion}_marcas.csv"

    def al_tecla(ev):
        tecla = (ev.key or "").upper()
        if tecla not in SIGNIFICADO_TECLA:
            return
        t = time.time()
        nuevo = not marcas.exists()
        with open(marcas, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if nuevo:
                w.writerow(["t_pc_unix", "tecla", "significado"])
            w.writerow([f"{t:.6f}", tecla, SIGNIFICADO_TECLA[tecla]])
        panel.txt_marca.set_text(f"Marca {tecla} ({SIGNIFICADO_TECLA[tecla]}) a las {datetime.fromtimestamp(t):%H:%M:%S}")
        print(f"{datetime.fromtimestamp(t):%H:%M:%S} marca {tecla}: {SIGNIFICADO_TECLA[tecla]}", flush=True)

    if not sin_ventana:
        panel.fig.canvas.mpl_connect("key_press_event", al_tecla)
        panel.txt_marca.set_text("Teclas: E = entra a la zona, S = sale, M = marca libre")
    fin = time.time() + segundos if segundos else None
    sesion = cfg = None
    prox_nube = 0
    while (sin_ventana or panel.plt.fignum_exists(panel.fig.number)) and (fin is None or time.time() < fin):
        sin_local = e.fuente != "local" or (e.t_ultimo and time.time() - e.t_ultimo > 10)
        if usar_nube and sin_local and time.time() >= prox_nube:
            from fb_rest import Sesion, cargar_config, peticion
            if sesion is None:
                cfg = cargar_config()
                sesion = Sesion(cfg, etiqueta="usuario (visor)")
            _, est = peticion(cfg, "GET", "/sensores/hab1/estado", sesion)
            _, bl = peticion(cfg, "GET", "/crudo/hab1", sesion, consulta={"orderBy": '"$key"', "limitToLast": 1})
            bloque = next(iter(bl.values())) if isinstance(bl, dict) and bl else None
            e.agregar_nube(est or {}, bloque)
            prox_nube = time.time() + 5
        panel.dibujar(e)
        if sin_ventana:
            time.sleep(0.2)
        else:
            panel.plt.pause(0.2)
    parar.set()
    if png:
        panel.guardar(png)
        print(f"Cuadro guardado en {png}")
    return 0


SIGNIFICADO_TECLA = {"E": "entra a la zona", "S": "sale de la zona", "M": "marca libre"}


def leer_usb_en_vivo(puerto: str, id_sesion: str, e: Estado, ultimo_local: list, parar: threading.Event):
    """Guarda el USB en <id>.csv (formato de capturar.py) y alimenta el panel con las lineas HMS cuando la via
    local no esta llegando (plan B sin red: señal del detector y estado, sin mapa de calor)."""
    from capturar import LectorSerie, nuevo_destino
    destino = nuevo_destino(id_sesion)
    lector = LectorSerie(puerto, 115200)
    with open(destino, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t_pc_unix", "linea"])
        while not parar.is_set():
            for t_ev, txt in lector.eventos:
                w.writerow([f"{t_ev:.6f}", "#AURA " + txt])
            lector.eventos.clear()
            b = lector.leer_linea()
            if b is None:
                continue
            t = time.time()
            linea = b.decode("utf-8", errors="replace").rstrip("\r\n")
            w.writerow([f"{t:.6f}", linea])
            if linea.startswith("HMS:") and t - ultimo_local[0] > 5:
                e.agregar_datagrama(t, LineaUSB(linea[4:]))
    lector.cerrar()


def main() -> int:
    ap = argparse.ArgumentParser(description="Visor de AURA (en vivo y reproduccion).")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--vivo", action="store_true")
    g.add_argument("--reproducir", type=Path)
    ap.add_argument("--ip")
    ap.add_argument("--id-sesion", default=time.strftime("V%Y%m%d_%H%M%S"))
    ap.add_argument("--nube", action="store_true", help="usar Firebase si la via local no responde")
    ap.add_argument("--exportar", type=Path, help="carpeta para los PNG de la reproduccion")
    ap.add_argument("--fps", type=float, default=10)
    ap.add_argument("--desde", type=float, help="hora UNIX (s) de inicio de la reproduccion")
    ap.add_argument("--hasta", type=float, help="hora UNIX (s) de fin de la reproduccion")
    ap.add_argument("--rotulo", default=ROTULO_REPRODUCCION, help="texto al pie de cada cuadro ('' = sin rotulo)")
    ap.add_argument("--puerto", help="en vivo: leer y guardar tambien el USB (plan B sin red)")
    ap.add_argument("--segundos", type=float, help="en vivo: cerrar solo tras N segundos (prueba)")
    ap.add_argument("--png", type=Path, help="en vivo: sin ventana; guarda el ultimo cuadro (prueba)")
    ap.add_argument("--con-presencia", action="store_true",
                    help="mostrar la presencia (PRESENCIA_QUIETA/VACIA) si la placa tiene entrenamiento valido; "
                         "por defecto se muestra 'no disponible'")
    args = ap.parse_args()
    Estado.con_presencia = args.con_presencia
    if args.reproducir:
        return reproducir(args.reproducir, args.exportar, args.fps, args.desde, args.hasta, args.rotulo or None)
    return vivo(args.ip, args.id_sesion, args.nube, args.puerto, args.segundos, args.png)


if __name__ == "__main__":
    sys.exit(main())
