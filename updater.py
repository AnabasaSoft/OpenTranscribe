"""Comprobación de versiones nuevas en GitHub (mismo modelo que CloudMount Wizard)."""
import json
import subprocess
import urllib.request

import transcriber

# Última release publicada (GitHub ya excluye borradores y pre-releases)
LATEST_RELEASE_URL = "https://api.github.com/repos/AnabasaSoft/OpenTranscribe/releases/latest"

def check_latest(current_version):
    """Devuelve {"tag", "url"} de la última release si es más nueva que
    current_version, o None si no lo es. Lanza excepción si no se puede consultar."""
    req = urllib.request.Request(LATEST_RELEASE_URL, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"OpenTranscribe/{current_version}",  # GitHub exige User-Agent
    })
    with urllib.request.urlopen(req, context=transcriber.ssl_context(), timeout=15) as resp:
        data = json.load(resp)
    tag, url = data.get("tag_name", ""), data.get("html_url", "")
    if tag and url and is_newer(tag, current_version):
        return {"tag": tag, "url": url}
    return None

def is_newer(latest, current):
    """Indica si latest es mayor que current ("v1.2.3" o "1.2.3").
    Si alguna no se puede interpretar ("dev", "0.0.0+git…") devuelve False,
    para no avisar por error."""
    l, c = parse_version(latest), parse_version(current)
    if l is None or c is None:
        return False
    return l > c

def parse_version(v):
    """Convierte "v1.2.3" en (1, 2, 3); las partes que falten cuentan como 0.
    Se ignoran sufijos tipo "-beta". Devuelve None si no es una versión válida."""
    v = (v or "").strip().removeprefix("v").split("-", 1)[0]
    parts = v.split(".")
    if not v or len(parts) > 3 or not all(p.isdigit() for p in parts):
        return None
    nums = [int(p) for p in parts]
    return tuple(nums + [0] * (3 - len(nums)))

def open_url(url):
    """Abre una URL en el navegador o el cliente de correo del sistema.
    Desde el ejecutable de PyInstaller, webbrowser.open hereda LD_LIBRARY_PATH
    y el navegador puede no arrancar: se usa xdg-open con el entorno limpio."""
    try:
        subprocess.Popen(["xdg-open", url], env=transcriber.system_env(),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except OSError:
        import webbrowser
        webbrowser.open(url)
