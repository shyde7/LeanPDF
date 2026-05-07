# LeanPDF

A lightweight, no-bloat desktop PDF manipulator. The Acrobat features you actually use, nothing else.

## What it does (MVP)

- Open and view PDFs with a thumbnail sidebar and zoomable page view.
- Place new text overlays on pages, drag them, change font size and color, and flatten them on save.
- Delete pages.
- Merge additional PDFs into the current document.
- Save / Save As.

## What it does NOT do (by design)

- Edit existing PDF text in place. Text editing means *placing new text overlays* that get flattened on save.
- No accounts, no cloud sync, no telemetry, no OCR, no AI, no e-signatures, no comments.

## Stack

- Python 3.11+
- PySide6 (Qt) for the GUI
- PyMuPDF (`pymupdf`) for PDF rendering and editing
- pytest for tests
- PyInstaller for packaging

## Install

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Run

From the project root (`leanpdf/`):

```bash
python -m app.main
```

## Test

```bash
pytest
```

Tests build tiny PDFs in temp directories using PyMuPDF — they don't depend on any external files.

## Build (PyInstaller)

The provided `build.py` defaults to a one-folder build (faster startup, easier to debug):

```bash
pip install pyinstaller
python build.py
```

Output appears in `dist/LeanPDF/`. Run `dist/LeanPDF/LeanPDF` (or `LeanPDF.exe` on Windows).

For a single-file build (slower startup, simpler distribution):

```bash
python build.py --onefile
```

Use `--clean` to wipe `dist/` and `build/` first.

## Architecture

```
app/
  main.py                  # entry point
  core/
    pdf_document.py        # PyMuPDF wrapper (open, render, edit, save)
    render_cache.py        # LRU cache for rendered pages/thumbnails
    coordinate_mapper.py   # screen ↔ PDF coordinate conversion
    operations.py          # higher-level state-aware ops
  models/
    text_overlay.py        # TextOverlay dataclass
    app_state.py           # in-memory app state
  ui/
    main_window.py         # toolbar, layout, action wiring
    pdf_canvas.py          # QGraphicsView page + draggable overlays
    thumbnail_sidebar.py   # left thumbnail list
    properties_panel.py    # right text-overlay property editor
    dialogs.py             # confirm / info / error / save-discard-cancel
  services/
    file_service.py        # path validation
    export_service.py      # flatten overlays + save
tests/                     # pytest suite
build.py                   # PyInstaller build helper
```

User-facing page numbers are 1-based; internal page indexes are 0-based throughout.

## Future features (post-MVP)

- Reorder pages via drag-and-drop in the sidebar.
- Merge ordering dialog.
- Bold/italic styling and font picker.
- Image stamps and signatures.
- Highlight / strikethrough annotation tools.
- Find / search text.
- Persist overlays as PDF annotations (instead of flatten-only).
- Undo/redo history.
