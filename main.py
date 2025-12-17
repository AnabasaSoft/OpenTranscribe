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

# Configuración inicial
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class OpenTranscribeApp(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__()

        self.TkdndVersion = TkinterDnD._require(self)
        pygame.mixer.init()

        self.title("OpenTranscribe v2.0 Pro")
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

        self.switch_diarize = ctk.CTkSwitch(self.frame_switches, text="Detectar Hablantes 👥") # <--- NUEVO
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

    def mostrar_confirmacion_oscura(self, titulo, mensaje):
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
        btn_yes = ctk.CTkButton(frame_btns, text="Sí", command=on_yes, fg_color="#8b0000", hover_color="#500000", width=80)
        btn_yes.pack(side="left", padx=10)

        btn_no = ctk.CTkButton(frame_btns, text="No", command=on_no, fg_color="gray", hover_color="#555", width=80)
        btn_no.pack(side="right", padx=10)

        # Bloquear la ventana principal hasta que se responda
        dialog.transient(self)
        dialog.grab_set()
        self.wait_window(dialog)

        return self.respuesta_usuario

    def cancel_transcription(self):
        # Usamos nuestra nueva alerta oscura
        confirm = self.mostrar_confirmacion_oscura("Cancelar", "¿Seguro que quieres detener la transcripción?")

        if confirm:
            transcriber.stop_transcription()
            self.btn_cancel.configure(state="disabled")
            self.btn_process.configure(state="normal", text="Transcribir")
            self.title("OpenTranscribe (Cancelado)")
            self.progress_bar.set(0)
            self.lbl_progress_percent.configure(text="0%")

    def start_transcription(self):
        if not self.selected_file_path: return

        # 1. Recogemos configuración
        srt_mode = self.switch_srt.get() == 1
        diarize_mode = self.switch_diarize.get() == 1
        model_name_ui = self.combo_models.get()

        # 2. VERIFICACIÓN DE MODELO
        exists, filename = transcriber.check_model_exists(model_name_ui)

        if not exists:
            # Preguntar al usuario si quiere descargar
            msg = f"El modelo '{filename}' no está descargado.\n¿Deseas descargarlo ahora? (~50MB - 3GB)"
            resp = self.mostrar_confirmacion_oscura("Modelo Faltante", msg)

            if resp:
                # Iniciar proceso de descarga + transcripción
                self.download_and_transcribe(filename, srt_mode, diarize_mode, model_name_ui)
            return # Si dice que no, no hacemos nada

        # 3. Si existe, procedemos normal
        self.prepare_ui_for_process()
        threading.Thread(target=self.run_process, args=(srt_mode, diarize_mode, model_name_ui), daemon=True).start()

    def prepare_ui_for_process(self):
        self.textbox.delete("0.0", "end")
        self.transcript_segments = []
        self.btn_process.configure(state="disabled", text="Procesando...")
        self.btn_cancel.configure(state="normal")
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)
        self.unsaved_changes = True
        self.title("OpenTranscribe v2.0 Pro * (Trabajando)")

    def download_and_transcribe(self, filename, srt_mode, diarize_mode, model_name_ui):
        self.prepare_ui_for_process()
        self.btn_process.configure(text="Descargando...")
        self.title("OpenTranscribe (Descargando Modelo...)")

        def thread_target():
            try:
                # 1. Descargar
                self.textbox.insert("end", f"Iniciando descarga de {filename}...\n")
                transcriber.download_model(filename, self.update_progress)
                self.textbox.insert("end", "Descarga completada. Iniciando transcripción...\n\n")

                # 2. Transcribir (Ahora que ya existe)
                # Reiniciamos barra para la transcripción
                self.update_progress(0)
                transcriber.run_transcription(
                    self.selected_file_path,
                    model_name_ui,
                    self.update_text_area,
                    self.update_progress,
                    with_timestamps=srt_mode,
                    diarize=diarize_mode
                )
            except Exception as e:
                self.textbox.insert("end", f"\nError en descarga: {e}")
            finally:
                self.after(0, lambda: [self.finish_transcription_ui(), self.sync_timestamps_from_text()])

        threading.Thread(target=thread_target, daemon=True).start()

    def run_process(self, srt_mode, diarize_mode, model_name):
        # ^^^ FÍJATE AQUÍ: Ahora aceptamos 'diarize_mode' entre los paréntesis

        # Llamamos al backend pasándole el nuevo parámetro
        transcriber.run_transcription(
            self.selected_file_path,
            model_name,
            self.update_text_area,
            self.update_progress,
            with_timestamps=srt_mode,
            diarize=diarize_mode # <--- Se lo pasamos a transcriber.py
        )
        self.after(0, lambda: [self.finish_transcription_ui(), self.sync_timestamps_from_text()])

    def finish_transcription_ui(self):
        self.btn_process.configure(state="normal", text="Transcribir")
        self.btn_cancel.configure(state="disabled")
        if "100%" not in self.lbl_progress_percent.cget("text") and not transcriber.is_cancelled:
             self.progress_bar.set(1)
             self.lbl_progress_percent.configure(text="100%")

    def parse_and_insert_line(self, text_line):
        # Limpiamos posibles espacios extra
        clean_line = text_line

        # Detectamos patrón de hablante [SPEAKER_00] o (SPEAKER_00)
        # Regex busca: (cualquier cosa antes)(SPEAKER_XX)(resto del texto)
        pattern = re.compile(r"(.*)(\[SPEAKER_\d+\]|\(SPEAKER_\d+\))(.*)")
        match = pattern.search(clean_line)

        if match:
            # Si encontramos hablante, lo formateamos bonito
            prefix = match.group(1) # Tiempos si los hay
            speaker_tag = match.group(2) # El tag feo
            content = match.group(3) # Lo que dicen

            # Extraemos solo el número
            num = "".join(filter(str.isdigit, speaker_tag))
            formatted_speaker = f" 👤 Hablante {int(num) + 1}: " # +1 para que empiece en 1, no en 0

            # Insertamos el prefijo (tiempos) normal
            self.textbox.insert("end", prefix)

            # Insertamos el hablante con COLOR y NEGRITA (simulada con tags)
            self.textbox.tag_config(f"speaker_{num}", foreground="#4da6ff", font=("Roboto", 14, "bold")) # Azul claro
            self.textbox.insert("end", formatted_speaker, f"speaker_{num}")

            # Insertamos el contenido normal
            self.textbox.insert("end", content + "\n")
        else:
            # Si no hay hablante, insertamos normal
            self.textbox.insert("end", clean_line)

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

    def update_audio_slider_loop(self):
        if self.is_playing and self.total_duration > 0:
            current_time = self.current_offset + (pygame.mixer.music.get_pos() / 1000)
            if current_time > self.total_duration:
                self.stop_audio()
                return
            self.slider_audio.set(current_time / self.total_duration)
            current_str = time.strftime('%M:%S', time.gmtime(int(current_time)))
            total_str = time.strftime('%M:%S', time.gmtime(self.total_duration))
            self.lbl_audio_time.configure(text=f"{current_str} / {total_str}")
            for seg in self.transcript_segments:
                if seg['start'] <= current_time <= seg['end']:
                    self.textbox._textbox.tag_add("highlight", seg['idx_start'], seg['idx_end'])
                else:
                    self.textbox._textbox.tag_remove("highlight", seg['idx_start'], seg['idx_end'])
            self.after(100, self.update_audio_slider_loop)

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
                self.update_audio_slider_loop()
            except Exception as e: print(e)
        else:
            pygame.mixer.music.pause()
            self.is_playing = False
            self.btn_play.configure(text="▶ Reanudar", fg_color="#333")

    def select_file(self):
        filename = ""
        if shutil.which("zenity"):
            try:
                cmd = ["zenity", "--file-selection", "--title=Seleccionar Audio", "--file-filter=Audio | *.mp3 *.wav *.m4a *.mkv *.mp4"]
                filename = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8").strip()
            except subprocess.CalledProcessError: return
        else:
            filename = filedialog.askopenfilename(title="Seleccionar Audio", filetypes=[("Archivos de audio", "*.mp3 *.wav *.m4a")])
        if filename: self.cargar_archivo_comun(filename)

    def al_soltar_archivo(self, event):
        filepath = event.data
        if filepath.startswith("{") and filepath.endswith("}"): filepath = filepath[1:-1]
        self.cargar_archivo_comun(filepath)

    def cargar_archivo_comun(self, filename):
        if not any(filename.lower().endswith(ext) for ext in ['.mp3', '.wav', '.m4a', '.mp4', '.mkv']):
            self.mostrar_alerta_oscura("Error", "Formato no soportado.")
            return
        self.selected_file_path = filename
        self.lbl_filename.configure(text=os.path.basename(filename), text_color="white")
        self.btn_process.configure(state="normal")
        self.progress_bar.set(0)
        self.lbl_progress_percent.configure(text="0%")
        self.load_audio_preview()

    def load_audio_preview(self):
        if self.selected_file_path:
            try:
                self.total_duration = transcriber.get_audio_duration(self.selected_file_path)
                pygame.mixer.music.load(self.selected_file_path)
                self.slider_audio.set(0)
                self.current_offset = 0
                self.is_playing = False
                self.btn_play.configure(state="normal", text="▶ Reproducir", fg_color="#333")
                self.btn_stop.configure(state="normal")
                total_str = time.strftime('%M:%S', time.gmtime(self.total_duration))
                self.lbl_audio_time.configure(text=f"00:00 / {total_str}")
                self.sync_timestamps_from_text()
            except Exception as e:
                print(f"Error cargando audio: {e}")
                self.btn_play.configure(state="disabled")

    def stop_audio(self):
        pygame.mixer.music.stop()
        self.is_playing = False
        self.current_offset = 0
        self.slider_audio.set(0)
        self.textbox._textbox.tag_remove("highlight", "1.0", "end")
        self.btn_play.configure(text="▶ Reproducir", fg_color="#333")
        total_str = time.strftime('%M:%S', time.gmtime(self.total_duration))
        self.lbl_audio_time.configure(text=f"00:00 / {total_str}")

    def seek_audio(self, value):
        if self.total_duration > 0:
            target_time = value * self.total_duration
            self.current_offset = target_time
            pygame.mixer.music.play(start=target_time)
            if not self.is_playing: pygame.mixer.music.pause()
            else:
                self.is_playing = True
                self.btn_play.configure(text="⏸ Pausa", fg_color="#555")
                self.update_audio_slider_loop()

    def update_text_area(self, text):
        self.parse_and_insert_line(text)

    def update_progress(self, progress_float):
        self.after(0, lambda: self._update_progress_gui(progress_float))

    def _update_progress_gui(self, value):
        self.progress_bar.set(value)
        percent_text = f"{int(value * 100)}%"
        self.lbl_progress_percent.configure(text=percent_text)

    def save_text(self):
        # 1. Obtener contenido
        raw_content = self.textbox.get("0.0", "end").strip()
        if not raw_content:
            self.mostrar_alerta_oscura("Error", "No hay texto para guardar.")
            return

        filename = ""

        # 2. INTENTO PRIORITY: Usar Zenity (Mejor integración visual en Linux)
        if shutil.which("zenity"):
            try:
                # Construimos el comando con filtros para que aparezca el desplegable
                cmd = [
                    "zenity", "--file-selection", "--save", "--confirm-overwrite",
                    "--title=Guardar Transcripción",
                    "--filename=Transcripcion.docx" if HAS_DOCX else "Transcripcion.txt"
                ]

                # Añadimos los filtros compatibles
                if HAS_DOCX:
                    cmd.append("--file-filter=Microsoft Word (*.docx) | *.docx")
                cmd.append("--file-filter=Texto Plano (*.txt) | *.txt")
                cmd.append("--file-filter=Subtítulos SRT (*.srt) | *.srt")
                cmd.append("--file-filter=Subtítulos VTT (*.vtt) | *.vtt")
                cmd.append("--file-filter=Excel / CSV (*.csv) | *.csv")

                # Ejecutamos Zenity
                filename = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8").strip()
            except:
                # Si el usuario cancela o falla Zenity, filename se queda vacío
                pass

        # 3. INTENTO SECUNDARIO: Si falló Zenity, usamos el estándar (puede salir blanco)
        if not filename:
            # Solo abrimos este si no se seleccionó nada arriba y no fue una cancelación voluntaria
            # (Simplificación: Si tienes Zenity instalado, usará el de arriba. Si no, este).
            if not shutil.which("zenity"):
                file_types = [
                    ("Texto Plano (*.txt)", "*.txt"),
                    ("Subtítulos SRT (*.srt)", "*.srt"),
                    ("Subtítulos VTT (*.vtt)", "*.vtt"),
                    ("Excel / CSV (*.csv)", "*.csv")
                ]
                if HAS_DOCX:
                    file_types.insert(0, ("Microsoft Word (*.docx)", "*.docx"))

                filename = filedialog.asksaveasfilename(
                    title="Guardar Transcripción",
                    defaultextension=".docx" if HAS_DOCX else ".txt",
                    filetypes=file_types
                )

        if not filename: return

        # 4. Procesar y Guardar (Igual que antes)
        ext = os.path.splitext(filename)[1].lower()

        try:
            # --- PARSEO ---
            lines_data = []
            raw_lines = raw_content.split('\n')
            timestamp_pattern = re.compile(r"\[(\d{2}:\d{2}:\d{2}[\.,]\d{3}) --> (\d{2}:\d{2}:\d{2}[\.,]\d{3})\]")

            current_segment = {"start": "", "end": "", "text": ""}

            for line in raw_lines:
                match = timestamp_pattern.search(line)
                if match:
                    current_segment["start"] = match.group(1).replace(',', '.')
                    current_segment["end"] = match.group(2).replace(',', '.')
                    text_part = timestamp_pattern.sub("", line).strip()
                    current_segment["text"] = text_part
                    lines_data.append(current_segment)
                    current_segment = {"start": "", "end": "", "text": ""}
                else:
                    if line.strip():
                        if current_segment["text"]:
                            current_segment["text"] += " " + line.strip()
                        else:
                            lines_data.append({"start": "", "end": "", "text": line.strip()})

            # --- GUARDADO POR FORMATO ---
            if ext == ".docx" and HAS_DOCX:
                doc = Document()
                doc.add_heading('Transcripción - OpenTranscribe', 0)
                for item in lines_data:
                    p = doc.add_paragraph()
                    if item["start"]:
                        run_time = p.add_run(f"[{item['start']} - {item['end']}] ")
                        run_time.bold = True
                        run_time.font.color.rgb = RGBColor(0, 50, 150)

                    text_content = item["text"]
                    if "👤" in text_content:
                        parts = text_content.split(":", 1)
                        if len(parts) > 1:
                            run_speaker = p.add_run(parts[0] + ":")
                            run_speaker.bold = True
                            run_speaker.font.color.rgb = RGBColor(200, 0, 0)
                            p.add_run(parts[1])
                        else:
                            p.add_run(text_content)
                    else:
                        p.add_run(text_content)
                doc.save(filename)

            elif ext == ".csv":
                with open(filename, mode='w', newline='', encoding='utf-8-sig') as csv_file:
                    writer = csv.writer(csv_file, delimiter=';')
                    writer.writerow(['Inicio', 'Fin', 'Contenido'])
                    for item in lines_data:
                        writer.writerow([item["start"], item["end"], item["text"]])

            elif ext == ".vtt":
                with open(filename, "w", encoding="utf-8") as f:
                    f.write("WEBVTT\n\n")
                    for i, item in enumerate(lines_data):
                        if item["start"]:
                            f.write(f"{i+1}\n")
                            f.write(f"{item['start']} --> {item['end']}\n")
                            f.write(f"{item['text']}\n\n")

            elif ext == ".srt":
                with open(filename, "w", encoding="utf-8") as f:
                    for i, item in enumerate(lines_data):
                        if item["start"]:
                            f.write(f"{i+1}\n")
                            start_srt = item['start'].replace('.', ',')
                            end_srt = item['end'].replace('.', ',')
                            f.write(f"{start_srt} --> {end_srt}\n")
                            f.write(f"{item['text']}\n\n")

            else: # .txt
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(raw_content)

            self.unsaved_changes = False
            self.title("OpenTranscribe v2.0 Pro")
            self.mostrar_alerta_oscura("Guardado", "Archivo guardado exitosamente.")

        except Exception as e:
            self.mostrar_alerta_oscura("Error", str(e))

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
        content = self.textbox.get("0.0", "end")
        if old_text not in content:
            self.mostrar_alerta_oscura("Error", f"No se encontró '{old_text}'", parent_window)
            return
        new_content = content.replace(old_text, new_text)
        self.textbox.delete("0.0", "end")
        self.textbox.insert("0.0", new_content)
        self.mark_as_modified()
        self.sync_timestamps_from_text()
        self.mostrar_alerta_oscura("Éxito", f"Se reemplazó '{old_text}' por '{new_text}'.", parent_window)

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

    def mostrar_confirmacion_oscura(self, titulo, mensaje):
        dialog = ctk.CTkToplevel(self)
        dialog.title(titulo)
        dialog.geometry("350x180")
        dialog.resizable(False, False)
        ctk.CTkLabel(dialog, text=mensaje, font=("Roboto", 14), wraplength=300).pack(pady=30, padx=20)
        frame_btns = ctk.CTkFrame(dialog, fg_color="transparent")
        frame_btns.pack(pady=10)
        self.respuesta_usuario = False
        def on_yes():
            self.respuesta_usuario = True
            dialog.destroy()
        def on_no():
            self.respuesta_usuario = False
            dialog.destroy()
        ctk.CTkButton(frame_btns, text="Sí, salir", command=on_yes, fg_color="red", hover_color="#800000", width=100).pack(side="left", padx=10)
        ctk.CTkButton(frame_btns, text="Cancelar", command=on_no, fg_color="gray", width=100).pack(side="right", padx=10)
        dialog.attributes("-topmost", True)
        dialog.update()
        try: dialog.grab_set()
        except: pass
        self.wait_window(dialog)
        return self.respuesta_usuario

    def mark_as_modified(self, event=None):
        keys_to_ignore = ["Control_L", "Control_R", "Alt_L", "Shift_L", "Up", "Down", "Left", "Right"]
        if event and event.keysym in keys_to_ignore: return
        if not self.unsaved_changes:
            self.unsaved_changes = True
            self.title("OpenTranscribe * (Sin guardar)")

    def on_closing(self):
        if self.unsaved_changes:
            # Usamos nuestra nueva alerta oscura
            salir = self.mostrar_confirmacion_oscura("Salir", "Tienes cambios sin guardar.\n¿Estás seguro de que quieres salir?")
            if salir:
                try: pygame.mixer.quit()
                except: pass
                self.destroy()
        else:
            try: pygame.mixer.quit()
            except: pass
            self.destroy()

    def abrir_ayuda(self):
        # Crear ventana emergente
        ayuda_window = ctk.CTkToplevel(self)
        ayuda_window.title("Ayuda - OpenTranscribe")
        ayuda_window.geometry("400x550")
        ayuda_window.resizable(False, False)
        ayuda_window.attributes("-topmost", True)

        # Logo
        try:
            if os.path.exists("Logo.jpg"):
                img_data = Image.open("Logo.jpg")
                logo_img = ctk.CTkImage(light_image=img_data, dark_image=img_data, size=(120, 120)) # Reduje un poco el logo
                lbl_img = ctk.CTkLabel(ayuda_window, text="", image=logo_img)
                lbl_img.pack(pady=(15, 5))
        except Exception: pass

        # Título
        ctk.CTkLabel(ayuda_window, text="Guía Rápida", font=("Roboto Medium", 18)).pack(pady=5)

        # Texto explicativo
        texto_ayuda = (
            "1. Selecciona o arrastra un archivo de audio.\n"
            "2. Elige el Modelo y pulsa 'Transcribir'.\n\n"
            "Usa el reproductor para corregir.\n"
            "El botón 'Sincronizar' ajusta los tiempos.\n"
        )
        ctk.CTkLabel(ayuda_window, text=texto_ayuda, wraplength=350).pack(pady=5, padx=20)

        # Separador
        ctk.CTkFrame(ayuda_window, height=2, fg_color="gray").pack(fill="x", padx=40, pady=10)

        # --- SECCIÓN CONTACTO CLICABLE ---
        ctk.CTkLabel(ayuda_window, text="Soporte y Contacto:", font=("Roboto", 12, "bold")).pack(pady=(5, 0))

        # 1. Email Clicable
        lbl_mail = ctk.CTkLabel(ayuda_window, text="anabasasoft@gmail.com", text_color="#4da6ff", cursor="hand2")
        lbl_mail.pack(pady=2)
        lbl_mail.bind("<Button-1>", lambda e: webbrowser.open("mailto:anabasasoft@gmail.com"))

        # 2. Web Clicable
        lbl_web = ctk.CTkLabel(ayuda_window, text="anabasasoft.github.io", text_color="#4da6ff", cursor="hand2")
        lbl_web.pack(pady=2)
        lbl_web.bind("<Button-1>", lambda e: webbrowser.open("https://anabasasoft.github.io"))

        # Botón cerrar
        ctk.CTkButton(ayuda_window, text="Entendido", command=ayuda_window.destroy, width=100).pack(pady=20)

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

if __name__ == "__main__":
    app = OpenTranscribeApp()
    app.mainloop()
