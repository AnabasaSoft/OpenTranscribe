import os
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

    with urllib.request.urlopen(url, context=ctx) as response, open(dest_path, 'wb') as out_file:
        total_size = int(response.info().get('Content-Length', -1))
        downloaded = 0
        block_size = 8192
        while True:
            buffer = response.read(block_size)
            if not buffer: break
            downloaded += len(buffer)
            out_file.write(buffer)
            if total_size > 0: progress_callback(downloaded / total_size)

def stop_transcription():
    global current_process, is_cancelled
    is_cancelled = True
    if current_process:
        try: current_process.kill()
        except: pass
        current_process = None

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
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(TEMP_WAV): return TEMP_WAV
    raise Exception("Error al convertir audio.")

def run_transcription(input_file, model_selection, callback_text, callback_progress, with_timestamps=False, diarize=False):
    global current_process, is_cancelled

    whisper_bin = get_whisper_executable()

    # Verificación estricta: Si no está el binario, es error crítico
    if not whisper_bin:
        callback_text("[ERROR CRÍTICO] No se encontró el archivo 'whisper-cli' interno.\nReinstala la aplicación.")
        return

    filename = get_model_filename(model_selection)
    model_path = get_model_path(filename)
    if not os.path.exists(model_path):
        callback_text(f"[ERROR] Modelo no encontrado: {model_path}")
        return

    try:
        is_cancelled = False
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

        current_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        timestamp_pattern = re.compile(r"\[(\d{2}):(\d{2}):(\d{2}\.\d{3})")

        while True:
            if is_cancelled: break
            line = current_process.stdout.readline()
            if not line and current_process.poll() is not None: break
            if line:
                match = timestamp_pattern.search(line)
                if match and total_duration > 0:
                    h, m, s = map(float, match.groups())
                    curr = h * 3600 + m * 60 + s
                    callback_progress(curr / total_duration)
                if "system_info" not in line and "main:" not in line:
                    callback_text(line)

        if os.path.exists(TEMP_WAV): os.remove(TEMP_WAV)
        current_process = None

        if is_cancelled:
            callback_text("\n[INFO] Cancelado.")
            callback_progress(0)
        else:
            callback_progress(1.0)
            callback_text("\n[LISTO] Finalizado.")

    except Exception as e:
        callback_text(f"\n[ERROR]: {str(e)}")
