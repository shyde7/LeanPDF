# LeanPDF

> PDFs are simple. The tools aren't.

---

Adobe Acrobat costs $240 a year. It takes 30 seconds to launch. It phones home. It nags you to sign in. It bundles features nobody asked for and hides the ones you actually need behind paywalls, tooltips, and modal dialogs.

All you wanted to do was add some text to a page. Delete a page. Merge two files. That's it.

**LeanPDF exists because that should be free, fast, and offline.**

No subscription. No account. No cloud. No telemetry. No AI. No "Pro" tier. Just a PDF editor that opens instantly, does what you need, and gets out of your way.

---

## What it does

| Feature | Details |
|---|---|
| **View** | Open any PDF with a zoomable page canvas and thumbnail sidebar |
| **Text overlays** | Click to place text anywhere on a page — drag, resize, change font/size/color/bold |
| **Highlight** | Drag to select words and highlight them in any color |
| **Delete pages** | Single page or multi-select from the sidebar |
| **Merge** | Append one or more PDFs into your current document |
| **Reorder pages** | Drag thumbnails in the sidebar to rearrange |
| **Save / Save As** | Overlays are flattened into the PDF on save |
| **Undo / Redo** | Full snapshot-based history for structural changes |
| **Zoom** | Preset steps from 50% to 300%, or Ctrl+scroll |

## What it deliberately does not do

- Edit existing embedded PDF text in-place — that way lies madness and licensing fees
- Accounts, cloud sync, or telemetry of any kind
- OCR, AI, e-signatures, form filling, redaction, comments
- Anything that requires a subscription to unlock

---

## Stack

| | |
|---|---|
| **Language** | Python 3.11+ |
| **GUI** | PySide6 (Qt6) |
| **PDF engine** | PyMuPDF (`pymupdf`) |
| **Tests** | pytest |
| **Packaging** | PyInstaller |

---

## Getting started

### Install

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### Run

```bash
python -m app.main
```

### Test

```bash
pytest
```

Tests generate real PDFs in temp directories using PyMuPDF — no fixtures or external files required.

### Build a standalone executable

```bash
pip install pyinstaller

# One-folder build (faster startup, easier to debug)
python build.py

# Single-file build (simpler to distribute, slower to launch)
python build.py --onefile

# Wipe dist/ and build/ before building
python build.py --clean
```

Output lands in `dist/LeanPDF/`. On Windows, run `dist/LeanPDF/LeanPDF.exe`.

---

## Architecture

```
app/
  main.py                  # entry point — QApplication bootstrap
  core/
    pdf_document.py        # PyMuPDF wrapper: open, render, edit, save
    render_cache.py        # LRU cache for rendered pages and thumbnails
    coordinate_mapper.py   # screen <-> PDF coordinate conversion
    operations.py          # state-aware ops: delete/move/merge pages, overlays
    text_layer.py          # word extraction and hit-testing for the highlight tool
    undo_stack.py          # snapshot-based undo/redo (PDF bytes + serialized state)
  models/
    text_overlay.py        # TextOverlay dataclass
    highlight_overlay.py   # HighlightOverlay dataclass
    app_state.py           # in-memory application state
  ui/
    main_window.py         # toolbar, layout wiring, all action handlers
    pdf_canvas.py          # QGraphicsView: page rendering, draggable overlays, highlights
    thumbnail_sidebar.py   # drag-reorderable page thumbnail list
    properties_panel.py    # text and highlight property editor (right panel)
    dialogs.py             # confirm / info / error / save-discard-cancel helpers
  services/
    file_service.py        # path validation, PDF magic-byte check
    export_service.py      # flatten overlays into PDF and write to disk
tests/                     # pytest suite — headless, no Qt required
build.py                   # PyInstaller build helper
```

**Coordinate convention:** page numbers are 1-based in the UI, 0-based everywhere internally. PyMuPDF uses a top-left origin with y increasing downward — same as screen space, so no Y-flip is needed.

---

## Roadmap

- [ ] Font picker and italic support
- [ ] Image stamps and signature blocks
- [ ] Find / search text
- [ ] Persist overlays as PDF annotations instead of flattening on save
- [ ] Merge ordering dialog
- [ ] Strikethrough annotation tool
