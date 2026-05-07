"""Main application window."""
from __future__ import annotations

import os
from typing import List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon, QKeySequence

_ICON_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "leadpdf_icon.svg")
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStatusBar,
    QToolBar,
    QWidget,
)

from ..core import operations
from ..core.pdf_document import EncryptedPDFError, PDFDocument, PDFDocumentError
from ..core.undo_stack import UndoStack
from ..models.app_state import AppState
from ..services.export_service import ExportError, export_pdf
from ..services.file_service import looks_like_pdf
from .dialogs import confirm, error, info, save_discard_cancel
from .pdf_canvas import PDFCanvas
from .properties_panel import PropertiesPanel
from .thumbnail_sidebar import ThumbnailSidebar


ZOOM_STEPS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LeanPDF")
        self.resize(1200, 800)
        if os.path.exists(_ICON_PATH):
            self.setWindowIcon(QIcon(_ICON_PATH))

        self.doc = PDFDocument()
        self.state = AppState()
        self.undo_stack = UndoStack()

        self._build_central()
        self._build_toolbar()
        self._build_statusbar()
        self._connect_signals()
        self._refresh_actions()
        self._update_title()

    # ---- layout -------------------------------------------------------

    def _build_central(self) -> None:
        central = QWidget(self)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = ThumbnailSidebar(self)
        self.canvas = PDFCanvas(self.doc, self.state, self)
        self.props = PropertiesPanel(self.state, self)

        layout.addWidget(self.sidebar)
        layout.addWidget(self.canvas, 1)
        layout.addWidget(self.props)

        self.setCentralWidget(central)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main", self)
        tb.setMovable(False)
        self.addToolBar(tb)

        self.act_open = QAction("Open", self)
        self.act_open.setShortcut(QKeySequence.Open)
        self.act_open.triggered.connect(self.action_open)
        tb.addAction(self.act_open)

        self.act_save = QAction("Save", self)
        self.act_save.setShortcut(QKeySequence.Save)
        self.act_save.triggered.connect(self.action_save)
        tb.addAction(self.act_save)

        self.act_save_as = QAction("Save As", self)
        self.act_save_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.act_save_as.triggered.connect(self.action_save_as)
        tb.addAction(self.act_save_as)

        tb.addSeparator()

        self.act_undo = QAction("Undo", self)
        self.act_undo.setShortcut(QKeySequence.Undo)
        self.act_undo.triggered.connect(self.action_undo)
        tb.addAction(self.act_undo)

        self.act_redo = QAction("Redo", self)
        self.act_redo.setShortcut(QKeySequence.Redo)
        self.act_redo.triggered.connect(self.action_redo)
        tb.addAction(self.act_redo)

        tb.addSeparator()

        self.act_add_text = QAction("Add Text", self)
        self.act_add_text.setCheckable(True)
        self.act_add_text.toggled.connect(self.action_toggle_add_text)
        tb.addAction(self.act_add_text)

        self.act_highlight = QAction("Highlight", self)
        self.act_highlight.setCheckable(True)
        self.act_highlight.toggled.connect(self.action_toggle_highlight)
        tb.addAction(self.act_highlight)

        self.act_delete = QAction("Delete Page", self)
        self.act_delete.triggered.connect(self.action_delete_page)
        tb.addAction(self.act_delete)

        self.act_merge = QAction("Merge PDFs", self)
        self.act_merge.triggered.connect(self.action_merge)
        tb.addAction(self.act_merge)

        tb.addSeparator()

        self.act_zoom_in = QAction("Zoom In", self)
        self.act_zoom_in.setShortcut(QKeySequence.ZoomIn)
        self.act_zoom_in.triggered.connect(self.action_zoom_in)
        tb.addAction(self.act_zoom_in)

        self.act_zoom_out = QAction("Zoom Out", self)
        self.act_zoom_out.setShortcut(QKeySequence.ZoomOut)
        self.act_zoom_out.triggered.connect(self.action_zoom_out)
        tb.addAction(self.act_zoom_out)

    def _build_statusbar(self) -> None:
        sb = QStatusBar(self)
        self.setStatusBar(sb)
        self.page_label = QLabel("")
        sb.addPermanentWidget(self.page_label)

    def _connect_signals(self) -> None:
        self.sidebar.page_selected.connect(self.on_page_selected)
        self.sidebar.delete_requested.connect(self.action_delete_pages)
        self.sidebar.delete_requested_silent.connect(lambda idx: self.action_delete_pages(idx, skip_confirm=True))
        self.sidebar.page_reordered.connect(self.on_page_reordered)
        self.canvas.pre_overlay_create.connect(self._push_undo)
        self.canvas.overlay_created.connect(self.on_overlay_created)
        self.canvas.overlay_selected.connect(self.on_overlay_selected)
        self.canvas.overlay_text_changed.connect(self.on_overlay_text_changed)
        self.canvas.pre_highlight_create.connect(self._push_undo)
        self.canvas.highlight_created.connect(self.on_highlight_created)
        self.canvas.highlight_selected.connect(self.on_highlight_selected)
        self.canvas.highlight_delete_requested.connect(self.on_highlight_delete_requested)
        self.canvas.zoom_requested.connect(self._step_zoom)
        self.props.overlay_changed.connect(self.on_overlay_changed_in_panel)
        self.props.overlay_deleted.connect(self.on_overlay_deleted_in_panel)
        self.props.highlight_color_changed.connect(self.on_highlight_color_changed)
        self.props.highlight_deleted.connect(self.on_highlight_delete_requested)

    # ---- top-level actions -------------------------------------------

    def action_open(self) -> None:
        if not self._confirm_discard_if_dirty():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF Files (*.pdf)")
        if not path:
            return
        if not looks_like_pdf(path):
            error(self, "Open PDF", "That file does not look like a PDF.")
            return
        try:
            self.doc.open(path)
        except EncryptedPDFError:
            error(self, "Open PDF", "This PDF is password-protected and cannot be opened.")
            return
        except PDFDocumentError as exc:
            error(self, "Open PDF", str(exc))
            return
        self.state.current_file_path = path
        self.state.selected_page_index = 0
        self.state.zoom = 1.0
        self.state.overlays.clear()
        self.state.selected_overlay_id = None
        self.state.highlights.clear()
        self.state.selected_highlight_id = None
        self.state.dirty = False
        self.undo_stack.clear()
        # Reset tool mode — unchecking a checked button fires the toggle handler
        # which resets state.active_tool and the cursor.
        self.act_add_text.setChecked(False)
        self.act_highlight.setChecked(False)
        self._post_doc_change()

    def action_save(self) -> None:
        if not self.doc.is_open:
            return
        if not self.state.current_file_path:
            self.action_save_as()
            return
        self._do_export(self.state.current_file_path)

    def action_save_as(self) -> None:
        if not self.doc.is_open:
            return
        suggested = self.state.current_file_path or "untitled.pdf"
        path, _ = QFileDialog.getSaveFileName(self, "Save PDF As", suggested, "PDF Files (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        self._do_export(path)

    def action_toggle_add_text(self, on: bool) -> None:
        if on:
            self.act_highlight.setChecked(False)
            self.state.active_tool = "add_text"
            self.canvas.setCursor(Qt.CrossCursor)
        else:
            self.state.active_tool = "select"
            self.canvas.setCursor(Qt.ArrowCursor)

    def action_toggle_highlight(self, on: bool) -> None:
        if on:
            self.act_add_text.setChecked(False)
            self.state.active_tool = "highlight"
            self.canvas.setCursor(Qt.CrossCursor)
        else:
            self.state.active_tool = "select"
            self.canvas.setCursor(Qt.ArrowCursor)

    def action_delete_page(self) -> None:
        if not self.doc.is_open:
            return
        indices = self.sidebar.selected_indices()
        if not indices:
            indices = [self.state.selected_page_index]
        self.action_delete_pages(indices)

    def action_delete_pages(self, page_indices: list, skip_confirm: bool = False) -> None:
        if not self.doc.is_open:
            return
        indices = sorted(set(page_indices))
        indices = [i for i in indices if 0 <= i < self.doc.page_count()]
        if not indices:
            return
        if self.doc.page_count() - len(indices) < 1:
            error(self, "Delete Page", "Cannot delete all remaining pages.")
            return
        if not skip_confirm:
            if len(indices) == 1:
                msg = f"Delete page {indices[0] + 1}?"
            else:
                labels = ", ".join(str(i + 1) for i in indices)
                msg = f"Delete pages {labels}?"
            if not confirm(self, "Delete Page", msg):
                return
        self._push_undo()
        # Delete highest index first so lower indices stay valid.
        for page_index in sorted(indices, reverse=True):
            try:
                operations.delete_page(self.doc, self.state, page_index)
            except PDFDocumentError as exc:
                error(self, "Delete Page", str(exc))
                break
        self._post_doc_change()

    def action_merge(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Merge PDFs", "", "PDF Files (*.pdf)")
        if not paths:
            return
        bad = [p for p in paths if not looks_like_pdf(p)]
        if bad:
            error(self, "Merge PDFs", f"Not a PDF: {bad[0]}")
            return
        self._push_undo()
        try:
            operations.merge_pdfs(self.doc, self.state, paths)
        except EncryptedPDFError as exc:
            error(self, "Merge PDFs", str(exc))
            self._post_doc_change()  # reflect any pages inserted before the failure
            return
        except PDFDocumentError as exc:
            error(self, "Merge PDFs", str(exc))
            self._post_doc_change()
            return
        self._post_doc_change()

    def action_undo(self) -> None:
        if not self.undo_stack.can_undo():
            return
        self.undo_stack.undo(self.doc, self.state)
        self._post_doc_change()

    def action_redo(self) -> None:
        if not self.undo_stack.can_redo():
            return
        self.undo_stack.redo(self.doc, self.state)
        self._post_doc_change()

    def action_zoom_in(self) -> None:
        self._step_zoom(+1)

    def action_zoom_out(self) -> None:
        self._step_zoom(-1)

    def _step_zoom(self, direction: int) -> None:
        if not self.doc.is_open:
            return
        try:
            idx = ZOOM_STEPS.index(self.state.zoom)
        except ValueError:
            idx = min(range(len(ZOOM_STEPS)), key=lambda i: abs(ZOOM_STEPS[i] - self.state.zoom))
        new_idx = max(0, min(len(ZOOM_STEPS) - 1, idx + direction))
        new_zoom = ZOOM_STEPS[new_idx]
        if new_zoom == self.state.zoom:
            return
        self.state.zoom = new_zoom
        self.canvas.render_current_page()
        self._refresh_status()

    # ---- handlers -----------------------------------------------------

    def on_page_selected(self, index: int) -> None:
        if index == self.state.selected_page_index:
            return
        self.state.selected_page_index = index
        self.state.selected_overlay_id = None
        self.canvas.render_current_page()
        self.props.show_overlay(None)
        self._refresh_status()

    def on_page_reordered(self, from_idx: int, to_idx: int) -> None:
        if not self.doc.is_open:
            return
        self._push_undo()
        try:
            operations.move_page(self.doc, self.state, from_idx, to_idx)
        except Exception as exc:
            error(self, "Reorder Pages", str(exc))
            # Rebuild to restore visual order to match doc state.
            self._post_doc_change()
            return
        # Rebuild the sidebar so thumbnail images match the new page order.
        self.sidebar.rebuild(self.doc, self.state.selected_page_index)
        self.canvas.render_current_page()
        self._refresh_actions()
        self._refresh_status()
        self._update_title()

    def on_overlay_created(self, overlay_id: str) -> None:
        ov = self.state.find_overlay(overlay_id)
        self.props.show_overlay(ov)
        # After placement, switch back to selection so user can immediately edit.
        self.act_add_text.setChecked(False)

    def on_overlay_selected(self, overlay_id: str) -> None:
        self.state.selected_overlay_id = overlay_id
        self.props.show_overlay(self.state.find_overlay(overlay_id))

    def on_overlay_text_changed(self, overlay_id: str) -> None:
        if self.state.selected_overlay_id == overlay_id:
            self.props.show_overlay(self.state.find_overlay(overlay_id))

    def on_overlay_changed_in_panel(self, overlay_id: str) -> None:
        self.canvas.refresh_selected_overlay_style()
        self._update_title()

    def on_overlay_deleted_in_panel(self, overlay_id: str) -> None:
        self._push_undo()
        operations.delete_overlay(self.state, overlay_id)
        self.canvas.remove_overlay_visual(overlay_id)
        self._refresh_undo_actions()
        self._update_title()

    def on_highlight_created(self, highlight_id: str) -> None:
        hl = self.state.find_highlight(highlight_id)
        self.props.show_highlight(hl)
        self.act_highlight.setChecked(False)  # revert to select mode after placement
        self._refresh_undo_actions()
        self._update_title()

    def on_highlight_selected(self, highlight_id: str) -> None:
        self.state.selected_highlight_id = highlight_id
        self.state.selected_overlay_id = None
        self.props.show_highlight(self.state.find_highlight(highlight_id))

    def on_highlight_color_changed(self, highlight_id: str) -> None:
        self.canvas.refresh_highlight_visual(highlight_id)
        self._update_title()

    def on_highlight_delete_requested(self, highlight_id: str) -> None:
        self._push_undo()
        self.state.remove_highlight(highlight_id)
        self.canvas.remove_highlight_visual(highlight_id)
        self.props.show_highlight(None)
        self._refresh_undo_actions()
        self._update_title()

    # ---- shared post-change refresh ----------------------------------

    def _post_doc_change(self) -> None:
        if self.doc.is_open:
            self.sidebar.rebuild(self.doc, self.state.selected_page_index)
            self.canvas.render_current_page()
        else:
            self.sidebar.rebuild(self.doc, 0)
            self.canvas.show_empty()
        self.props.show_overlay(None)
        self._refresh_actions()
        self._refresh_status()
        self._update_title()

    def _push_undo(self) -> None:
        if self.doc.is_open:
            self.undo_stack.push(self.doc, self.state)
            self._refresh_undo_actions()

    def _refresh_undo_actions(self) -> None:
        self.act_undo.setEnabled(self.undo_stack.can_undo())
        self.act_redo.setEnabled(self.undo_stack.can_redo())

    def _refresh_actions(self) -> None:
        is_open = self.doc.is_open
        self.act_save.setEnabled(is_open)
        self.act_save_as.setEnabled(is_open)
        self.act_add_text.setEnabled(is_open)
        self.act_highlight.setEnabled(is_open)
        self.act_delete.setEnabled(is_open and self.doc.page_count() > 1)
        self.act_merge.setEnabled(True)  # always enabled: works with or without an open doc
        self.act_zoom_in.setEnabled(is_open)
        self.act_zoom_out.setEnabled(is_open)
        self._refresh_undo_actions()

    def _refresh_status(self) -> None:
        if not self.doc.is_open:
            self.page_label.setText("")
            return
        self.page_label.setText(
            f"Page {self.state.selected_page_index + 1} / {self.doc.page_count()}  •  "
            f"{int(self.state.zoom * 100)}%"
        )

    def _update_title(self) -> None:
        name = self.state.current_file_path or "Untitled"
        dirty = "*" if self.state.dirty else ""
        self.setWindowTitle(f"LeanPDF — {name}{dirty}")

    # ---- save flow ----------------------------------------------------

    def _do_export(self, path: str) -> None:
        try:
            export_pdf(self.doc, self.state, path)
        except ExportError as exc:
            error(self, "Save PDF", str(exc))
            return
        except PDFDocumentError as exc:
            error(self, "Save PDF", str(exc))
            return
        self._post_doc_change()
        info(self, "Save PDF", f"Saved to {path}")

    def _confirm_discard_if_dirty(self) -> bool:
        if not self.state.dirty:
            return True
        choice = save_discard_cancel(self, "Unsaved changes", "Save changes before continuing?")
        if choice == "save":
            self.action_save()
            return not self.state.dirty
        if choice == "discard":
            return True
        return False

    # ---- close --------------------------------------------------------

    def closeEvent(self, event) -> None:
        if not self._confirm_discard_if_dirty():
            event.ignore()
            return
        self.doc.close()
        event.accept()
