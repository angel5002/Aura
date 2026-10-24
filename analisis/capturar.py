"""Captura cruda del puerto serie de la placa receptora.

Guarda TODAS las líneas que llegan (CSI y logs) en datos/crudos/<id_sesion>.csv
con dos columnas: t_pc_unix (segundos, reloj de la PC) y linea (texto crudo).
No interpreta los datos: eso lo hacen leer_csi.py y evaluar_deteccion.py.

Sirve para cualquier firmware que escriba líneas de texto por el puerto: csi_recv (líneas CSI_DATA)
o wifi_sensing (líneas HMS:{json}).

Con el USB nativo (USB Serial/JTAG) el puerto puede desaparecer un instante cuando la placa se
reinicia; el lector se reconecta solo y deja una línea "#AURA ..." en el archivo para marcarlo.

Ejemplo (PowerShell con el entorno activado):
    python C:\\aura\\analisis\\capturar.py --puerto COM5 --id-sesion S001 --duracion 180 --reiniciar
"""

import argparse
import csv
import sys
import time
from pathlib import Path

import serial

RAIZ = Path(__file__).resolve().parent.parent
DIR_CRUDOS = RAIZ / "datos" / "crudos"
MARCA_CSI = "CSI_DATA"
MARCA_HMS = "HMS:"  # mensajes de wifi_sensing_demo (web_serial_monitor.c)
MARCA_AURA = "#AURA "  # líneas escritas por estos scripts, no por la placa


def abrir_puerto(puerto: str, baudios: int) -> serial.Serial:
    # DTR/RTS en bajo antes de abrir: en placas ESP32 esas líneas controlan
    # EN/BOOT y dejarlas activas puede reiniciar o bloquear la placa.
    ser = serial.Serial()
    ser.port = puerto
    ser.baudrate = baudios
    ser.timeout = 1
    ser.dtr = False
    ser.rts = False
    ser.open()
    ser.reset_input_buffer()
    return ser


class LectorSerie:
    """Lee líneas del puerto y se reconecta si el puerto desaparece (reinicio de la placa, cable)."""

    def __init__(self, puerto: str, baudios: int):
        self.puerto, self.baudios = puerto, baudios
        self.ser = abrir_puerto(puerto, baudios)
        self.reconexiones = 0
        self.eventos = []  # (t, texto) para anotar en el archivo

    def _poner_rts(self, estado: bool):
        # Como esptool (reset.py, _setRTS): con el driver usbser.sys de Windows, el cambio de RTS no se envía
        # hasta que cambia DTR, así que se reescribe DTR con su mismo valor.
        self.ser.rts = estado
        self.ser.dtr = self.ser.dtr

    def reiniciar_placa(self):
        # Secuencia HardReset de esptool para USB Serial/JTAG: RTS=1 (EN en bajo), 0,2 s, RTS=0, 0,2 s.
        # DTR queda en 0: DTR=1 con RTS=0 entraría en modo de descarga.
        self.ser.dtr = False
        self._poner_rts(True)
        time.sleep(0.2)
        self._poner_rts(False)
        time.sleep(0.2)
        self.eventos.append((time.time(), "reinicio de la placa por RTS"))

    def reiniciar_por_consola(self):
        # Reinicio por software con el comando de consola de aura_nodo. Acordado el 23/10/2026 para todas las
        # pruebas en lugar de RTS (la secuencia RTS precedio a un bloqueo de la placa). Solo con aura_nodo.
        ok = self.escribir(b"AURA REBOOT\n")
        self.eventos.append((time.time(), "reinicio de la placa por consola (AURA REBOOT)" if ok
                             else "no se pudo enviar AURA REBOOT"))

    def leer_linea(self):
        """Devuelve bytes, o None si no llegó nada (timeout) o el puerto está reconectándose."""
        if self.ser is None:
            try:
                self.ser = abrir_puerto(self.puerto, self.baudios)
                self.reconexiones += 1
                self.eventos.append((time.time(), "puerto reconectado"))
            except serial.SerialException:
                time.sleep(0.5)
                return None
        try:
            return self.ser.readline() or None
        except serial.SerialException as e:
            self.eventos.append((time.time(), f"puerto perdido: {e}"))
            try:
                self.ser.close()
            except serial.SerialException:
                pass
            self.ser = None
            return None

    def escribir(self, datos: bytes) -> bool:
        if self.ser is None:
            return False
        try:
            self.ser.write(datos)
            return True
        except serial.SerialException:
            return False

    def cerrar(self):
        if self.ser is not None:
            self.ser.close()


def nuevo_destino(id_sesion: str) -> Path:
    DIR_CRUDOS.mkdir(parents=True, exist_ok=True)
    destino = DIR_CRUDOS / f"{id_sesion}.csv"
    if destino.exists():
        raise FileExistsError(f"{destino} ya existe. Usa otro --id-sesion (no se sobrescriben datos).")
    return destino


