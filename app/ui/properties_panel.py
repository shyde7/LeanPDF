"""Right-side panel: shows properties for the selected text overlay or highlight."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..models.app_state import AppState
from ..models.highlight_overlay import HighlightOverlay
from ..models.text_overlay import TextOverlay
from .pdf_canvas import HIGHLIGHT_COLORS


class PropertiesPanel(QWidget):
    # text overlay signals
    overlay_changed = Signal(str)
    overlay_deleted = Signal(str)
    # highlight signals
    highlight_color_changed = Signal(str)   # highlight id
    highlight_deleted = Signal(str)         # highlight id

    def __init__(self, state: AppState, parent=None) -> None:
        super().__init__(parent)
        self.state = state
        self._current_overlay: Optional[TextOverlay] = None
        self._current_highlight: Optional[HighlightOverlay] = None
        self._building = False

        self.setMinimumWidth(220)
        self.setMaximumWidth(300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.title = QLabel("Properties")
        self.title.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.title)

        # --- empty state ---
        self.empty_label = QLabel("Select a text overlay or highlight to edit its properties.")
        self.empty_label.setWordWrap(True)
        self.empty_label.setStyleSheet("color: #666;")
        layout.addWidget(self.empty_label)

        # --- text overlay section ---
        self.overlay_widget = QWidget()
        form = QFormLayout(self.overlay_widget)
        form.setContentsMargins(0, 0, 0, 0)

        self.text_edit = QLineEdit()
        self.text_edit.editingFinished.connect(self._commit_text)
        form.addRow("Text:", self.text_edit)

        self.size_spin = QDoubleSpinBox()
        self.size_spin.setRange(4.0, 144.0)
        self.size_spin.setSingleStep(1.0)
        self.size_spin.setDecimals(1)
        self.size_spin.valueChanged.connect(self._commit_size)
        form.addRow("Font size:", self.size_spin)

        self.color_btn = QPushButton("Choose color")
        self.color_btn.clicked.connect(self._choose_overlay_color)
        form.addRow("Color:", self.color_btn)

        self.bold_check = QCheckBox("Bold")
        self.bold_check.toggled.connect(self._commit_bold)
        form.addRow("", self.bold_check)

        self.overlay_delete_btn = QPushButton("Delete Overlay")
        self.overlay_delete_btn.clicked.connect(self._on_delete_overlay)
        form.addRow("", self.overlay_delete_btn)

        layout.addWidget(self.overlay_widget)

        # --- highlight section ---
        self.highlight_widget = QWidget()
        hl_layout = QVBoxLayout(self.highlight_widget)
        hl_layout.setContentsMargins(0, 0, 0, 0)
        hl_layout.setSpacing(6)

        hl_layout.addWidget(QLabel("Highlight color:"))

        preset_row = QHBoxLayout()
        preset_row.setSpacing(4)
        self._preset_btns = []
        for name, color in HIGHLIGHT_COLORS:
            btn = QPushButton()
            btn.setFixedSize(28, 28)
            btn.setToolTip(name)
            rc, gc, bc = color
            qc = QColor(int(rc * 255), int(gc * 255), int(bc * 255))
            btn.setStyleSheet(
                f"background-color: {qc.name()}; border: 1px solid #999; border-radius: 4px;"
            )
            btn.clicked.connect(lambda checked, c=color: self._set_hl_color(c))
            preset_row.addWidget(btn)
            self._preset_btns.append(btn)
        preset_row.addStretch(1)
        hl_layout.addLayout(preset_row)

        self.hl_custom_btn = QPushButton("Custom color…")
        self.hl_custom_btn.clicked.connect(self._choose_hl_color)
        hl_layout.addWidget(self.hl_custom_btn)

        self.hl_delete_btn = QPushButton("Delete Highlight")
        self.hl_delete_btn.clicked.connect(self._on_delete_highlight)
        hl_layout.addWidget(self.hl_delete_btn)

        layout.addWidget(self.highlight_widget)

        layout.addStretch(1)

        # start with both hidden
        self.overlay_widget.hide()
        self.highlight_widget.hide()

    # ---- public -----------------------------------------------------------

    def show_overlay(self, overlay: Optional[TextOverlay]) -> None:
        self._current_overlay = overlay
        self._current_highlight = None
        self.highlight_widget.hide()
        if overlay is None:
            self.overlay_widget.hide()
            self.empty_label.show()
            return
        self.empty_label.hide()
        self.overlay_widget.show()
        self._building = True
        self.text_edit.setText(overlay.text)
        self.size_spin.setValue(overlay.font_size)
        self.bold_check.setChecked(overlay.bold)
        self._update_overlay_color_button(overlay.color)
        self._building = False

    def show_highlight(self, highlight: Optional[HighlightOverlay]) -> None:
        self._current_highlight = highlight
        self._current_overlay = None
        self.overlay_widget.hide()
        if highlight is None:
            self.highlight_widget.hide()
            self.empty_label.show()
            return
        self.empty_label.hide()
        self.highlight_widget.show()

    def set_state(self, state: AppState) -> None:
        self.state = state
        self.show_overlay(None)

    def clear(self) -> None:
        self.show_overlay(None)

    # ---- overlay internals -----------------------------------------------

    def _update_overlay_color_button(self, color_tuple) -> None:
        r, g, b = color_tuple
        qc = QColor(int(r * 255), int(g * 255), int(b * 255))
        self.color_btn.setStyleSheet(
            f"background-color: {qc.name()}; "
            f"color: {'white' if qc.lightness() < 128 else 'black'};"
        )
        self.color_btn.setText(qc.name())

    def _commit_text(self) -> None:
        if self._building or self._current_overlay is None:
            return
        new = self.text_edit.text()
        if new != self._current_overlay.text:
            self._current_overlay.text = new
            self.state.dirty = True
            self.overlay_changed.emit(self._current_overlay.id)

    def _commit_size(self, value: float) -> None:
        if self._building or self._current_overlay is None:
            return
        self._current_overlay.font_size = float(value)
        self.state.dirty = True
        self.overlay_changed.emit(self._current_overlay.id)

    def _commit_bold(self, checked: bool) -> None:
        if self._building or self._current_overlay is None:
            return
        self._current_overlay.bold = checked
        self.state.dirty = True
        self.overlay_changed.emit(self._current_overlay.id)

    def _choose_overlay_color(self) -> None:
        if self._current_overlay is None:
            return
        r, g, b = self._current_overlay.color
        initial = QColor(int(r * 255), int(g * 255), int(b * 255))
        chosen = QColorDialog.getColor(initial, self, "Text Color")
        if not chosen.isValid():
            return
        self._current_overlay.color = (chosen.redF(), chosen.greenF(), chosen.blueF())
        self.state.dirty = True
        self._update_overlay_color_button(self._current_overlay.color)
        self.overlay_changed.emit(self._current_overlay.id)

    def _on_delete_overlay(self) -> None:
        if self._current_overlay is None:
            return
        oid = self._current_overlay.id
        self.show_overlay(None)
        self.overlay_deleted.emit(oid)

    # ---- highlight internals ---------------------------------------------

    def _set_hl_color(self, color: tuple) -> None:
        if self._current_highlight is None:
            return
        self._current_highlight.color = tuple(color)
        self.state.dirty = True
        self.highlight_color_changed.emit(self._current_highlight.id)

    def _choose_hl_color(self) -> None:
        if self._current_highlight is None:
            return
        r, g, b = self._current_highlight.color
        initial = QColor(int(r * 255), int(g * 255), int(b * 255))
        chosen = QColorDialog.getColor(initial, self, "Highlight Color")
        if not chosen.isValid():
            return
        self._current_highlight.color = (chosen.redF(), chosen.greenF(), chosen.blueF())
        self.state.dirty = True
        self.highlight_color_changed.emit(self._current_highlight.id)

    def _on_delete_highlight(self) -> None:
        if self._current_highlight is None:
            return
        hid = self._current_highlight.id
        self.show_highlight(None)
        self.highlight_deleted.emit(hid)
