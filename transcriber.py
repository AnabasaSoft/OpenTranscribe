import os
import collections
import threading
import subprocess
import re
import sys
import shutil
import urllib.request
import ssl

# ==========================================
# CONFIGURACIÓN DE RUTAS
# ==========================================
USER_HOME = os.path.expanduser("~")
APP_DIR = os.path.join(USER_HOME, ".OpenTranscribe")
MODELS_DIR = os.path.join(APP_DIR, "models")
TEMP_WAV = os.path.join(APP_DIR, "temp_audio.wav")

# Solo aseguramos la carpeta de modelos
os.makedirs(MODELS_DIR, exist_ok=True)

MODEL_URLS = {
    "ggml-tiny.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin",
    "ggml-base.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin",
    "ggml-small.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin",
    "ggml-medium.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin",
    "ggml-large-v3.bin": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin"
}

current_process = None
is_cancelled = False

class Cancelled(Exception):
    """El usuario ha cancelado el trabajo en curso."""

def reset_cancellation():
    """Se llama al empezar un trabajo nuevo (no en cada archivo de una cola,
    o se perdería una cancelación pedida entre dos archivos)."""
    global is_cancelled
    is_cancelled = False

def get_whisper_executable():
    """
    Busca el binario 'whisper-cli' incluido en la aplicación.
    """
    binary_name = "whisper-cli"

    # 1. Modo PyInstaller (Cuando el usuario final ejecute la app)
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        # Busca en la carpeta temporal donde se descomprime el exe
        path = os.path.join(base_path, "binaries_linux", binary_name)
        if os.path.exists(path): return path

    # 2. Modo Desarrollo (Cuando tú lo ejecutas ahora)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dev_path = os.path.join(base_dir, "binaries_linux", binary_name)
    if os.path.exists(dev_path): return dev_path

    return None

def get_ffmpeg_executable():
    return shutil.which("ffmpeg")

def get_model_filename(model_name_ui):
    mapa_modelos = {
        "Tiny (Muy rápido)": "ggml-tiny.bin",
        "Base (Equilibrado)": "ggml-base.bin",
        "Small (Preciso)": "ggml-small.bin",
        "Medium (Muy preciso)": "ggml-medium.bin",
        "Large (Lento/Pro)": "ggml-large-v3.bin"
    }
    return mapa_modelos.get(model_name_ui, "ggml-base.bin")

def get_model_path(model_filename):
    return os.path.join(MODELS_DIR, model_filename)

def check_model_exists(model_name_ui):
    filename = get_model_filename(model_name_ui)
    path = get_model_path(filename)
    return os.path.exists(path), filename

def download_model(filename, progress_callback):
    url = MODEL_URLS.get(filename)
    dest_path = get_model_path(filename)
    if not url: raise Exception("URL de modelo no encontrada")

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    # Se descarga a un .part y solo se renombra al terminar: si se cancela o se
    # corta, no queda en MODELS_DIR un modelo a medias que parezca válido
    part_path = dest_path + ".part"
    try:
        with urllib.request.urlopen(url, context=ctx) as response, open(part_path, 'wb') as out_file:
            total_size = int(response.info().get('Content-Length', -1))
            downloaded = 0
            block_size = 8192
            while True:
                if is_cancelled: raise Cancelled()
                buffer = response.read(block_size)
                if not buffer: break
                downloaded += len(buffer)
                out_file.write(buffer)
                if total_size > 0: progress_callback(downloaded / total_size)
        if total_size > 0 and downloaded != total_size:
            raise Exception(f"Descarga incompleta ({downloaded} de {total_size} bytes)")
        os.replace(part_path, dest_path)
    finally:
        if os.path.exists(part_path): os.remove(part_path)

def stop_transcription():
    """Pide la cancelación y mata el proceso externo en curso (ffmpeg o whisper).
    current_process lo pone a None el hilo de trabajo, no esta función, para no
    dejarlo sin referencia mientras aún lo está leyendo."""
    global is_cancelled
    is_cancelled = True
    proc = current_process
    if proc:
        try: proc.kill()
        except: pass

def get_audio_duration(file_path):
    ffmpeg = get_ffmpeg_executable()
    if not ffmpeg: return 0
    try:
        cmd = [ffmpeg, "-i", file_path]
        result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
        match = re.search(r"Duration: (\d{2}):(\d{2}):(\d{2}\.\d{2})", result.stderr)
        if match:
            h, m, s = map(float, match.groups())
            return h * 3600 + m * 60 + s
    except: pass
    return 0

