import customtkinter as ctk
import os
import subprocess
import shutil
from tkinter import filedialog, messagebox
import transcriber
import threading
import pygame
import time
import re
from tkinterdnd2 import TkinterDnD, DND_FILES
from PIL import Image
import webbrowser
import csv
try:
    from docx import Document
    from docx.shared import Pt, RGBColor
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False
    print("Nota: Instala 'python-docx' para exportar a Word.")
import platform
import sys
import tkinter as tk

def resource_path(relative_path):
    """Obtiene la ruta absoluta al recurso, funcione en dev o en PyInstaller"""
    try:
        # PyInstaller crea una carpeta temporal en _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def format_duration(seconds):
    """"MM:SS", o "H:MM:SS" a partir de una hora (con %M:%S, 1 h 05 min salía como "05:00")."""
    seconds = int(seconds)
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

SPEAKER_LABEL = re.compile(r"👤 Hablante (\d+|\?): ")
TIMESTAMP_PATTERN = re.compile(r"\[(\d{2}:\d{2}:\d{2}[\.,]\d{3}) --> (\d{2}:\d{2}:\d{2}[\.,]\d{3})\]")

def parse_transcript(raw_content):
    """Convierte el texto de la transcripción en una lista de segmentos
    {start, end, text}. Las líneas sin marca de tiempo que no siguen a un
    segmento (p. ej. transcripción sin "Modo Subtítulos") quedan con start/end vacíos."""
    lines_data = []
    current_seg = {"start": "", "end": "", "text": ""}

    for line in raw_content.split('\n'):
        match = TIMESTAMP_PATTERN.search(line)
        if match:
            # Guardar segmento previo
            if current_seg["start"]:
                lines_data.append(current_seg)

            # Normalizar tiempos (usar punto internamente) y quitar la marca del texto
            current_seg = {"start": match.group(1).replace(',', '.'),
                           "end": match.group(2).replace(',', '.'),
                           "text": TIMESTAMP_PATTERN.sub("", line).strip()}
        elif line.strip():
            if current_seg["start"]:
                # Texto continuado del segmento actual
                current_seg["text"] += " " + line.strip()
            else:
                # Texto sin tiempo
                lines_data.append({"start": "", "end": "", "text": line.strip()})

    # Añadir el último segmento
    if current_seg["start"]:
        lines_data.append(current_seg)
    return lines_data

def write_transcript(filename, ext, raw_content, heading):
    """Escribe la transcripción en el formato que indica ext."""
    lines_data = parse_transcript(raw_content)
    timed = [item for item in lines_data if item["start"]]

    # Sin marcas de tiempo no hay subtítulos posibles: mejor avisar que dejar un archivo vacío
    if ext in (".srt", ".vtt") and not timed:
        raise ValueError("El texto no tiene marcas de tiempo.\n"
                         "Activa 'Modo Subtítulos' y vuelve a transcribir para exportar subtítulos.")

    # --- A) MICROSOFT WORD (.docx) ---
    if ext == ".docx" and HAS_DOCX:
        doc = Document()
        doc.add_heading(heading, 0)

        for item in lines_data:
            p = doc.add_paragraph()

            # Tiempo en Azul
            if item["start"]:
                run_time = p.add_run(f"[{item['start']} - {item['end']}] ")
                run_time.bold = True
                run_time.font.color.rgb = RGBColor(0, 50, 150)

            # Detección de Hablantes (Rojo)
            text_content = item["text"]
            parts = text_content.split(":", 1)
            if "👤" in text_content and len(parts) > 1:
                run_speaker = p.add_run(parts[0] + ":")
                run_speaker.bold = True
                run_speaker.font.color.rgb = RGBColor(200, 0, 0)
                p.add_run(parts[1])
            else:
                p.add_run(text_content)

        doc.save(filename)

    # --- B) EXCEL / CSV (.csv) ---
    elif ext == ".csv":
        with open(filename, mode='w', newline='', encoding='utf-8-sig') as csv_file:
            writer = csv.writer(csv_file, delimiter=';')
            writer.writerow(['Inicio', 'Fin', 'Contenido'])
            for item in lines_data:
                writer.writerow([item["start"], item["end"], item["text"]])

    # --- C) SUBTÍTULOS VTT (.vtt) ---
    elif ext == ".vtt":
        with open(filename, "w", encoding="utf-8") as f:
            f.write("WEBVTT\n\n")
            for i, item in enumerate(timed, 1):
                f.write(f"{i}\n")
                f.write(f"{item['start']} --> {item['end']}\n")
                f.write(f"{item['text']}\n\n")

    # --- D) SUBTÍTULOS SRT (.srt) ---
    elif ext == ".srt":
        with open(filename, "w", encoding="utf-8") as f:
            for i, item in enumerate(timed, 1):
                f.write(f"{i}\n")
                # SRT requiere coma en milisegundos
                start_srt = item['start'].replace('.', ',')
                end_srt = item['end'].replace('.', ',')
                f.write(f"{start_srt} --> {end_srt}\n")
                f.write(f"{item['text']}\n\n")

    # --- E) TEXTO PLANO (.txt) ---
    else:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(raw_content)


