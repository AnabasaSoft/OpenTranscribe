# OpenTranscribe 🎙️

<p align="center">
  <img src="https://github.com/AnabasaSoft/OpenTranscribe/blob/main/Logo.jpg" alt="OpenTranscribe Logo" width="800">
</p>

Una aplicación de escritorio moderna y oscura para transcribir audio a texto utilizando la potencia de Whisper (C++).

![Captura de pantalla](https://github.com/AnabasaSoft/OpenTranscribe/blob/main/Captura.png)

## Características 🚀
- **Interfaz "Dark Mode"** profesional con CustomTkinter.
- **Transcribe a múltiples formatos:** Word (.docx), CSV, SRT, VTT y TXT.
- **Diarización:** Detección experimental de hablantes.
- **Ligero:** Utiliza `whisper.cpp` para un rendimiento alto y bajo consumo de memoria.
- **Editor Karaoke:** Reproductor integrado que resalta el texto mientras se escucha.

## Requisitos 🛠️
1. Python 3.10+
2. **FFmpeg** instalado en el sistema.
   - Linux: `sudo apt install ffmpeg`
3. **Whisper.cpp** - Motor de transcripción.

## Instalación 📦

### Desde paquetes precompilados

- **Arch Linux (AUR):**
  ```bash
  yay -S opentranscribe
  ```

- **Debian/Ubuntu (.deb):**
  Descarga el paquete desde [Releases](https://github.com/AnabasaSoft/OpenTranscribe/releases) e instala:
  ```bash
  sudo dpkg -i opentranscribe_*.deb
  sudo apt-get install -f
  ```

- **Fedora/RHEL (.rpm):**
  Descarga el paquete desde [Releases](https://github.com/AnabasaSoft/OpenTranscribe/releases) e instala:
  ```bash
  sudo rpm -i opentranscribe_*.rpm
  ```

### Desde el código fuente

1. Clona el repositorio:
   ```bash
   git clone https://github.com/TU_USUARIO/OpenTranscribe.git
   cd OpenTranscribe
   ```

2. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

3. (Opcional) Compila whisper.cpp si no usas el binario predeterminado.

## Uso ▶️

Ejecuta el archivo principal:

```bash
python main.py
```

La aplicación descargará automáticamente los modelos necesarios en tu carpeta de usuario.

## Licencia 📄

MIT License

---

## Contacto 📧

- **Email:** anabasasoft@gmail.com
- **Web:** [anabasasoft.github.io](https://anabasasoft.github.io)

<div align="center">
  <br/>
  <p><code>>_ sudo buy-me-a-coffee --theme=dark --force</code></p>
  <a href="https://www.buymeacoffee.com/danitxu" target="_blank">
    <img src="https://cdn.buymeacoffee.com/buttons/v2/default-black.png" alt="Buy Me A Coffee" style="height: 50px !important;width: 180px !important; box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;">
  </a>
  <br/>
</div>
