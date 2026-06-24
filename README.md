<div align="center">

# 🧼 MetaScrub

### Your photo. Your edit. Your work. — minus the metadata that mislabels it as AI.

**For photographers.** You took the shot and retouched it with AI tools — it's still *your* photograph. But your editor embeds **C2PA / IPTC / XMP / EXIF** provenance tags, and platforms like Instagram read them and stamp your post *"Made with AI."* MetaScrub removes those tags — **losslessly, entirely on your machine** — so your own work isn't misrepresented.

[![License: MIT](https://img.shields.io/badge/License-MIT-7c6bff.svg)](LICENSE)
![Platform](https://img.shields.io/badge/platform-macOS%20·%20Linux%20·%20Windows-111)
![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)
![No tracking](https://img.shields.io/badge/network-100%25%20offline-43e09b)
![Lossless](https://img.shields.io/badge/quality-lossless-43e09b)

<img src="docs/screenshot.png" alt="MetaScrub dark UI" width="640">

</div>

---

## Why this exists

You photograph a client, then use an AI tool (Photoshop Generative Fill, Lightroom AI, Topaz, ChatGPT…) to retouch the shot — fix a stray hair, smooth skin, clean the background. The result is still **your** photograph: your subject, your composition, your work. But the moment an AI tool touches the file it writes a signed **C2PA manifest** and an IPTC `digitalSourceType: trainedAlgorithmicMedia` tag. Instagram, Facebook and others read that metadata and stamp your post *"Made with AI"* — even when the edit was trivial.

That label misrepresents genuine photography as synthetic. **MetaScrub removes the metadata** so your own photos are judged as what they are — losslessly, on your own machine, nothing uploaded.

## ✅ Intended use — and the line it won't cross

MetaScrub is for **cleaning false AI‑labels off photographs you actually took and retouched.** Your camera captured the moment; an AI tool helped you edit it; the work is yours.

It is **not** for passing **fully AI‑generated images** — text‑to‑image pictures invented from a prompt, with no camera involved — off as authentic photography. Removing metadata doesn't make a synthetic image real, and where a platform or law requires AI disclosure, **disclose it.** Be honest about what you made.

## ✨ Features

- 🖱️ **Friendly drag‑and‑drop app** — add many photos at once, watch them clean in real time
- 🪶 **Lossless** — JPEG pixels are never re‑encoded; PNG/WebP are re‑encoded losslessly (pixels identical)
- 🧾 **Before/after report** — see exactly which tags were removed on every image
- 🔒 **100% offline** — a tiny local web server; your photos never leave your computer
- 🗂️ **Originals are never touched** — cleaned copies are written to a separate `out/` folder
- ⌨️ **CLI included** — script the same engine for batch jobs
- 🧰 Removes: **C2PA / JUMBF manifests**, **IPTC DigitalSourceType**, **XMP**, **EXIF**, software/author tags

## 📸 Supported formats

`JPG` · `JPEG` · `PNG` · `WebP` · `HEIC` · `TIFF` · `GIF`

## 🚀 Quick start

### Requirements

Runs anywhere with **Python 3.9+** (standard library only — no pip packages) plus [ExifTool](https://exiftool.org/) and [ImageMagick](https://imagemagick.org/):

| OS | Install the two tools |
|----|-----------------------|
| **macOS** | `brew install exiftool imagemagick` |
| **Linux** (Debian/Ubuntu) | `sudo apt install libimage-exiftool-perl imagemagick` |
| **Windows** | `winget install OliverBetz.ExifTool ImageMagick.ImageMagick` |

### Run the app

```bash
git clone https://github.com/adrozdenko/metascrub.git
cd metascrub
python3 server.py        # Windows: py server.py
```

It starts a tiny local server and opens the UI in your browser. Drag photos in, download the clean versions. Done.

> **macOS shortcut:** double‑click **`Photo Cleaner.command`** in Finder instead of using the terminal.

### Use the CLI

```bash
./clean.sh                 # clean every image in ./in  -> ./out
./clean.sh ~/Photos        # clean a whole folder       -> ./out
./clean.sh a.jpg b.png     # clean specific files       -> ./out
```

Each run prints a per‑file before/after report.

## 🔍 How it works

| Format | Method | Quality |
|--------|--------|---------|
| **JPEG / HEIC** | `exiftool -all=` — strips every metadata block, pixels untouched | 🟢 Lossless (no re‑encode) |
| **PNG / WebP / TIFF** | `magick … -strip` re‑encode (drops C2PA chunks) + `exiftool -all=` | 🟢 Lossless (pixels identical) |

The app exposes a minimal local HTTP server (`server.py`, stdlib only). The browser posts each image's bytes to `/clean`; the server runs the tools above, writes a clean copy to `out/`, and returns the result for preview and download. No frameworks, no telemetry, no cloud.

## ⚠️ What this can — and can't — do (read this)

MetaScrub removes **metadata**, which is the signal platforms use for the automatic AI‑label. It does **not** remove **pixel‑level invisible watermarks** such as Google **SynthID** or **Trufo**, which some *generative* tools (OpenAI's `gpt-image`, Google's Imagen/Gemini) bake directly into the pixels. Those survive metadata removal, re‑encoding, cropping and compression by design.

> **Tip for photographers:** to keep your retouched photo unambiguously *yours*, prefer **non‑generative editors** (Lightroom, Capture One, Photoshop manual retouching, Topaz) over tools that *regenerate* the image. Pixel‑editing your own photograph adds no watermark and no `trainedAlgorithmicMedia` tag in the first place — and the result is plainly your own work, not a synthetic rebuild of it.

## 🗂️ Project structure

```
metascrub/
├── Photo Cleaner.command   # double‑click launcher (macOS)
├── server.py               # local web server + cleaning engine (stdlib only)
├── index.html              # the UI (dark theme)
├── clean.sh                # CLI batch cleaner
├── in/                     # drop photos here (CLI) — git‑ignored
└── out/                    # cleaned copies land here — git‑ignored
```

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md). Ideas: Windows/Linux launchers, a native menu‑bar build, video metadata support, watermark‑detection reporting.

## 📄 License

[MIT](LICENSE) © 2026 Andrii Drozdenko