# Configuración inicial
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class OpenTranscribeApp(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()

        self.TkdndVersion = TkinterDnD._require(self)
        # Sin dispositivo de sonido (o con el servidor de audio caído) init() lanza
        # pygame.error: la app debe arrancar igual, solo sin reproductor
        try:
            pygame.mixer.init()
            self.audio_ok = True
        except pygame.error as e:
            print(f"Reproductor desactivado (sin audio): {e}")
            self.audio_ok = False

        self.title("OpenTranscribe v2.0")
        self.geometry("750x700")

        try:
            # Buscamos icon.png usando la función segura
            icon_file = resource_path("icon.png")

            if os.path.exists(icon_file):
                # Para Linux/macOS (y Windows modernos con PNG) se usa iconphoto
                img_icon = tk.PhotoImage(file=icon_file)
                self.iconphoto(True, img_icon) # True aplica el icono a todas las ventanas futuras
            else:
                print(f"Advertencia: No se encontró {icon_file}")
        except Exception as e:
            print(f"Error cargando icono: {e}")

        # Configuración principal
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.unsaved_changes = False
        self.selected_file_path = ""
        self.is_playing = False
        self.total_duration = 0
        self.current_offset = 0
        self.transcript_segments = []
        self._slider_job = None  # after() pendiente del refresco del reproductor
        self._preview_token = 0   # identifica la última carga del reproductor
        self._preview_file = None # copia en Opus para formatos que pygame no abre
        transcriber.cleanup_previews()  # restos de una ejecución anterior

        self.queue_files = []
        self.is_batch_mode = False
        # True desde que arranca un trabajo hasta que su hilo termina de verdad
        # (no hasta que se pulsa Cancelar). Impide cargar archivos o lanzar otro trabajo.
        self.is_processing = False

        # ============================================================
        # 1. TÍTULO
        # ============================================================
        self.lbl_title = ctk.CTkLabel(self, text="OpenTranscribe", font=("Roboto Medium", 26))
        self.lbl_title.pack(pady=(20, 10))

        # ============================================================
        # 2. TARJETA DE CONTROL (Card UI)
        # ============================================================
        self.card_frame = ctk.CTkFrame(self, fg_color="#2b2b2b", corner_radius=15)
        self.card_frame.pack(fill="x", padx=25, pady=(0, 15))

        # Configuración de columnas de la tarjeta
        self.card_frame.grid_columnconfigure(0, weight=0) # Columna 0 ajustada al botón (NO se estira)
        self.card_frame.grid_columnconfigure(1, weight=1) # Columna 1 se estira (para el texto del archivo)
        self.card_frame.grid_columnconfigure(2, weight=0)

        # --- Fila A: Selección de Archivo ---
        # width=160 (Fijo), height=32 (Igual a guardar), SIN sticky
        self.btn_browse = ctk.CTkButton(self.card_frame, text="📂 Seleccionar Audio", command=self.select_file, width=160, height=32)
        self.btn_browse.grid(row=0, column=0, padx=(20, 10), pady=(20, 10))

        self.lbl_filename = ctk.CTkLabel(self.card_frame, text="Arrastra un archivo aquí...", text_color="gray", anchor="w")
        self.lbl_filename.grid(row=0, column=1, columnspan=2, padx=(0, 20), pady=(20, 10), sticky="ew")

        # --- Fila B: Reproductor ---
        self.frame_player = ctk.CTkFrame(self.card_frame, fg_color="transparent")
        self.frame_player.grid(row=1, column=0, columnspan=3, sticky="ew", padx=10, pady=5)

        self.btn_play = ctk.CTkButton(self.frame_player, text="▶", state="disabled", width=50, command=self.toggle_audio, fg_color="#444", height=30)
        self.btn_play.pack(side="left", padx=(5, 5))

        self.btn_stop = ctk.CTkButton(self.frame_player, text="⏹", state="disabled", width=40, command=self.stop_audio, fg_color="#800000", height=30)
        self.btn_stop.pack(side="left", padx=(0, 15))

        self.slider_audio = ctk.CTkSlider(self.frame_player, from_=0, to=1, command=self.seek_audio, height=18)
        self.slider_audio.set(0)
        self.slider_audio.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.lbl_audio_time = ctk.CTkLabel(self.frame_player, text="00:00 / 00:00", font=("Arial", 11), text_color="#aaa")
        self.lbl_audio_time.pack(side="right", padx=(0, 5))

        # --- Fila C: Configuración ---
        self.frame_settings = ctk.CTkFrame(self.card_frame, fg_color="transparent")
        self.frame_settings.grid(row=2, column=0, columnspan=3, sticky="ew", padx=15, pady=(15, 10))

        # Modelo
        ctk.CTkLabel(self.frame_settings, text="Modelo IA:", font=("Arial", 12, "bold")).pack(side="left", padx=(0, 10))
        self.combo_models = ctk.CTkComboBox(self.frame_settings, width=180, values=["Tiny (Muy rápido)", "Base (Equilibrado)", "Small (Preciso)", "Medium (Muy preciso)", "Large (Lento/Pro)"])
        self.combo_models.set("Base (Equilibrado)")
        self.combo_models.pack(side="left")

        # Switches (Usamos un frame a la derecha para apilarlos o ponerlos juntos)
        self.frame_switches = ctk.CTkFrame(self.frame_settings, fg_color="transparent")
        self.frame_switches.pack(side="right")

        self.switch_diarize = ctk.CTkSwitch(self.frame_switches, text="Hablantes por canal 👥")
        self.switch_diarize.pack(side="left", padx=(0, 15))

        self.switch_srt = ctk.CTkSwitch(self.frame_switches, text="Modo Subtítulos")
        self.switch_srt.pack(side="left")

        # --- Fila D: BOTONES DE ACCIÓN (Centrados y Tamaño Fijo) ---
        self.frame_big_btns = ctk.CTkFrame(self.card_frame, fg_color="transparent")
        self.frame_big_btns.grid(row=3, column=0, columnspan=3, sticky="ew", padx=15, pady=(15, 20))

        # Usamos columnas con peso para que los botones se centren en su mitad, pero no se estiren
        self.frame_big_btns.grid_columnconfigure(0, weight=1)
        self.frame_big_btns.grid_columnconfigure(1, weight=1)

        # Botón Transcribir: width=160, height=32. Quitamos sticky="ew" para que no se estire.
        self.btn_process = ctk.CTkButton(self.frame_big_btns, text="TRANSCRIBIR", font=("Arial", 12, "bold"), state="disabled", fg_color="green", hover_color="#006400", command=self.start_transcription, width=160, height=32)
        self.btn_process.grid(row=0, column=0, padx=10) # Centrado en su columna

        # Botón Cancelar: width=160, height=32.
        self.btn_cancel = ctk.CTkButton(self.frame_big_btns, text="CANCELAR", font=("Arial", 12, "bold"), state="disabled", fg_color="#8b0000", hover_color="#500000", command=self.cancel_transcription, width=160, height=32)
        self.btn_cancel.grid(row=0, column=1, padx=10) # Centrado en su columna

        # --- Fila E: Barra de Progreso ---
        self.progress_bar = ctk.CTkProgressBar(self.card_frame, height=6, corner_radius=0)
        self.progress_bar.grid(row=4, column=0, columnspan=3, sticky="ew", padx=15, pady=(0, 15))
        self.progress_bar.set(0)

        self.lbl_progress_percent = ctk.CTkLabel(self.card_frame, text="0%", font=("Arial", 10))
        self.lbl_progress_percent.place(relx=0.95, rely=0.92, anchor="e")

        # ============================================================
        # 3. ÁREA DE TEXTO
        # ============================================================
        self.frame_text = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_text.pack(fill="both", expand=True, padx=25, pady=(0, 10))

        self.textbox = ctk.CTkTextbox(self.frame_text, corner_radius=10, font=("Roboto", 14), fg_color="#1d1d1d", border_width=1, border_color="#333")
        self.textbox.pack(fill="both", expand=True)
        self.textbox.insert("0.0", "El texto transcrito aparecerá aquí...\n")
        self.textbox._textbox.bind("<KeyRelease>", self.mark_as_modified)
        self.textbox._textbox.tag_config("highlight", background="#005f73", foreground="#ffffff")

        # ============================================================
        # 4. BARRA INFERIOR
        # ============================================================
        self.frame_bottom = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_bottom.pack(fill="x", padx=25, pady=(0, 20))

        # Izquierda
        self.btn_help = ctk.CTkButton(self.frame_bottom, text="? Ayuda", command=self.abrir_ayuda, fg_color="#333", width=80, height=28)
        self.btn_help.pack(side="left", padx=(0, 10))

        self.btn_find = ctk.CTkButton(self.frame_bottom, text="🔍 Buscar", command=self.open_find_replace_dialog, fg_color="#333", width=80, height=28)
        self.btn_find.pack(side="left", padx=(0, 10))

        self.btn_clear = ctk.CTkButton(self.frame_bottom, text="🗑️ Limpiar", command=self.limpiar_texto, fg_color="#333", width=80, height=28)
        self.btn_clear.pack(side="left", padx=(0, 10))

        # Centro
        self.btn_sync = ctk.CTkButton(self.frame_bottom, text="🔄 Sincronizar Tiempos", command=self.sync_timestamps_manual, fg_color="#4a4a4a", width=140, height=28)
        self.btn_sync.pack(side="left")

        # Derecha (Referencia de tamaño)
        self.btn_save = ctk.CTkButton(self.frame_bottom, text="💾 Guardar Texto", command=self.save_text, fg_color="#1f6aa5", height=32, font=("Arial", 12, "bold"))
        self.btn_save.pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.al_soltar_archivo)

        self.after(500, self.check_system_requirements)

    # ==========================================================
    # LÓGICA DE LA APLICACIÓN (SIN CAMBIOS FUNCIONALES)
    # ==========================================================

    def mostrar_confirmacion_oscura(self, titulo, mensaje, texto_si="Sí", texto_no="No"):
        # Crear ventana emergente oscura
        dialog = ctk.CTkToplevel(self)
        dialog.title(titulo)
        dialog.geometry("350x180")
        dialog.resizable(False, False)

        # Hacemos que flote siempre encima
        dialog.attributes("-topmost", True)

        # Etiqueta con el mensaje
        lbl = ctk.CTkLabel(dialog, text=mensaje, font=("Roboto", 14), wraplength=300)
        lbl.pack(pady=30, padx=20)

        # Frame para los botones
        frame_btns = ctk.CTkFrame(dialog, fg_color="transparent")
        frame_btns.pack(pady=10)

        # Variable para guardar la respuesta
        self.respuesta_usuario = False

        def on_yes():
            self.respuesta_usuario = True
            dialog.destroy()

        def on_no():
            self.respuesta_usuario = False
            dialog.destroy()

        # Botones Sí/No estilizados
        btn_yes = ctk.CTkButton(frame_btns, text=texto_si, command=on_yes, fg_color="#8b0000", hover_color="#500000", width=100)
        btn_yes.pack(side="left", padx=10)

        btn_no = ctk.CTkButton(frame_btns, text=texto_no, command=on_no, fg_color="gray", hover_color="#555", width=100)
        btn_no.pack(side="right", padx=10)

        # Bloquear la ventana principal hasta que se responda.
        # En Linux grab_set falla si la ventana aún no es visible, de ahí el update()
        dialog.transient(self)
        dialog.update()
        try: dialog.grab_set()
        except: pass
        self.wait_window(dialog)

        return self.respuesta_usuario

    def cancel_transcription(self):
        # Usamos nuestra nueva alerta oscura
        confirm = self.mostrar_confirmacion_oscura("Cancelar", "¿Seguro que quieres detener la transcripción?")

        # El trabajo pudo terminar mientras el diálogo estaba abierto
        if confirm and self.is_processing:
            transcriber.stop_transcription()
            # TRANSCRIBIR sigue desactivado hasta que el hilo termine de verdad:
            # lo reactiva finish_transcription_ui
            self.btn_cancel.configure(state="disabled")
            self.btn_process.configure(text="Cancelando...")
            self.title("OpenTranscribe (Cancelando...)")
            self.progress_bar.set(0)
            self.lbl_progress_percent.configure(text="0%")

    def start_transcription(self):
        if self.is_processing: return

        # 1. Configuración básica
        srt_mode = self.switch_srt.get() == 1
        diarize_mode = self.switch_diarize.get() == 1
        model_name_ui = self.combo_models.get()
        exists, filename_model = transcriber.check_model_exists(model_name_ui)

        # 2. LÓGICA MODO COLA (BATCH)
        if self.is_batch_mode:
            # A) Preguntar FORMATO (Una vez para todos)
            target_ext = self.ask_export_format()
            if not target_ext: return # Cancelado

            # B) Preguntar DÓNDE GUARDAR (Una vez para todos)
            # Si el usuario cancela o lo deja vacío, usaremos la carpeta de origen de cada archivo.
            output_folder = filedialog.askdirectory(title="Seleccionar carpeta de destino (Cancelar = Misma carpeta que original)")

            # C) Comprobar MODELO y arrancar
            if not exists:
                # Si falta modelo: Descargar -> Y AUTOMÁTICAMENTE procesar cola
                msg = f"El modelo '{filename_model}' no está descargado.\nSe descargará y luego comenzará la cola automáticamente."
                resp = self.mostrar_confirmacion_oscura("Modelo Faltante", msg)
                if resp:
                    # Pasamos todos los datos necesarios para que arranque solo después
                    self.download_and_transcribe(
                        filename_model, srt_mode, diarize_mode, model_name_ui,
                        is_batch=True, batch_args=(list(self.queue_files), target_ext, output_folder)
                    )
            else:
                # Si el modelo ya está, arrancamos directo
                self.prepare_ui_for_process()
                self.btn_process.configure(text="Procesando Cola...")
                threading.Thread(target=self.run_batch_process,
                               args=(list(self.queue_files), model_name_ui, srt_mode, diarize_mode, target_ext, output_folder),
                               daemon=True).start()

        # 3. LÓGICA MODO INDIVIDUAL (Un solo archivo)
        else:
            # Fijamos el archivo ahora: si se leyera self.selected_file_path al acabar
            # la descarga, se transcribiría lo que estuviera cargado en ese momento
            input_file = self.selected_file_path
            if not input_file: return

            # La separación de hablantes compara los canales izquierdo y derecho
            if diarize_mode and transcriber.get_audio_channels(input_file) == 1:
                seguir = self.mostrar_confirmacion_oscura(
                    "Audio mono",
                    "Este audio es mono: no se pueden separar hablantes por canal.\n¿Transcribir sin separar hablantes?",
                    texto_si="Continuar", texto_no="Cancelar")
                if not seguir: return
                diarize_mode = False

            if not exists:
                msg = f"El modelo '{filename_model}' no está descargado.\n¿Deseas descargarlo ahora?"
                resp = self.mostrar_confirmacion_oscura("Modelo Faltante", msg)
                if resp:
                    self.download_and_transcribe(filename_model, srt_mode, diarize_mode, model_name_ui, is_batch=False, input_file=input_file)
            else:
                self.prepare_ui_for_process()
                threading.Thread(target=self.run_process, args=(input_file, srt_mode, diarize_mode, model_name_ui), daemon=True).start()

    def run_batch_process(self, file_list, model_name, srt_mode, diarize_mode, extension, output_folder=None):
        """Procesa la lista de archivos con una barra de progreso GLOBAL basada en el tiempo total."""
        guardados, fallidos = [], []
        try:
            self._run_batch_loop(file_list, model_name, srt_mode, diarize_mode, extension, output_folder, guardados, fallidos)
        except Exception as e:
            self.append_text(f"\n❌ Error inesperado en la cola: {e}\n")
            fallidos.append(("(cola)", str(e)))
        finally:
            # Siempre se cierra el trabajo, aunque algo falle: si no, is_processing
            # se quedaría a True y la app no dejaría volver a transcribir
            self.after(0, lambda: self._finish_batch(len(file_list), guardados, fallidos))

    def _run_batch_loop(self, file_list, model_name, srt_mode, diarize_mode, extension, output_folder, guardados, fallidos):
        # Los subtítulos necesitan marcas de tiempo aunque no esté activado "Modo Subtítulos"
        with_timestamps = srt_mode or extension in (".srt", ".vtt")

        # 1. FASE DE PREPARACIÓN: Calcular duración total de la cola
        self.run_on_ui(lambda: self.textbox.delete("0.0", "end"))
        self.append_text("⏳ Analizando duración total de la cola...\n")

        total_batch_duration = 0
        files_durations = {}

        # Pre-calculamos la duración de cada archivo para ponderar la barra
        for f in file_list:
            duration = transcriber.get_audio_duration(f)
            files_durations[f] = duration
            total_batch_duration += duration

        total_files = len(file_list)
        accumulated_time = 0 # Tiempo acumulado de los archivos ya terminados

        self.append_text(f"Total a procesar: {format_duration(total_batch_duration)}\n\n")

        # 2. BUCLE DE PROCESAMIENTO
        for index, audio_file in enumerate(file_list):
            if transcriber.is_cancelled: break

            # Datos del archivo actual
            file_name = os.path.basename(audio_file)
            current_file_duration = files_durations.get(audio_file, 0)

            # --- ACTUALIZACIÓN VISUAL DEL HEADER ---
            msg_header = f"--- [{index + 1}/{total_files}] PROCESANDO: {file_name} ---\n"
            msg_header += f"⏱️ Duración: {format_duration(current_file_duration)}\n"

            # Escribimos en el textbox sin borrar lo anterior para tener un historial
            self.append_text("\n" + msg_header)

            self.run_on_ui(self.title, f"OpenTranscribe (Archivo {index + 1} de {total_files})")

            # --- CALLBACK INTELIGENTE PARA LA BARRA GLOBAL ---
            def batch_progress_callback(local_percent):
                """
                Convierte el % del archivo actual en el % del total de la cola.
                Fórmula: (Tiempo_Acumulado + (Tiempo_Archivo * %_Local)) / Tiempo_Total
                """
                if total_batch_duration > 0:
                    # Cuántos segundos llevamos de ESTE archivo
                    seconds_done_current = current_file_duration * local_percent

                    # Cuántos segundos llevamos EN TOTAL (anteriores + actual)
                    total_seconds_done = accumulated_time + seconds_done_current

                    # Porcentaje global (0.0 a 1.0)
                    global_percent = total_seconds_done / total_batch_duration

                    # Barra y texto en una sola llamada al hilo principal, para que
                    # el "(Total)" no lo pise después el texto de _update_progress_gui
                    def _update_global():
                        self.progress_bar.set(global_percent)
                        self.lbl_progress_percent.configure(text=f"{int(global_percent * 100)}% (Total)")
                    self.run_on_ui(_update_global)

            # --- EJECUCIÓN ---
            # Acumulamos solo el texto de este archivo para el guardado
            text_parts = []

            if diarize_mode and transcriber.get_audio_channels(audio_file) == 1:
                self.append_text("ℹ️ Audio mono: se transcribe sin separar hablantes\n")

            error = transcriber.run_transcription(
                audio_file,
                model_name,
                text_parts.append,
                batch_progress_callback, # Usamos el nuevo callback global
                with_timestamps=with_timestamps,
                diarize=diarize_mode
            )

            if error:
                # El acumulador no se muestra en pantalla: hay que enseñar el error aquí
                # y no guardarlo como si fuera la transcripción
                self.append_text(f"❌ {error}\n")
                fallidos.append((file_name, error))
            elif not transcriber.is_cancelled:
                try:
                    saved_path = self.auto_save_transcript("".join(text_parts), audio_file, extension, output_folder)
                    self.append_text(f"✅ Guardado en: {os.path.basename(saved_path)}\n")
                    guardados.append(saved_path)
                except Exception as e:
                    self.append_text(f"❌ Error guardando: {e}\n")
                    fallidos.append((file_name, str(e)))

            accumulated_time += current_file_duration

            # Pequeña pausa para respirar
            time.sleep(1)

    def _finish_batch(self, total_files, guardados, fallidos):
        """Resumen final de la cola (hilo principal)."""
        cancelado = transcriber.is_cancelled
        self.finish_transcription_ui(failed=not guardados and bool(fallidos) and not cancelado)

        resumen = f"Guardados: {len(guardados)} de {total_files}"
        if fallidos:
            resumen += f"\nCon error: {len(fallidos)}"
            for nombre, _ in fallidos[:5]:
                resumen += f"\n  • {nombre}"
            if len(fallidos) > 5:
                resumen += f"\n  • ... y {len(fallidos) - 5} más (detalles en el texto)"

        if cancelado:
            titulo = "Cola Cancelada"
            resumen += f"\nSin procesar: {total_files - len(guardados) - len(fallidos)}"
        elif fallidos:
            titulo = "Cola Finalizada con Errores"
        else:
            titulo = "Cola Finalizada"
            self.progress_bar.set(1)
            self.lbl_progress_percent.configure(text="100%")
            self.title("OpenTranscribe (Cola finalizada)")

        self.append_text(f"\n=== {titulo} ===\n{resumen}\n")
        self.mostrar_alerta_oscura(titulo, resumen)

    def prepare_ui_for_process(self):
        self.is_processing = True
        transcriber.reset_cancellation()
        self.btn_browse.configure(state="disabled")
        self.textbox.delete("0.0", "end")
        self.transcript_segments = []
        self.btn_process.configure(state="disabled", text="Procesando...")
        self.btn_cancel.configure(state="normal")
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)
        self.unsaved_changes = True
        self.title("OpenTranscribe v2.0 Pro * (Trabajando)")

    def download_and_transcribe(self, filename, srt_mode, diarize_mode, model_name_ui, is_batch=False, batch_args=None, input_file=None):
        """Descarga el modelo y encadena la transcripción automáticamente (Individual o Cola)."""
        self.prepare_ui_for_process()
        self.btn_process.configure(text="Descargando...")
        self.title("OpenTranscribe (Descargando Modelo...)")

        def thread_target():
            try:
                # 1. Descargar
                self.append_text(f"Iniciando descarga de {filename}...\n")
                transcriber.download_model(filename, self.update_progress)
                self.append_text("Descarga completada.\n\n")

                # 2. Transición automática a la tarea principal
                if is_batch and batch_args:
                    # Desempaquetamos los argumentos: (lista, extensión, carpeta_salida)
                    queue_files, target_ext, output_folder = batch_args

                    self.append_text("Iniciando procesamiento de cola automáticamente...\n")
                    # Llamamos directamente a la función de cola (ya estamos en un hilo, así que es seguro)
                    self.run_batch_process(queue_files, model_name_ui, srt_mode, diarize_mode, target_ext, output_folder)

                else:
                    # Modo Individual: limpiamos los mensajes de la descarga para que
                    # en el cuadro (y en lo que se guarde) quede solo la transcripción
                    self.run_on_ui(lambda: self.textbox.delete("0.0", "end"))
                    self.update_progress(0)
                    error = transcriber.run_transcription(
                        input_file,
                        model_name_ui,
                        self.update_text_area,
                        self.update_progress,
                        with_timestamps=srt_mode,
                        diarize=diarize_mode
                    )
                    self.after(0, lambda: [self.finish_transcription_ui(failed=bool(error)), self.sync_timestamps_from_text()])

            except transcriber.Cancelled:
                self.append_text("\n[INFO] Descarga cancelada.")
                self.after(0, self.finish_transcription_ui)
            except Exception as e:
                self.append_text(f"\nError crítico: {e}")
                self.after(0, lambda: self.finish_transcription_ui(failed=True))

        threading.Thread(target=thread_target, daemon=True).start()

    def run_process(self, input_file, srt_mode, diarize_mode, model_name):
        error = transcriber.run_transcription(
            input_file,
            model_name,
            self.update_text_area,
            self.update_progress,
            with_timestamps=srt_mode,
            diarize=diarize_mode # <--- Se lo pasamos a transcriber.py
        )
        self.after(0, lambda: [self.finish_transcription_ui(failed=bool(error)), self.sync_timestamps_from_text()])

    def finish_transcription_ui(self, failed=False):
        self.is_processing = False
        self.btn_browse.configure(state="normal")
        self.btn_process.configure(state="normal", text="Transcribir")
        self.btn_cancel.configure(state="disabled")
        if transcriber.is_cancelled:
            self.title("OpenTranscribe (Cancelado)")
            self.lbl_progress_percent.configure(text="Cancelado")
        elif failed:
            self.progress_bar.set(0)
            self.lbl_progress_percent.configure(text="Error")
            self.title("OpenTranscribe (Error)")
        else:
            self.progress_bar.set(1)
            self.lbl_progress_percent.configure(text="100%")
            self.title("OpenTranscribe * (Terminado, sin guardar)")

    def parse_and_insert_line(self, text_line):
        # transcriber ya convierte "(speaker 0)" en "👤 Hablante 1: "; aquí solo
        # se colorea esa etiqueta
        match = SPEAKER_LABEL.search(text_line)

        if match:
            # Insertamos lo anterior (tiempos, si los hay) normal
            self.textbox.insert("end", text_line[:match.start()])

            # Hablante en azul y negrita. Se configura en el Text interno porque
            # CTkTextbox.tag_config no admite "font"
            self.textbox._textbox.tag_config("speaker", foreground="#4da6ff", font=("Roboto", 14, "bold"))
            self.textbox.insert("end", match.group(0), "speaker")

            # Lo que dicen (ya trae su salto de línea)
            self.textbox.insert("end", text_line[match.end():])
        else:
            self.textbox.insert("end", text_line)

        self.textbox.see("end")

    def sync_timestamps_from_text(self):
        self.transcript_segments = []
        total_lines = int(self.textbox.index("end-1c").split('.')[0])
        pattern = re.compile(r"\[(\d{2}):(\d{2}):(\d{2}\.\d{3}) --> (\d{2}):(\d{2}):(\d{2}\.\d{3})\]")
        for i in range(1, total_lines + 1):
            line_idx = f"{i}.0"
            line_end_idx = f"{i}.end"
            line_text = self.textbox.get(line_idx, line_end_idx)
            match = pattern.search(line_text)
            if match:
                try:
                    h1, m1, s1 = map(float, match.group(1, 2, 3))
                    start_seconds = h1 * 3600 + m1 * 60 + s1
                    h2, m2, s2 = map(float, match.group(4, 5, 6))
                    end_seconds = h2 * 3600 + m2 * 60 + s2
                    segment_data = {'start': start_seconds, 'end': end_seconds, 'idx_start': line_idx, 'idx_end': line_end_idx}
                    self.transcript_segments.append(segment_data)
                except ValueError: continue

    def sync_timestamps_manual(self):
        self.sync_timestamps_from_text()
        self.mostrar_alerta_oscura("Sincronizado", "Se han actualizado los tiempos del Karaoke.")

    def start_slider_loop(self):
        """Arranca el refresco del reproductor sustituyendo el que hubiera programado.
        Llamar directamente a update_audio_slider_loop en cada seek o reanudación
        añadía un bucle más cada vez, y se acumulaban."""
        if self._slider_job:
            self.after_cancel(self._slider_job)
        self._slider_job = None
        self.update_audio_slider_loop()

    def update_audio_slider_loop(self):
        self._slider_job = None
        if self.is_playing and self.total_duration > 0:
            current_time = self.current_offset + (pygame.mixer.music.get_pos() / 1000)
            if current_time > self.total_duration:
                self.stop_audio()
                return
            self.slider_audio.set(current_time / self.total_duration)
            current_str = format_duration(current_time)
            total_str = format_duration(self.total_duration)
            self.lbl_audio_time.configure(text=f"{current_str} / {total_str}")
            for seg in self.transcript_segments:
                if seg['start'] <= current_time <= seg['end']:
                    self.textbox._textbox.tag_add("highlight", seg['idx_start'], seg['idx_end'])
                else:
                    self.textbox._textbox.tag_remove("highlight", seg['idx_start'], seg['idx_end'])
            self._slider_job = self.after(100, self.update_audio_slider_loop)

    def toggle_audio(self):
        if not self.is_playing:
            try:
                if len(self.transcript_segments) == 0: self.sync_timestamps_from_text()
                if pygame.mixer.music.get_pos() == -1: pygame.mixer.music.play()
                else:
                     pygame.mixer.music.unpause()
                     if not pygame.mixer.music.get_busy(): pygame.mixer.music.play(start=self.current_offset)
                self.is_playing = True
                self.btn_play.configure(text="⏸ Pausa", fg_color="#555")
                self.start_slider_loop()
            except Exception as e: print(e)
        else:
            pygame.mixer.music.pause()
            self.is_playing = False
            self.btn_play.configure(text="▶ Reanudar", fg_color="#333")

    def select_file(self):
        """Abre el explorador nativo del sistema."""
        # Filtros de archivo
        file_types = [
            ("Todos los medios", "*.mp3 *.wav *.m4a *.mp4 *.mkv *.mov *.avi *.webm *.flv"),
            ("Audio", "*.mp3 *.wav *.m4a"),
            ("Vídeo", "*.mp4 *.mkv *.mov *.avi *.webm *.flv"),
            ("Todos los archivos", "*.*")
        ]

        # Usamos filedialog nativo (permite selección múltiple)
        filenames = filedialog.askopenfilenames(
            title="Seleccionar Archivos",
            filetypes=file_types
        )

        if not filenames:
            return # Cancelado

        # Pasamos la lista tal cual: unirla en un string y volver a separarla
        # rompería las rutas con espacios
        self.cargar_archivos(list(filenames))

    def al_soltar_archivo(self, event):
        self.cargar_archivos(self.parse_dropped_files(event.data))

    def cargar_archivos(self, filepaths):
        """Carga 1 archivo (modo normal) o varios (modo cola)."""
        if not filepaths:
            return

        if self.is_processing:
            self.mostrar_alerta_oscura("Ocupado", "Espera a que termine el trabajo actual o cancélalo antes de cargar otro archivo.")
            return

        valid_exts = ['.mp3', '.wav', '.m4a', '.mp4', '.mkv', '.mov', '.avi', '.webm', '.flv']

        if len(filepaths) == 1:
            # Comportamiento normal (1 archivo)
            self.queue_files = []
            self.is_batch_mode = False
            self.cargar_archivo_comun(filepaths[0])
        else:
            # MODO BATCH
            self.queue_files = filepaths
            self.is_batch_mode = True

            # Validar extensiones
            valid_files = [f for f in filepaths if any(f.lower().endswith(ext) for ext in valid_exts)]
            self.queue_files = valid_files

            if not valid_files:
                self.mostrar_alerta_oscura("Error", "Ningún archivo válido detectado.")
                return

            # Actualizar UI
            self.lbl_filename.configure(text=f"📚 COLA: {len(valid_files)} archivos listos", text_color="#4da6ff")
            self.btn_process.configure(state="normal", text="Procesar Cola 📚")
            self.btn_play.configure(state="disabled") # No reproducimos en modo cola
            self.textbox.delete("0.0", "end")
            self.textbox.insert("0.0", "Modo Cola activado.\nArchivos detectados:\n\n")
            for f in valid_files:
                self.textbox.insert("end", f"• {os.path.basename(f)}\n")

    def cargar_archivo_comun(self, filename):
        # 1. Validar extensión
        extensiones_validas = ['.mp3', '.wav', '.m4a', '.mp4', '.mkv', '.mov', '.avi', '.webm', '.flv']

        if not any(filename.lower().endswith(ext) for ext in extensiones_validas):
            self.mostrar_alerta_oscura("Error", "Formato no soportado.")
            return

        # 2. Resetear variables de Cola (IMPORTANTE para salir del modo Batch)
        self.is_batch_mode = False
        self.queue_files = []

        # 3. Actualizar Referencias
        self.selected_file_path = filename
        self.lbl_filename.configure(text=os.path.basename(filename), text_color="white")

        # 4. RESTAURAR UI (Aquí estaba el fallo)
        # Volvemos el botón a su texto normal
        self.btn_process.configure(state="normal", text="TRANSCRIBIR")

        # Limpiamos la caja de texto (borramos la lista de la cola anterior)
        self.textbox.delete("0.0", "end")
        self.textbox.insert("0.0", "El texto transcrito aparecerá aquí...\n")

        # Reseteamos barras de progreso
        self.progress_bar.set(0)
        self.lbl_progress_percent.configure(text="0%")

        # 5. Cargar Previsualización de Audio
        self.load_audio_preview()

    def load_audio_preview(self):
        if not self.selected_file_path: return
        if not self.audio_ok:
            self.btn_play.configure(state="disabled", text="▶ Sin audio")
            return
        if self.is_playing or pygame.mixer.music.get_busy():
            self.stop_audio()
        self.total_duration = transcriber.get_audio_duration(self.selected_file_path)
        self.slider_audio.set(0)
        self.current_offset = 0
        self.is_playing = False
        self._preview_token += 1
        try:
            pygame.mixer.music.load(self.selected_file_path)
            self._set_preview_file(None)
            self._preview_ready()
        except Exception:
            # pygame no abre AAC ni vídeo (M4A, MP4, MKV...): se extrae el audio con
            # ffmpeg en segundo plano, porque en archivos largos tarda unos segundos
            self.btn_play.configure(state="disabled", text="⏳ Preparando...")
            self.btn_stop.configure(state="disabled")
            token, source = self._preview_token, self.selected_file_path
            def worker():
                path = transcriber.convert_for_preview(source)
                self.run_on_ui(self._preview_converted, token, path)
            threading.Thread(target=worker, daemon=True).start()

    def _preview_converted(self, token, path):
        if token != self._preview_token:
            # Se cargó otro archivo mientras se convertía este
            if path and os.path.exists(path): os.remove(path)
            return
        if path:
            try:
                pygame.mixer.music.load(path)
                self._set_preview_file(path)
                self._preview_ready()
                return
            except Exception as e:
                print(f"Error cargando audio: {e}")
                os.remove(path)
        self.btn_play.configure(state="disabled", text="▶ No disponible")
        self.lbl_audio_time.configure(text="Sin vista previa")

    def _set_preview_file(self, path):
        """Recuerda la copia que está cargada y borra la anterior (pygame ya no la
        tiene abierta tras el load nuevo). Solo esa: borrar todas las preview_*
        eliminaría la de una conversión que aún esté en marcha."""
        old, self._preview_file = self._preview_file, path
        if old and old != path and os.path.exists(old):
            os.remove(old)

    def _preview_ready(self):
        self.btn_play.configure(state="normal", text="▶ Reproducir", fg_color="#333")
        self.btn_stop.configure(state="normal")
        total_str = format_duration(self.total_duration)
        self.lbl_audio_time.configure(text=f"00:00 / {total_str}")
        self.sync_timestamps_from_text()

    def stop_audio(self):
        pygame.mixer.music.stop()
        self.is_playing = False
        self.current_offset = 0
        self.slider_audio.set(0)
        self.textbox._textbox.tag_remove("highlight", "1.0", "end")
        self.btn_play.configure(text="▶ Reproducir", fg_color="#333")
        total_str = format_duration(self.total_duration)
        self.lbl_audio_time.configure(text=f"00:00 / {total_str}")

    def seek_audio(self, value):
        if not self.audio_ok: return
        if self.total_duration > 0:
            target_time = value * self.total_duration
            self.current_offset = target_time
            pygame.mixer.music.play(start=target_time)
            if not self.is_playing: pygame.mixer.music.pause()
            else:
                self.is_playing = True
                self.btn_play.configure(text="⏸ Pausa", fg_color="#555")
                self.start_slider_loop()

    def run_on_ui(self, func, *args):
        """Ejecuta func en el hilo principal. Tkinter no es thread-safe, así que
        los hilos de trabajo nunca deben tocar widgets directamente."""
        self.after(0, lambda: func(*args))

    def append_text(self, text):
        """Añade texto al final del textbox; seguro desde cualquier hilo."""
        def _append():
            self.textbox.insert("end", text)
            self.textbox.see("end")
        self.run_on_ui(_append)

    def update_text_area(self, text):
        # Lo llama transcriber desde el hilo de trabajo
        self.run_on_ui(self.parse_and_insert_line, text)

    def update_progress(self, progress_float):
        self.after(0, lambda: self._update_progress_gui(progress_float))

    def _update_progress_gui(self, value):
        self.progress_bar.set(value)
        percent_text = f"{int(value * 100)}%"
        self.lbl_progress_percent.configure(text=percent_text)

    def save_text(self):
        """Guardado nativo robusto."""
        if self.is_batch_mode:
            self.mostrar_alerta_oscura("Aviso", "En modo Cola el guardado es automático.")
            return

        raw_content = self.textbox.get("0.0", "end").strip()
        if not raw_content or "El texto transcrito aparecerá aquí" in raw_content:
            self.mostrar_alerta_oscura("Error", "No hay texto para guardar.")
            return

        # Filtros
        filtros = [
            ("Documento Word (*.docx)", "*.docx") if HAS_DOCX else None,
            ("Texto Plano (*.txt)", "*.txt"),
            ("Subtítulos SRT (*.srt)", "*.srt"),
            ("Subtítulos VTT (*.vtt)", "*.vtt"),
            ("Excel / CSV (*.csv)", "*.csv")
        ]
        filtros = [f for f in filtros if f is not None]

        # Diálogo nativo
        filename = filedialog.asksaveasfilename(
            title="Guardar Transcripción",
            defaultextension=".docx" if HAS_DOCX else ".txt",
            filetypes=filtros
        )

        if not filename:
            return

        ext = os.path.splitext(filename)[1].lower()

        try:
            write_transcript(filename, ext, raw_content, 'Transcripción - OpenTranscribe')

            # 5. FINALIZACIÓN
            self.unsaved_changes = False
            self.title("OpenTranscribe v2.0 Pro")
            self.mostrar_alerta_oscura("Guardado", f"Archivo guardado exitosamente:\n{os.path.basename(filename)}")

        except Exception as e:
            print(f"Error guardando: {e}")
            self.mostrar_alerta_oscura("Error", f"No se pudo guardar el archivo:\n{str(e)}")

    def open_find_replace_dialog(self):
        self.dialog = ctk.CTkToplevel(self)
        self.dialog.title("Buscar y Reemplazar")
        self.dialog.geometry("400x250")
        self.dialog.attributes("-topmost", True)
        ctk.CTkLabel(self.dialog, text="Buscar palabra:").pack(pady=(20, 5))
        entry_find = ctk.CTkEntry(self.dialog, width=250)
        entry_find.pack(pady=5)
        ctk.CTkLabel(self.dialog, text="Reemplazar con:").pack(pady=(10, 5))
        entry_replace = ctk.CTkEntry(self.dialog, width=250)
        entry_replace.pack(pady=5)
        def ejecutar_reemplazo():
            texto_a_buscar = entry_find.get()
            texto_nuevo = entry_replace.get()
            if texto_a_buscar: self.perform_replace(texto_a_buscar, texto_nuevo, parent_window=self.dialog)
        ctk.CTkButton(self.dialog, text="Reemplazar Todo", command=ejecutar_reemplazo, fg_color="#1f6aa5").pack(pady=20)

    def perform_replace(self, old_text, new_text, parent_window):
        # Se reemplaza cada aparición en su sitio. Antes se borraba todo y se volvía
        # a insertar: se perdía el formato de los hablantes y se añadía una línea en
        # blanco por uso (get(..., "end") incluye el "\n" final de Tk)
        tb = self.textbox._textbox
        match_len = tk.IntVar()
        pos, total = "1.0", 0
        while True:
            pos = tb.search(old_text, pos, stopindex="end", count=match_len)
            if not pos: break
            # Mismo formato que el texto sustituido (salvo resaltado del karaoke y selección)
            tags = tuple(t for t in tb.tag_names(pos) if t not in ("highlight", "sel"))
            tb.delete(pos, f"{pos}+{match_len.get()}c")
            # Marca con gravedad derecha: queda tras el texto insertado y la búsqueda
            # sigue desde ahí (no se vuelve a encontrar si new_text contiene old_text)
            tb.mark_set("replace_end", pos)
            tb.mark_gravity("replace_end", "right")
            tb.insert(pos, new_text, tags)
            pos = tb.index("replace_end")
            total += 1
        tb.mark_unset("replace_end")

        if not total:
            self.mostrar_alerta_oscura("Error", f"No se encontró '{old_text}'", parent_window)
            return
        self.mark_as_modified()
        self.sync_timestamps_from_text()
        veces = "1 vez" if total == 1 else f"{total} veces"
        self.mostrar_alerta_oscura("Éxito", f"Se reemplazó '{old_text}' por '{new_text}' ({veces}).", parent_window)

    def mostrar_alerta_oscura(self, titulo, mensaje, parent_window=None):
        padre = parent_window if parent_window else self
        popup = ctk.CTkToplevel(padre)
        popup.title(titulo)
        popup.geometry("350x180")
        popup.resizable(False, False)
        popup.grid_columnconfigure(0, weight=1)
        popup.grid_rowconfigure(0, weight=1)
        lbl = ctk.CTkLabel(popup, text=mensaje, font=("Roboto", 14), wraplength=300)
        lbl.pack(pady=40, padx=20)
        btn = ctk.CTkButton(popup, text="Aceptar", command=popup.destroy, width=100)
        btn.pack(pady=(0, 20))
        popup.attributes("-topmost", True)
        popup.update()
        try: popup.grab_set()
        except: pass
        padre.wait_window(popup)

    def mark_as_modified(self, event=None):
        keys_to_ignore = ["Control_L", "Control_R", "Alt_L", "Shift_L", "Up", "Down", "Left", "Right"]
        if event and event.keysym in keys_to_ignore: return
        if not self.unsaved_changes:
            self.unsaved_changes = True
            self.title("OpenTranscribe * (Sin guardar)")

    def on_closing(self):
        if self.unsaved_changes:
            # Usamos nuestra nueva alerta oscura
            salir = self.mostrar_confirmacion_oscura("Salir", "Tienes cambios sin guardar.\n¿Estás seguro de que quieres salir?",
                                                     texto_si="Sí, salir", texto_no="Cancelar")
            if salir:
                self.cerrar_app()
        else:
            self.cerrar_app()

    def cerrar_app(self):
        # Los hilos de trabajo son daemon y mueren con la app, pero ffmpeg/whisper
        # son procesos aparte: si no se matan, siguen consumiendo CPU tras cerrar
        transcriber.stop_transcription()
        try: pygame.mixer.quit()
        except: pass
        transcriber.cleanup_previews()
        self.destroy()

    def abrir_ayuda(self):
        # Crear ventana emergente más grande
        ayuda_window = ctk.CTkToplevel(self)
        ayuda_window.title("Manual de Usuario - OpenTranscribe")
        ayuda_window.geometry("550x860") # Alto suficiente para logo + manual + contacto
        ayuda_window.resizable(False, True) # Permitir redimensionar alto
        ayuda_window.attributes("-topmost", True)

        # 1. LOGO (Depurado y Ajustado)
        try:
            logo_path = "Logo.jpg"
            # Soporte para modo congelado (exe/binario)
            if hasattr(sys, '_MEIPASS'):
                logo_path = os.path.join(sys._MEIPASS, "Logo.jpg")
            # Soporte para modo desarrollo local
            elif not os.path.exists(logo_path):
                logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Logo.jpg")

            if os.path.exists(logo_path):
                img_data = Image.open(logo_path)

                # --- CONFIGURACIÓN DE TAMAÑO ---
                # La ventana mide 550px de ancho.
                # 350px es un tamaño muy bueno (grande pero cabe con márgenes).
                ancho_deseado = 350

                # Calculamos el alto proporcional (Regla de tres)
                w_original, h_original = img_data.size
                ratio = ancho_deseado / float(w_original)
                alto_calculado = int(float(h_original) * float(ratio))

                print(f"DEBUG: Cargando logo. Original: {w_original}x{h_original} -> Nuevo: {ancho_deseado}x{alto_calculado}")

                logo_img = ctk.CTkImage(light_image=img_data, dark_image=img_data,
                                      size=(ancho_deseado, alto_calculado))

                lbl_img = ctk.CTkLabel(ayuda_window, text="", image=logo_img)
                lbl_img.pack(pady=(20, 10))
            else:
                print(f"DEBUG: No se encontró el archivo en: {logo_path}")

        except Exception as e:
            print(f"ERROR cargando el logo: {e}")

        ctk.CTkLabel(ayuda_window, text="OpenTranscribe v2.0", font=("Roboto Medium", 20)).pack(pady=5)

        # 2. ÁREA DE TEXTO CON SCROLL (Para todo el manual)
        # Usamos Textbox en modo lectura para que sea scrollable y copiable
        info_text = ctk.CTkTextbox(ayuda_window, width=500, height=480, corner_radius=10,
                                   fg_color="#232323", text_color="#eeeeee", font=("Consolas", 12))
        # Se coloca (pack) al final: así, si la ventana es más baja de lo necesario,
        # encoge el manual (que tiene scroll) y no se cortan el contacto ni Cerrar

        # --- CONTENIDO DEL MANUAL ---
        manual = (
            "============================================\n"
            "GUÍA DE FUNCIONES PRINCIPALES\n"
            "============================================\n\n"

            "1. TRANSCRIPCIÓN BÁSICA\n"
            "----------------------\n"
            "• Arrastra un archivo de audio o vídeo a la ventana.\n"
            "• Elige el 'Modelo IA' (Base es recomendado).\n"
            "• Pulsa 'TRANSCRIBIR'.\n\n"

            "2. MODO COLA (Lotes / Batch) [NUEVO] 📚\n"
            "------------------------------------\n"
            "• Arrastra MÚLTIPLES archivos a la vez (ej. 10 vídeos).\n"
            "• La aplicación detectará el modo 'Cola'.\n"
            "• Pulsa 'Procesar Cola'.\n"
            "• Te preguntará el formato (Word, TXT, SRT o CSV) y la\n"
            "  carpeta de destino. Si cancelas la carpeta, cada\n"
            "  archivo se guarda junto a su original.\n"
            "• Las transcripciones se guardan AUTOMÁTICAMENTE y al\n"
            "  final verás un resumen (guardados, errores...).\n\n"

            "3. SOPORTE MULTIMEDIA 🎬\n"
            "------------------------\n"
            "• Aceptamos: MP3, WAV, M4A (Audio).\n"
            "• Aceptamos: MP4, MKV, AVI, MOV, WEBM (Vídeo).\n"
            "• El vídeo se procesa internamente, no necesitas\n"
            "  extraer el audio antes.\n\n"

            "4. HERRAMIENTAS INTELIGENTES\n"
            "----------------------------\n"
            "• Hablantes por canal 👥: Para grabaciones ESTÉREO con\n"
            "  cada persona en un canal (llamadas, podcasts con un\n"
            "  micro por persona). Izquierdo = Hablante 1,\n"
            "  derecho = Hablante 2. Con audio mono no se aplica.\n"
            "• Modo Subtítulos: Genera marcas de tiempo exactas.\n"
            "  Necesario para exportar .SRT/.VTT y para el karaoke.\n"
            "• Reproductor Karaoke: Pulsa ▶ para escuchar el audio\n"
            "  y ver cómo se resalta el texto en tiempo real.\n"
            "• Sincronizar: Si editas el texto manualmente, pulsa\n"
            "  este botón para recalcular los tiempos del karaoke.\n\n"

            "5. EXPORTACIÓN\n"
            "--------------\n"
            "• Word (.docx): Con colores y negritas.\n"
            "• Subtítulos (.srt/.vtt): Listos para YouTube/VLC.\n"
            "• Excel (.csv): Para análisis de datos.\n"
            "• Texto (.txt): Simple y ligero.\n"
        )

        info_text.insert("0.0", manual)
        info_text.configure(state="disabled") # Hacemos que sea solo lectura

        # 3. SECCIÓN DE CONTACTO
        frame_contact = ctk.CTkFrame(ayuda_window, fg_color="transparent")
        # Botón Cerrar (abajo del todo; se coloca antes que el contacto por ir con side="bottom")
        ctk.CTkButton(ayuda_window, text="Cerrar", command=ayuda_window.destroy,
                      fg_color="#333", hover_color="#444", width=100).pack(side="bottom", pady=(5, 20))
        frame_contact.pack(side="bottom", pady=10, fill="x")

        ctk.CTkLabel(frame_contact, text="¿Dudas o Bugs?", font=("Roboto", 12, "bold")).pack()

        # Email Clicable
        lbl_mail = ctk.CTkLabel(frame_contact, text="anabasasoft@gmail.com", text_color="#4da6ff", cursor="hand2")
        lbl_mail.pack()
        lbl_mail.bind("<Button-1>", lambda e: webbrowser.open("mailto:anabasasoft@gmail.com"))

        # Web Clicable
        lbl_web = ctk.CTkLabel(frame_contact, text="anabasasoft.github.io", text_color="#4da6ff", cursor="hand2")
        lbl_web.pack()
        lbl_web.bind("<Button-1>", lambda e: webbrowser.open("https://anabasasoft.github.io"))

        info_text.pack(pady=10, padx=20, fill="both", expand=True)

    def check_system_requirements(self):
        """Verifica dependencias del sistema"""
        missing = []

        # 1. Verificar FFMPEG (Esto depende del usuario)
        if not transcriber.get_ffmpeg_executable():
            missing.append("FFmpeg (Necesario para procesar audio)")

        # 2. Verificar Whisper (Debería estar incluido)
        if not transcriber.get_whisper_executable():
            missing.append("ERROR: No se encuentra el motor interno (whisper-cli)")

        if missing:
            msg = "Faltan componentes necesarios:\n\n"
            for item in missing:
                msg += f"❌ {item}\n"

            if shutil.which("apt"): # Si es Debian/Ubuntu/Mint
                msg += "\nIntenta instalar FFmpeg con:\nsudo apt install ffmpeg"

            self.mostrar_alerta_oscura("Faltan Dependencias", msg)

    def parse_dropped_files(self, data):
        """Convierte el string de TkinterDnD en una lista de rutas limpias."""
        # Si viene entre corchetes {} (común en Linux/Windows con espacios)
        # Usamos regex para separar
        files = []
        if data.startswith('{') or '}' in data:
            parts = re.findall(r'\{.*?\}|\S+', data)
            for part in parts:
                path = part.strip('{}')
                if os.path.isfile(path):
                    files.append(path)
        else:
            # Caso simple: un archivo o varios sin espacios
            candidates = data.split()
            for c in candidates:
                if os.path.isfile(c):
                    files.append(c)

        # Fallback: si el regex falla, intentamos usar data directo si es un archivo
        if not files and os.path.isfile(data):
            files = [data]

        return files

    def ask_export_format(self):
        """Pregunta al usuario en qué formato guardar los archivos de la cola."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Formato de Salida")
        dialog.geometry("300x250")
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)

        self.selected_format = None

        ctk.CTkLabel(dialog, text="Elige el formato para guardar:", font=("Roboto", 14, "bold")).pack(pady=20)

        def set_format(fmt):
            self.selected_format = fmt
            dialog.destroy()

        ctk.CTkButton(dialog, text="📄 Word (.docx)", command=lambda: set_format(".docx") if HAS_DOCX else None,
                      state="normal" if HAS_DOCX else "disabled", fg_color="#2b5797").pack(pady=5)
        ctk.CTkButton(dialog, text="📝 Texto (.txt)", command=lambda: set_format(".txt"), fg_color="#444").pack(pady=5)
        ctk.CTkButton(dialog, text="🎬 Subtítulos (.srt)", command=lambda: set_format(".srt"), fg_color="#d68a00").pack(pady=5)
        ctk.CTkButton(dialog, text="📊 Excel/CSV (.csv)", command=lambda: set_format(".csv"), fg_color="#217346").pack(pady=5)

        dialog.wait_window(dialog)
        return self.selected_format

    def auto_save_transcript(self, text_content, audio_path, extension, output_folder=None):
        """
        Guarda la transcripción y devuelve la ruta del archivo.
        Si output_folder tiene valor, guarda allí.
        Si output_folder es None o vacío, guarda junto al audio original.
        Lanza una excepción si no puede guardar (el llamador la muestra).
        """
        if not text_content.strip():
            raise ValueError("la transcripción está vacía (¿el audio no tiene voz?)")

        base_name = os.path.splitext(os.path.basename(audio_path))[0]

        # DECISIÓN DE CARPETA
        if output_folder and os.path.isdir(output_folder):
            # Guardar en carpeta personalizada
            target_folder = output_folder
        else:
            # Guardar junto al original
            target_folder = os.path.dirname(audio_path)

        filename = os.path.join(target_folder, f"{base_name}_Transcribed{extension}")
        write_transcript(filename, extension, text_content, f'Transcripción: {base_name}')
        return filename

    def limpiar_texto(self):
        # 1. Debug: Imprimir en consola para asegurar que el botón reacciona
        print("Botón limpiar pulsado...")

        # 2. Preguntamos directamente, sin comprobar el contenido previo
        confirmar = self.mostrar_confirmacion_oscura(
            "Limpiar Transcripción",
            "¿Estás seguro de que quieres borrar todo el texto?"
        )

        if confirmar:
            # Borramos desde el inicio (1.0 es la primera línea en Tkinter) hasta el final
            self.textbox.delete("1.0", "end")
            self.textbox.insert("1.0", "El texto transcrito aparecerá aquí...\n")

            # Reseteamos las variables internas
            self.transcript_segments = []
            self.unsaved_changes = False
            self.title("OpenTranscribe v2.0")
            print("Texto limpiado correctamente.")

if __name__ == "__main__":
    app = OpenTranscribeApp()
    app.mainloop()