def convert_to_wav(input_path):
    ffmpeg = get_ffmpeg_executable()
    if not ffmpeg: raise Exception("No se encontró FFMPEG instalado en el sistema.")

    if os.path.exists(TEMP_WAV): os.remove(TEMP_WAV)
    cmd = [ffmpeg, "-i", input_path, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", "-y", TEMP_WAV]

    # --- INICIO DEL FIX ---
    # Creamos una copia del entorno actual
    env = os.environ.copy()

    # Si estamos en un binario de PyInstaller, LD_LIBRARY_PATH apunta a la carpeta temporal.
    # FFmpeg del sistema odia esto. Lo borramos SOLO para esta llamada.
    if "LD_LIBRARY_PATH" in env:
        del env["LD_LIBRARY_PATH"]

    # Popen (no run) y registrado en current_process para que Cancelar pueda matarlo
    global current_process
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    current_process = proc
    try:
        if is_cancelled: proc.kill()  # cancelado justo antes de registrarlo
        proc.wait()
    finally:
        current_process = None
    # --- FIN DEL FIX ---
    if is_cancelled: raise Cancelled()
    if os.path.exists(TEMP_WAV): return TEMP_WAV
    raise Exception("Error al convertir audio.")

def run_transcription(input_file, model_selection, callback_text, callback_progress, with_timestamps=False, diarize=False):
    """Devuelve None si todo va bien (o se cancela) y el mensaje de error si falla."""
    global current_process, is_cancelled

    def fail(msg):
        callback_text(msg)
        return msg.strip()

    whisper_bin = get_whisper_executable()

    # Verificación estricta: Si no está el binario, es error crítico
    if not whisper_bin:
        return fail("[ERROR CRÍTICO] No se encontró el archivo 'whisper-cli' interno.\nReinstala la aplicación.")

    filename = get_model_filename(model_selection)
    model_path = get_model_path(filename)
    if not os.path.exists(model_path):
        return fail(f"[ERROR] Modelo no encontrado: {model_path}")

    # is_cancelled NO se reinicia aquí: lo hace reset_cancellation() al empezar el
    # trabajo, para que una cancelación durante la descarga o entre archivos se respete
    proc = None
    try:
        if is_cancelled: raise Cancelled()
        total_duration = get_audio_duration(input_file)
        wav_path = convert_to_wav(input_file)

        cmd = [whisper_bin, "-m", model_path, "-f", wav_path, "--language", "auto"]
        if not with_timestamps: cmd.append("--no-timestamps")
        if diarize: cmd.append("--diarize")

        # IMPORTANTE: Asegurar permisos de ejecución al vuelo por si acaso
        try:
            st = os.stat(whisper_bin)
            os.chmod(whisper_bin, st.st_mode | 0o111) # +x
        except: pass

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
                                encoding="utf-8", errors="replace")
        current_process = proc
        if is_cancelled: proc.kill()  # cancelado entre ffmpeg y whisper

        # stderr se vacía en un hilo aparte: si nadie lo lee y whisper escribe más de
        # lo que cabe en la tubería (~64 KB), el proceso se queda bloqueado.
        # Solo guardamos las últimas líneas, que son las que explican un fallo.
        stderr_tail = collections.deque(maxlen=15)
        # Con un modelo truncado (descarga a medias) whisper.cpp no falla: lo trata
        # como "modelo vacío de pruebas", no transcribe nada y sale con código 0
        model_empty = False
        def drain_stderr():
            nonlocal model_empty
            for err_line in proc.stderr:
                if "no tensors loaded" in err_line: model_empty = True
                stderr_tail.append(err_line.rstrip())
        stderr_thread = threading.Thread(target=drain_stderr, daemon=True)
        stderr_thread.start()

        timestamp_pattern = re.compile(r"\[(\d{2}):(\d{2}):(\d{2}\.\d{3})")

        while True:
            if is_cancelled: break
            line = proc.stdout.readline()
            if not line and proc.poll() is not None: break
            if line:
                match = timestamp_pattern.search(line)
                if match and total_duration > 0:
                    h, m, s = map(float, match.groups())
                    curr = h * 3600 + m * 60 + s
                    callback_progress(curr / total_duration)
                if "system_info" not in line and "main:" not in line:
                    callback_text(line)

        if is_cancelled: raise Cancelled()

        returncode = proc.wait()
        stderr_thread.join(timeout=2)
        if returncode != 0:
            detalle = "\n".join(stderr_tail) or "(whisper-cli no dio detalles)"
            callback_progress(0)
            return fail(f"\n[ERROR] whisper-cli terminó con código {returncode}:\n{detalle}")
        if model_empty:
            callback_progress(0)
            return fail(f"\n[ERROR] El modelo {filename} está dañado o incompleto.\n"
                        f"Bórralo de {MODELS_DIR} y vuelve a descargarlo.")

        callback_progress(1.0)
        callback_text("\n[LISTO] Finalizado.")
        return None

    except Cancelled:
        callback_text("\n[INFO] Cancelado.")
        callback_progress(0)
        return None

    except Exception as e:
        return fail(f"\n[ERROR]: {str(e)}")

    finally:
        # Nunca dejar un whisper huérfano, salgamos por donde salgamos
        if proc and proc.poll() is None:
            proc.kill()
            proc.wait()
        current_process = None
        if os.path.exists(TEMP_WAV): os.remove(TEMP_WAV)
