🌐 [English](README.md) · [Español](README.es.md) · **Euskara**

# OpenTranscribe 🎙️

<p align="center">
  <img src="Logo.jpg" alt="OpenTranscribe logoa" width="800"/>
</p>

<p align="center">
  <strong>Transkribatu audioa eta bideoa testura zure ordenagailuan bertan, konexiorik gabe eta hodeira ezer bidali gabe, Whisper-en (C++) indarrarekin.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/License-GPL%20v3-blue.svg" alt="License">
  <img src="https://img.shields.io/badge/Platform-Linux-lightgrey.svg" alt="Platform">
  <img src="https://img.shields.io/badge/Motorra-whisper.cpp-success.svg" alt="whisper.cpp">
  <img src="https://img.shields.io/badge/Pribatutasuna-%25100%20lokala-orange.svg" alt="%100 lokala">
</p>

<p align="center">
  <img src="Captura.png" alt="Pantaila-argazkia"/>
</p>

---

## 🚀 Ezaugarriak

- **%100 lokala:** audioa ez da inoiz zure ordenagailutik ateratzen. Internet lehen aldiz ereduak deskargatzeko eta abiaraztean bertsio berririk dagoen egiaztatzeko baino ez da erabiltzen (Laguntzan desaktiba daiteke).
- **Eguneraketa-abisuak:** bertsio berri bat argitaratzean, aplikazioak adierazten du, deskargarako estekarekin.
- **Audioa eta bideoa:** MP3, WAV, M4A, MP4, MKV, MOV, AVI, WEBM eta FLV. Ez dago audioa aldez aurretik atera beharrik.
- **Hainbat eredu:** *Tiny*-tik (oso azkarra) *Large*-ra (zehaztasun handiena). Behar direnean automatikoki deskargatzen dira.
- **Hainbat formatutara esportatzea:** Word (.docx), CSV, SRT, VTT eta TXT.
- **Ilara modua:** arrastatu hainbat fitxategi batera, eta bata bestearen atzetik transkribatu eta gordetzen dira automatikoki.
- **Hiztunak kanalaren arabera:** pertsona bakoitza kanal batean duten grabazio estereoetan (deiak, podcastak), nork hitz egiten duen identifikatzen du (ezkerra = 1. hiztuna, eskuina = 2. hiztuna).
- **Karaoke editorea:** testua entzun ahala nabarmentzen duen erreproduzitzaile integratua.
- **Bilatu eta ordeztu** transkripzioa gorde aurretik zuzentzeko.
- **Interfaze iluna** CustomTkinter-ekin, fitxategiak arrastatu eta jaregiteko aukerarekin.

> Interfazea gaztelaniaz dago oraingoz; behean botoien izenak aplikazioan agertzen diren bezala aipatzen dira, eta ondoren euskarazko esanahia.

---

## 🛠️ Betekizunak

- **Linux x86-64**, AVX2rekin bateragarria den prozesadore batekin (ia edozein, 2013-2015etik aurrera).
- **FFmpeg** sisteman instalatuta:
  - Debian/Ubuntu: `sudo apt install ffmpeg`
  - Fedora: `sudo dnf install ffmpeg` (RPM Fusion-etik)
  - openSUSE: `sudo zypper install ffmpeg` (biltegi ofizialetakoa nahikoa da)
- Iturburu-kodetik exekutatzeko: **Python 3.10+**, `git`, `cmake` eta `g++`.

---

## 📦 Instalazioa

### Aurrez konpilatutako paketeetatik

