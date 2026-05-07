"""Snapshot-based undo/redo stack.

Each entry stores the PDF bytes and enough AppState to fully restore the
session.  Overlay mutations (drag, type, color) are not individually tracked —
only structural changes (page delete/move/merge, overlay add/remove) push a
snapshot.  This keeps memory usage bounded and avoids per-keystroke entries.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, TYPE_CHECKING

import pymupdf

from ..models.highlight_overlay import HighlightOverlay
from ..models.text_overlay import TextOverlay

if TYPE_CHECKING:
    from ..core.pdf_document import PDFDocument
    from ..models.app_state import AppState

MAX_HISTORY = 30


@dataclass
class _Snapshot:
    doc_bytes: bytes
    file_path: Optional[str]
    selected_page_index: int
    overlays: List[dict]
    highlights: List[dict]


class UndoStack:
    def __init__(self) -> None:
        self._undo: List[_Snapshot] = []
        self._redo: List[_Snapshot] = []

    # ---- public API ---------------------------------------------------

    def push(self, doc: "PDFDocument", state: "AppState") -> None:
        """Capture current state; call this BEFORE a mutating operation."""
        self._undo.append(self._capture(doc, state))
        if len(self._undo) > MAX_HISTORY:
            self._undo.pop(0)
        self._redo.clear()

    def undo(self, doc: "PDFDocument", state: "AppState") -> bool:
        if not self._undo:
            return False
        self._redo.append(self._capture(doc, state))
        self._restore(self._undo.pop(), doc, state)
        return True

    def redo(self, doc: "PDFDocument", state: "AppState") -> bool:
        if not self._redo:
            return False
        self._undo.append(self._capture(doc, state))
        self._restore(self._redo.pop(), doc, state)
        return True

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

    # ---- internals ----------------------------------------------------

    def _capture(self, doc: "PDFDocument", state: "AppState") -> _Snapshot:
        return _Snapshot(
            doc_bytes=doc.snapshot_bytes(),
            file_path=state.current_file_path,
            selected_page_index=state.selected_page_index,
            overlays=[o.to_dict() for o in state.overlays],
            highlights=[h.to_dict() for h in state.highlights],
        )

    def _restore(self, snap: _Snapshot, doc: "PDFDocument", state: "AppState") -> None:
        doc.restore_from_bytes(snap.doc_bytes, snap.file_path)
        page_count = doc.page_count()
        state.current_file_path = snap.file_path
        state.selected_page_index = min(snap.selected_page_index, max(0, page_count - 1))
        state.overlays = [TextOverlay.from_dict(d) for d in snap.overlays]
        state.selected_overlay_id = None
        state.highlights = [HighlightOverlay.from_dict(d) for d in snap.highlights]
        state.selected_highlight_id = None
        state.dirty = True
