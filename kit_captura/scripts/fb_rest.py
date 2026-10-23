"""Cliente REST minimo de Firebase para la PC (cuenta de USUARIO, nunca la clave de servicio).

Configuracion no secreta en C:\\aura\\secretos\\firebase_web.json: el objeto de configuracion web tal como
lo da la consola de Firebase (Configuracion del proyecto > Tus apps > app web), con los nombres
"apiKey" y "databaseURL" (tambien se aceptan "api_key" y "db_url"):
    {"apiKey": "AIza...", "databaseURL": "https://aura-csi-default-rtdb.firebaseio.com", "projectId": ...}
El correo y la contrasena se piden sin eco (getpass) y no se guardan en disco.
"""

import getpass
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CONFIG_WEB = RAIZ / "secretos" / "firebase_web.json"


def cargar_config() -> dict:
    """Devuelve {"api_key", "db_url", "project_id"} a partir de firebase_web.json (nombres de la consola)."""
    if not CONFIG_WEB.exists():
        raise FileNotFoundError(f"Falta {CONFIG_WEB} con apiKey y databaseURL (ver docs/guia_firebase.md).")
    crudo = json.loads(CONFIG_WEB.read_text(encoding="utf-8-sig"))
    api_key = crudo.get("apiKey") or crudo.get("api_key")
    db_url = crudo.get("databaseURL") or crudo.get("db_url")
    if not api_key or not db_url:
        raise ValueError(f"{CONFIG_WEB} debe tener 'apiKey' y 'databaseURL' (nombres de la consola de Firebase).")
    if not api_key.startswith("AIza") or len(api_key) != 39:
        raise ValueError("apiKey con formato inesperado (debe empezar con 'AIza' y tener 39 caracteres).")
    if not db_url.startswith("https://") or not (".firebaseio.com" in db_url or ".firebasedatabase.app" in db_url):
        raise ValueError("databaseURL con formato inesperado (https://<proyecto>-default-rtdb.firebaseio.com).")
    return {"api_key": api_key, "db_url": db_url.rstrip("/"), "project_id": crudo.get("projectId", "")}


def _post_json(url: str, cuerpo: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(cuerpo).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def probar_inicio_sesion(cfg: dict, email: str, password: str) -> tuple[str, str | None]:
    """Prueba correo/contrasena contra Firebase Auth (HTTPS con verificacion de certificados).

    Devuelve ("correcto", uid), ("incorrecto", None) o ("sin_conexion", None). No guarda ni devuelve el
    token, y no imprime nada.
    """
    try:
        r = _post_json("https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key="
                       + cfg["api_key"], {"email": email, "password": password, "returnSecureToken": False})
    except urllib.error.HTTPError:
        return "incorrecto", None       # 400: credenciales invalidas, cuenta inhabilitada o bloqueada
    except (urllib.error.URLError, TimeoutError, OSError):
        return "sin_conexion", None
    return ("correcto", r.get("localId")) if r.get("localId") else ("incorrecto", None)


class Sesion:
    """Sesion de Firebase Auth (correo/contrasena) con renovacion automatica del idToken."""

    def __init__(self, cfg: dict, email: str | None = None, password: str | None = None, etiqueta: str = "usuario"):
        self.cfg = cfg
        email = email or input(f"Correo de la cuenta de {etiqueta}: ").strip()
        password = password or getpass.getpass(f"Contrasena de la cuenta de {etiqueta} (no se muestra): ")
        r = _post_json("https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key="
                       + cfg["api_key"], {"email": email, "password": password, "returnSecureToken": True})
        del password
        self.uid = r["localId"]
        self._token = r["idToken"]
        self._refresh = r["refreshToken"]
        self._vence = time.time() + int(r.get("expiresIn", 3600))

    def token(self) -> str:
        if time.time() > self._vence - 300:
            datos = urllib.parse.urlencode({"grant_type": "refresh_token", "refresh_token": self._refresh}).encode()
            req = urllib.request.Request("https://securetoken.googleapis.com/v1/token?key=" + self.cfg["api_key"],
                                         data=datos, method="POST",
                                         headers={"Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(req, timeout=20) as r:
                j = json.loads(r.read())
            self._token, self._refresh = j["id_token"], j["refresh_token"]
            self._vence = time.time() + int(j.get("expires_in", 3600))
        return self._token


def peticion(cfg: dict, metodo: str, ruta: str, sesion: Sesion | None = None, cuerpo=None,
             consulta: dict | None = None) -> tuple[int, object]:
    """Devuelve (codigo_http, json_o_texto). sesion=None -> peticion SIN autenticar (para probar reglas)."""
    params = dict(consulta or {})
    if sesion is not None:
        params["auth"] = sesion.token()
    url = f"{cfg['db_url']}{ruta}.json"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(url, data=datos, method=metodo, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            txt = r.read().decode()
            codigo = r.status
    except urllib.error.HTTPError as e:
        txt = e.read().decode(errors="replace")
        codigo = e.code
    try:
        return codigo, json.loads(txt) if txt else None
    except json.JSONDecodeError:
        return codigo, txt
