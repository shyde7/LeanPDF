"""Left sidebar showing page thumbnails."""
from __future__ import annotations

from typing import List

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QImage, QPixmap, QAction
from PySide6.QtWidgets import QAbstractItemView, QListWidget, QListWidgetItem, QMenu

from ..core.pdf_document import PDFDocument


class ThumbnailSidebar(QListWidget):
    page_selected = Signal(int)               # primary page for canvas view
    delete_requested = Signal(list)           # list[int] — with confirm dialog
    delete_requested_silent = Signal(list)    # list[int] — no confirm (Backspace)
    page_reordered = Signal(int, int)         # (from_index, to_index)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setIconSize(QSize(140, 180))
        self.setUniformItemSizes(False)
        self.setSpacing(4)
        self.setMinimumWidth(180)
        self.setMaximumWidth(220)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self.currentRowChanged.connect(self._on_row_changed)
        self._drag_source_row: int = -1

    def rebuild(self, doc: PDFDocument, selected: int = 0) -> None:
        self.blockSignals(True)
        self.clear()
        if not doc.is_open:
            self.blockSignals(False)
            return
        for i in range(doc.page_count()):
            item = QListWidgetItem(f"Page {i + 1}")
            try:
                img = doc.render_thumbnail(i)
                qimg = QImage(
                    img.samples,
                    img.width,
                    img.height,
                    img.stride,
                    QImage.Format_RGB888,
                ).copy()
                item.setIcon(QPixmap.fromImage(qimg))
            except Exception:
                pass
            item.setTextAlignment(Qt.AlignCenter)
            self.addItem(item)
        if 0 <= selected < self.count():
            self.setCurrentRow(selected)
        self.blockSignals(False)

    def select_page(self, index: int) -> None:
        if 0 <= index < self.count() and self.currentRow() != index:
            self.setCurrentRow(index)

    def selected_indices(self) -> List[int]:
        return sorted(self.row(item) for item in self.selectedItems())

    def _on_row_changed(self, row: int) -> None:
        if row >= 0:
            self.page_selected.emit(row)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Backspace, Qt.Key_Delete):
            indices = self.selected_indices()
            if indices:
                self.delete_requested_silent.emit(indices)
                return
        super().keyPressEvent(event)

    def startDrag(self, supported_actions) -> None:
        self._drag_source_row = self.currentRow()
        super().startDrag(supported_actions)

    def dropEvent(self, event) -> None:
        super().dropEvent(event)
        dest_row = self.currentRow()
        if self._drag_source_row >= 0 and dest_row != self._drag_source_row:
            self.page_reordered.emit(self._drag_source_row, dest_row)
        self._drag_source_row = -1

    def _on_context_menu(self, pos) -> None:
        item = self.itemAt(pos)
        if item is None:
            return
        indices = self.selected_indices()
        if not indices:
            indices = [self.row(item)]
        label = f"Delete {len(indices)} Page{'s' if len(indices) != 1 else ''}"
        menu = QMenu(self)
        action = QAction(label, menu)
        action.triggered.connect(lambda: self.delete_requested.emit(indices))
        menu.addAction(action)
        menu.exec(self.mapToGlobal(pos))
