"""Preferencias de la aplicación en ~/.OpenTranscribe/config.json."""
import json
import os

from transcriber import APP_DIR

CONFIG_PATH = os.path.join(APP_DIR, "config.json")

DEFAULTS = {
    "comprobar_actualizaciones": True,  # Buscar versiones nuevas al arrancar
    "version_omitida": "",              # Versión de la que el usuario pidió no volver a avisar
}

def _load():
    """Lee el fichero; si falta o está dañado se usan los valores por defecto
    (la app tiene que arrancar igual)."""
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}

def get(key):
    return _load().get(key, DEFAULTS.get(key))

def set(key, value):
    data = _load()
    data[key] = value
    # Escritura atómica: si la app se cierra a mitad, no queda un JSON a medias
    tmp = CONFIG_PATH + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, CONFIG_PATH)
    except OSError as e:
        print(f"No se pudo guardar la configuración: {e}")