Deskargatu paketea [Releases](https://github.com/AnabasaSoft/OpenTranscribe/releases) orritik:

- **Debian/Ubuntu (.deb):**
  ```bash
  sudo apt install ./OpenTranscribe-linux-x64.deb
  ```

- **Fedora (.rpm):**
  ```bash
  sudo dnf install ./OpenTranscribe-linux-x64.rpm
  ```

- **openSUSE Tumbleweed / Leap (.rpm):**
  ```bash
  sudo zypper install ./OpenTranscribe-linux-x64.rpm
  ```
  Biltegi ofizialetako FFmpeg-a nahikoa da: OpenTranscribe-k audioa irakurri baino ez du behar, eta FFmpeg horrek AAC, MP3, Opus, Vorbis edo FLAC deskodetzen ditu, baita MP4 edo MKV bideoen barruan ere. Ez da Packman behar.

- **AppImage (edozein banaketa, instalatu gabe):**
  ```bash
  chmod +x OpenTranscribe-x86_64.AppImage
  ./OpenTranscribe-x86_64.AppImage
  ```
  Edozein banaketatan dabilen fitxategi bakarra. **FFmpeg** instalatuta izatea baino ez du behar.
  Zure sistemak FUSE ez badu (ez da ohikoa mahaigainetan), exekutatu `./OpenTranscribe-x86_64.AppImage --appimage-extract-and-run` erabiliz.

- **Karpeta konprimitua (instalatu gabe):**
  ```bash
  tar xzf OpenTranscribe-linux-x64.tar.gz
  ./OpenTranscribe/OpenTranscribe
  ```

Paketeek glibc 2.35 edo berriagoa duten banaketetan funtzionatzen dute (Ubuntu 22.04, Debian 12, Fedora 36, openSUSE Leap 15.6 edo berriagoak).

### Iturburu-kodetik

1. Klonatu biltegia:
   ```bash
   git clone https://github.com/AnabasaSoft/OpenTranscribe.git
   cd OpenTranscribe
   ```

2. Instalatu mendekotasunak:
   ```bash
   pip install -r requirements.txt
   ```

3. Konpilatu transkripzio-motorra:
   ```bash
   ./build_whisper.sh
   ```
   `binaries_linux/whisper-cli` sortzen du whisper.cpp-tik abiatuta.

---

## ▶️ Erabilera

```bash
python main.py
```

1. Arrastatu audio- edo bideo-fitxategi bat leihora (edo sakatu **📂 Seleccionar Audio** — Audioa hautatu).
2. Aukeratu **AA eredua**. *Base* abiaduraren eta zehaztasunaren arteko oreka ona da.
3. Aktibatu **Modo Subtítulos** (Azpititulu modua) denbora-markak nahi badituzu (SRT/VTTrako eta karaokerako beharrezkoak).
4. Sakatu **TRANSCRIBIR** (Transkribatu) eta, amaitzean, **💾 Guardar Texto** (Testua gorde).

**Hainbat fitxategi** arrastatzen badituzu, ilara modua aktibatzen da: formatua eta helburuko karpeta behin aukeratzen dituzu, eta transkripzio bakoitza automatikoki gordetzen da.

Ereduak `~/.OpenTranscribe/models/` karpetan gordetzen dira.

---

## 📄 Lizentzia

Proiektu hau **GNU General Public License v3.0 (GPL-3.0)** lizentziapean dago.
Ikusi `LICENSE` fitxategia testu osoa irakurtzeko.

Copyright (C) 2025-2026 AnabasaSoft

### Zer esan nahi du praktikan

- ✅ OpenTranscribe libreki **erabil** dezakezu, baita zure enpresan eta helburu komertzialekin ere
- ✅ Kodea **aztertu, aldatu eta birbanatu** dezakezu
- ⚠️ Bertsio aldatu bat banatzen baduzu, **GPL-3.0 lizentziapean ere** argitaratu behar duzu eta haren iturburu-kodea eskuragarri jarri
- ⚠️ Copyright eta lizentzia oharrak mantendu behar dituzu

### Lizentzia-oharra

Ohar ofiziala ingelesez dago (ikusi [README.md](README.md)); hau haren itzulpen informatiboa da:

```
OpenTranscribe - Audio eta bideoaren transkripzio lokala
Copyright (C) 2025-2026 AnabasaSoft

Programa hau software librea da: birbanatu eta/edo aldatu dezakezu Free
Software Foundation-ek argitaratutako GNUren Lizentzia Publiko Orokorraren
baldintzen arabera, Lizentziaren 3. bertsioa edo (zuk hala nahi baduzu)
ondorengo edozein bertsio erabiliz.

Programa hau erabilgarria izango delakoan banatzen da, baina INOLAKO
BERMERIK GABE; ezta MERKATURATZEKO edo HELBURU JAKIN BATERAKO EGOKITASUNAREN
berme inplizitua ere. Xehetasun gehiagorako, ikusi GNUren Lizentzia
Publiko Orokorra.

Programa honekin batera GNUren Lizentzia Publiko Orokorraren kopia bat
jaso beharko zenuke. Hala ez bada, ikusi <https://www.gnu.org/licenses/>.
```

> **Lizentzia komertzialei buruzko oharra**: AnabasaSoft da OpenTranscribe-ren
> copyrightaren titular bakarra, eta, beraz, kode bera GPLren desberdinak
> diren baldintzetan eskain dezake. OpenTranscribe produktu jabedun batean
> integratu behar baduzu, jarri harremanetan.

---

## 📧 Harremana

**AnabasaSoft**

- 📧 Posta elektronikoa: [anabasasoft@gmail.com](mailto:anabasasoft@gmail.com)
- 🌐 GitHub: [github.com/AnabasaSoft](https://github.com/AnabasaSoft)
- 💼 Proiektua: [github.com/AnabasaSoft/OpenTranscribe](https://github.com/AnabasaSoft/OpenTranscribe)

---

## 🙏 Eskerrak

- [whisper.cpp](https://github.com/ggml-org/whisper.cpp): OpenAI-ren Whisper-en oinarritutako C/C++ transkripzio-motorra
- [FFmpeg](https://ffmpeg.org/): audioa eta bideoa bihurtzea eta irakurtzea
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter): Tkinter-en gaineko interfaze grafiko modernoa
- [tkinterdnd2](https://github.com/Eliav2/tkinterdnd2): fitxategiak arrastatu eta jaregitea
- [pygame](https://www.pygame.org/): audioaren erreprodukzioa karaoke modurako
- [python-docx](https://github.com/python-openxml/python-docx): Wordera esportatzea
- [Pillow](https://python-pillow.org/): irudien tratamendua
- Kode irekiko komunitatea, bere babes eta ekarpenengatik

---

<div align="center">

<img src="https://raw.githubusercontent.com/AnabasaSoft/MantPro/main/AnabasaSoft.png" alt="Anabasa Software" width="120"/>

**[Anabasa Software](https://anabasasoft.github.io)-k ❤️-z garatua**

📧 Posta elektronikoa: [anabasasoft@gmail.com](mailto:anabasasoft@gmail.com) • 🌐 Portfolioa: [anabasasoft.github.io](https://anabasasoft.github.io)

⭐ Proiektu hau gustatzen bazaizu, eman izar bat GitHub-en

</div>

<div align="center">
  <br/>
  <p><code>>_ sudo buy-me-a-coffee --theme=dark --force</code></p>
  <a href="https://www.buymeacoffee.com/danitxu" target="_blank">
    <img src="https://cdn.buymeacoffee.com/buttons/v2/default-black.png" alt="Buy Me A Coffee" style="height: 50px !important;width: 180px !important; box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;-webkit-box-shadow: 0px 3px 2px 0px rgba(190, 190, 190, 0.5) !important;">
  </a>
  <br/>
</div>
