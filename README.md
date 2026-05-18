# SViewG

SVG viewer with syntax-highlighted source view, bidirectional element selection, zoom/pan, and minimap.

## Features

- Split view: syntax-highlighted SVG source ↔ interactive renderer
- Bidirectional selection — click element in viewer or code to highlight both
- Hover highlights in both panels
- Code folding, zoom (scroll/keyboard), pan, minimap
- Drag & drop SVG files, "Open With…" on macOS
- Persistent settings, DE/EN UI (extensible via `lang/` JSON files)

## Requirements

Python 3.9+, PyQt6

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python main.py [file.svg]
```

## Build

```bash
pyinstaller SViewG.spec --noconfirm
# → dist/SViewG.app (macOS) / dist/SViewG/ (Windows, Linux)
```

Releases are built automatically via GitHub Actions on every `v*` tag.

## Add a language

Drop a `lang/lang_xx.json` into `lang/` — no code changes needed. See `lang/lang_en.json` for the required keys.