def main() -> int:
    ap = argparse.ArgumentParser(description="Captura cruda del puerto serie.")
    ap.add_argument("--puerto", required=True, help="Puerto COM de la placa receptora, p. ej. COM5")
    ap.add_argument("--baudios", type=int, default=921600,
                    help="Baudios. Con el USB nativo (USB Serial/JTAG) de la FireBeetle no limitan la velocidad; "
                         "solo importan con un puente USB-UART")
    ap.add_argument("--id-sesion", required=True, help="Identificador de la sesión, p. ej. S001")
    ap.add_argument("--duracion", type=float, required=True, help="Duración de la captura en segundos")
    ap.add_argument("--reiniciar", action="store_true",
                    help="Reinicia la placa al empezar con 'AURA REBOOT' (aura_nodo), para capturar el arranque")
    ap.add_argument("--reiniciar-rts", action="store_true",
                    help="Reinicio por RTS (solo para firmware sin consola AURA; evitar con aura_nodo)")
    ap.add_argument("--teclas", action="store_true",
                    help="Marcar con el teclado en esta ventana: E = entra a la zona, S = sale, M = marca libre "
                         "(se guardan en <id>_marcas.csv y como lineas #AURA en la captura)")
    args = ap.parse_args()
    teclado = None
    if args.teclas:
        try:
            import msvcrt as teclado     # Windows: lectura de teclas sin esperar Enter
        except ImportError:
            print("ERROR: --teclas solo funciona en Windows.")
            return 1
    marcas = DIR_CRUDOS / f"{args.id_sesion}_marcas.csv"
    significado = {"E": "entra a la zona", "S": "sale de la zona", "M": "marca libre"}

    try:
        destino = nuevo_destino(args.id_sesion)
        lector = LectorSerie(args.puerto, args.baudios)
    except FileExistsError as e:
        print(f"ERROR: {e}")
        return 1
    except serial.SerialException as e:
        print(f"ERROR al abrir {args.puerto}: {e}")
        print("¿Está cerrado idf.py monitor / el Monitor Serie de Arduino? ¿Es el COM correcto?")
        return 1

    n_lineas = n_datos = n_errores_decod = 0
    t_inicio = time.time()
    t_fin = t_inicio + args.duracion
    t_aviso = t_inicio + 5
    print(f"Capturando {args.duracion:.0f} s de {args.puerto} -> {destino}")
    print("Ctrl+C para detener antes de tiempo.")
    if teclado:
        print("Teclas (con ESTA ventana activa): E = entra a la zona, S = sale, M = marca libre")

    try:
        with open(destino, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["t_pc_unix", "linea"])
            if args.reiniciar:
                lector.reiniciar_por_consola()
            elif args.reiniciar_rts:
                lector.reiniciar_placa()
            while time.time() < t_fin:
                while teclado and teclado.kbhit():
                    tecla = teclado.getwch().upper()
                    if tecla in significado:
                        t_m = time.time()
                        nuevo = not marcas.exists()
                        with open(marcas, "a", newline="", encoding="utf-8") as fm:
                            wm = csv.writer(fm)
                            if nuevo:
                                wm.writerow(["t_pc_unix", "tecla", "significado"])
                            wm.writerow([f"{t_m:.6f}", tecla, significado[tecla]])
                        w.writerow([f"{t_m:.6f}", MARCA_AURA + f"marca {tecla} ({significado[tecla]})"])
                        print(f"  [{t_m - t_inicio:6.1f} s] MARCA {tecla}: {significado[tecla]}", flush=True)
                bruto = lector.leer_linea()
                for t_ev, texto in lector.eventos:
                    w.writerow([f"{t_ev:.6f}", MARCA_AURA + texto])
                    print(f"  [{t_ev - t_inicio:6.1f} s] {texto}")
                lector.eventos.clear()
                if bruto is None:
                    continue
                t = time.time()
                linea = bruto.decode("utf-8", errors="replace").rstrip("\r\n")
                if "\ufffd" in linea:
                    n_errores_decod += 1
                w.writerow([f"{t:.6f}", linea])
                n_lineas += 1
                if MARCA_CSI in linea or linea.startswith(MARCA_HMS):
                    n_datos += 1
                if t >= t_aviso:
                    print(f"  {t - t_inicio:6.1f} s | líneas {n_lineas} | datos {n_datos} "
                          f"| {n_datos / (t - t_inicio):.1f} /s")
                    t_aviso += 5
    except KeyboardInterrupt:
        print("\nDetenido por el usuario.")
    finally:
        lector.cerrar()

    dur = time.time() - t_inicio
    print("\n--- Resumen ---")
    print(f"Archivo:            {destino}")
    print(f"Duración real:      {dur:.1f} s")
    print(f"Líneas guardadas:   {n_lineas}")
    print(f"Líneas de datos:    {n_datos} (CSI_DATA o HMS:)")
    print(f"Tasa promedio:      {n_datos / dur:.1f} líneas de datos/s" if dur > 0 else "")
    print(f"Reconexiones:       {lector.reconexiones}")
    if n_errores_decod:
        print(f"Aviso: {n_errores_decod} líneas con bytes no decodificables (¿baudios incorrectos?).")
    if n_datos == 0:
        print("Aviso: no llegó ninguna línea CSI_DATA ni HMS:. Revisa que el puerto sea el de la placa B, "
              "que el transmisor (placa A o el router) esté encendido y que la consola esté en USB Serial/JTAG.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
