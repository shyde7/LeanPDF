"""Higher-level operations that coordinate PDFDocument with AppState."""
from __future__ import annotations

from typing import Sequence

from ..models.app_state import AppState
from ..models.text_overlay import TextOverlay
from .pdf_document import PDFDocument


def add_text_overlay(state: AppState, overlay: TextOverlay) -> None:
    state.overlays.append(overlay)
    state.selected_overlay_id = overlay.id
    state.dirty = True


def update_overlay(state: AppState, overlay_id: str, **fields) -> None:
    ov = state.find_overlay(overlay_id)
    if ov is None:
        return
    for k, v in fields.items():
        if hasattr(ov, k):
            setattr(ov, k, v)
    state.dirty = True


def delete_overlay(state: AppState, overlay_id: str) -> None:
    state.remove_overlay(overlay_id)
    state.dirty = True


def delete_page(doc: PDFDocument, state: AppState, page_index: int) -> None:
    doc.delete_page(page_index)
    state.reindex_after_page_delete(page_index)
    new_count = doc.page_count()
    if state.selected_page_index >= new_count:
        state.selected_page_index = max(0, new_count - 1)
    elif state.selected_page_index > page_index:
        state.selected_page_index -= 1
    state.dirty = True


def move_page(doc: PDFDocument, state: AppState, from_idx: int, to_idx: int) -> None:
    if from_idx == to_idx:
        return
    doc.move_page(from_idx, to_idx)
    state.reindex_after_page_move(from_idx, to_idx)
    if state.selected_page_index == from_idx:
        state.selected_page_index = to_idx
    elif from_idx < to_idx and from_idx < state.selected_page_index <= to_idx:
        state.selected_page_index -= 1
    elif from_idx > to_idx and to_idx <= state.selected_page_index < from_idx:
        state.selected_page_index += 1
    state.dirty = True


def merge_pdfs(doc: PDFDocument, state: AppState, paths: Sequence[str]) -> None:
    if not paths:
        return
    if doc.is_open:
        doc.merge_pdfs(paths)
    else:
        doc.open_from_paths_as_new(paths)
        state.current_file_path = None
        state.selected_page_index = 0
    state.dirty = True
