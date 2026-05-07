"""Final export: flatten overlays, write PDF, reset overlay state."""
from __future__ import annotations

from ..core.pdf_document import PDFDocument
from ..models.app_state import AppState
from .file_service import is_writable_target


class ExportError(Exception):
    pass


def export_pdf(doc: PDFDocument, state: AppState, path: str) -> None:
    if not doc.is_open:
        raise ExportError("No document is open")
    if not is_writable_target(path):
        raise ExportError(f"Cannot write to: {path}")

    if state.overlays:
        doc.apply_text_overlays(state.overlays)

    if state.highlights:
        doc.apply_highlights(state.highlights)

    doc.save_as(path)

    state.overlays.clear()
    state.selected_overlay_id = None
    state.highlights.clear()
    state.selected_highlight_id = None
    state.current_file_path = path
    state.dirty = False
