"""Center canvas: renders the current page and hosts draggable text overlays
and text highlight overlays.

Overlay interaction model
--------------------------
Text overlays use a two-item stack:
  _OverlayItem  (QGraphicsObject)  — outer drag container  (z = 10)
      └── _TextChild (QGraphicsTextItem) — inner text editor

Highlights use a single item:
  _HighlightItem (QGraphicsItem)  — semi-transparent rects   (z = 5)
  Selection-preview rects live at z = 6 and are temporary.

Tool modes
----------
  "select"    — normal Qt scene interaction (click to select items)
  "add_text"  — click page to place a text overlay
  "highlight" — drag across page to select words; release to place highlight
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
)

from ..core.coordinate_mapper import CoordinateMapper
from ..core.pdf_document import PDFDocument
from ..core.text_layer import extract_words, select_words, words_to_line_rects
from ..models.app_state import AppState
from ..models.highlight_overlay import HighlightOverlay
from ..models.text_overlay import TextOverlay

_DRAG_PADDING = 12  # extra grab area (px) around text overlay items

# Preset highlight colors (name, RGB 0–1 floats)
HIGHLIGHT_COLORS: List[Tuple[str, Tuple[float, float, float]]] = [
    ("Yellow",  (1.0,  0.92, 0.0)),
    ("Green",   (0.55, 0.93, 0.55)),
    ("Pink",    (1.0,  0.60, 0.80)),
    ("Blue",    (0.53, 0.81, 1.0)),
    ("Orange",  (1.0,  0.72, 0.30)),
]


# ---------------------------------------------------------------------------
# Text overlay — inner editing child
# ---------------------------------------------------------------------------

class _TextChild(QGraphicsTextItem):
    """Text editor zone inside an _OverlayItem.  Never moves independently."""

    def __init__(self, parent_item: "_OverlayItem") -> None:
        super().__init__(parent=parent_item)
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.ItemIsSelectable, False)
        self.setTextInteractionFlags(Qt.TextEditorInteraction)
        self.setAcceptHoverEvents(True)

    def hoverEnterEvent(self, event) -> None:
        self.setCursor(Qt.IBeamCursor)
        event.accept()

    def hoverLeaveEvent(self, event) -> None:
        self.unsetCursor()
        event.accept()

    def mousePressEvent(self, event) -> None:
        parent = self.parentItem()
        if parent is not None:
            scene = parent.scene()
            if scene:
                scene.clearSelection()
            parent.setSelected(True)
        super().mousePressEvent(event)

    def focusOutEvent(self, event) -> None:
        parent = self.parentItem()
        if parent is not None:
            overlay = parent.overlay
            canvas = parent._canvas
            new_text = self.toPlainText()
            if new_text != overlay.text:
                overlay.text = new_text
                canvas.state.dirty = True
                canvas.overlay_text_changed.emit(overlay.id)
        super().focusOutEvent(event)


# ---------------------------------------------------------------------------
# Text overlay — outer drag container
# ---------------------------------------------------------------------------

class _OverlayItem(QGraphicsObject):
    """Drag container for a text overlay.  Local origin == text top-left."""

    def __init__(self, overlay: TextOverlay, canvas: "PDFCanvas") -> None:
        super().__init__()
        self.overlay = overlay
        self._canvas = canvas

        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

        self._text = _TextChild(self)
        self._text.setPlainText(overlay.text)
        self._text.document().contentsChanged.connect(self._on_contents_changed)
        self._apply_style()

    def refresh_style(self) -> None:
        self._apply_style()

    def boundingRect(self) -> QRectF:
        tr = self._text.boundingRect()
        return QRectF(
            -_DRAG_PADDING, -_DRAG_PADDING,
            tr.width() + 2 * _DRAG_PADDING,
            tr.height() + 2 * _DRAG_PADDING,
        )

    def paint(self, painter: QPainter, option, widget=None) -> None:
        if self.isSelected():
            painter.save()
            painter.setPen(QPen(QColor("#4a90d9"), 1, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(self.boundingRect().adjusted(0.5, 0.5, -0.5, -0.5))
            painter.restore()

    def hoverEnterEvent(self, event) -> None:
        self.setCursor(Qt.OpenHandCursor)
        event.accept()

    def hoverLeaveEvent(self, event) -> None:
        self.unsetCursor()
        event.accept()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self._canvas.mapper is not None:
            mapper = self._canvas.mapper
            px, py = mapper.screen_to_pdf(value.x(), value.y())
            px, py = mapper.clamp_pdf(px, py)
            self.overlay.x_pdf, self.overlay.y_pdf = px, py
            sx, sy = mapper.pdf_to_screen(px, py)
            return QPointF(sx, sy)
        if change == QGraphicsItem.ItemSelectedHasChanged and bool(value):
            self._canvas.state.selected_overlay_id = self.overlay.id
            self._canvas.state.selected_highlight_id = None
            self._canvas.overlay_selected.emit(self.overlay.id)
        return super().itemChange(change, value)

    def _apply_style(self) -> None:
        font = QFont()
        font.setPointSizeF(self.overlay.font_size * self._canvas.state.zoom)
        font.setBold(self.overlay.bold)
        self._text.setFont(font)
        r, g, b = self.overlay.color
        self._text.setDefaultTextColor(QColor(int(r * 255), int(g * 255), int(b * 255)))
        if self._text.toPlainText() != self.overlay.text:
            self._text.setPlainText(self.overlay.text)
        self._on_contents_changed()

    def _on_contents_changed(self) -> None:
        self.prepareGeometryChange()
        self.update()


# ---------------------------------------------------------------------------
# Highlight item
# ---------------------------------------------------------------------------

class _HighlightItem(QGraphicsItem):
    """Renders a highlight annotation as semi-transparent filled rects."""

    def __init__(
        self,
        hl: HighlightOverlay,
        canvas: "PDFCanvas",
        mapper: CoordinateMapper,
    ) -> None:
        super().__init__()
        self.hl = hl
        self._canvas = canvas
        self._screen_rects: List[QRectF] = []
        self._build_rects(mapper)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(5)

    def _build_rects(self, mapper: CoordinateMapper) -> None:
        self._screen_rects = []
        for r in self.hl.rects:
            sx0, sy0 = mapper.pdf_to_screen(r[0], r[1])
            sx1, sy1 = mapper.pdf_to_screen(r[2], r[3])
            self._screen_rects.append(QRectF(sx0, sy0, sx1 - sx0, sy1 - sy0))

    def boundingRect(self) -> QRectF:
        if not self._screen_rects:
            return QRectF()
        r = self._screen_rects[0]
        for rect in self._screen_rects[1:]:
            r = r.united(rect)
        return r.adjusted(-1, -1, 1, 1)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        for r in self._screen_rects:
            path.addRect(r)
        return path

    def paint(self, painter: QPainter, option, widget=None) -> None:
        rc, gc, bc = self.hl.color
        fill = QColor(int(rc * 255), int(gc * 255), int(bc * 255), 110)
        painter.setBrush(QBrush(fill))
        if self.isSelected():
            painter.setPen(QPen(QColor("#e07000"), 1.5, Qt.DashLine))
        else:
            painter.setPen(Qt.NoPen)
        for r in self._screen_rects:
            painter.drawRect(r)

    def hoverEnterEvent(self, event) -> None:
        self.setCursor(Qt.PointingHandCursor)
        event.accept()

    def hoverLeaveEvent(self, event) -> None:
        self.unsetCursor()
        event.accept()

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedHasChanged and bool(value):
            self._canvas.state.selected_highlight_id = self.hl.id
            self._canvas.state.selected_overlay_id = None
            self._canvas.highlight_selected.emit(self.hl.id)
        return super().itemChange(change, value)


# ---------------------------------------------------------------------------
# Canvas
# ---------------------------------------------------------------------------

class PDFCanvas(QGraphicsView):
    # text overlay signals
    overlay_selected = Signal(str)
    overlay_text_changed = Signal(str)
    pre_overlay_create = Signal()
    overlay_created = Signal(str)
    # highlight signals
    pre_highlight_create = Signal()
    highlight_created = Signal(str)
    highlight_selected = Signal(str)
    highlight_delete_requested = Signal(str)
    # zoom
    zoom_requested = Signal(int)        # +1 = in, -1 = out
    page_clicked_empty = Signal()

    def __init__(self, doc: PDFDocument, state: AppState, parent=None) -> None:
        super().__init__(parent)
        self.doc = doc
        self.state = state
        self.mapper: Optional[CoordinateMapper] = None
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHints(QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)
        self.setBackgroundBrush(QBrush(QColor("#e6e6e6")))
        self.setAlignment(Qt.AlignCenter)
        self._page_item: Optional[QGraphicsPixmapItem] = None
        self._page_border: Optional[QGraphicsRectItem] = None
        self._overlay_items: Dict[str, _OverlayItem] = {}
        self._highlight_items: Dict[str, _HighlightItem] = {}
        # highlight drag state
        self._hl_anchor: Optional[Tuple[float, float]] = None
        self._hl_preview: List[QGraphicsRectItem] = []
        self._show_placeholder()

    # ---- public API -------------------------------------------------------

    def show_empty(self) -> None:
        self._scene.clear()
        self._page_item = None
        self._page_border = None
        self._overlay_items.clear()
        self._highlight_items.clear()
        self._hl_anchor = None
        self._hl_preview.clear()
        self.mapper = None
        self._show_placeholder()

    def render_current_page(self) -> None:
        if not self.doc.is_open:
            self.show_empty()
            return
        page_index = self.state.selected_page_index
        try:
            img = self.doc.render_page(page_index, self.state.zoom)
        except Exception:
            self.show_empty()
            return

        self._scene.clear()
        self._overlay_items.clear()
        self._highlight_items.clear()
        self._hl_preview.clear()
        self._hl_anchor = None

        qimg = QImage(
            img.samples, img.width, img.height, img.stride, QImage.Format_RGB888
        ).copy()
        pixmap = QPixmap.fromImage(qimg)
        self._page_item = self._scene.addPixmap(pixmap)
        self._page_item.setZValue(0)
        self._page_border = self._scene.addRect(
            QRectF(0, 0, img.width, img.height),
            QPen(QColor("#bbbbbb")),
        )
        self._page_border.setZValue(1)
        self._scene.setSceneRect(QRectF(0, 0, img.width, img.height))
        self.mapper = CoordinateMapper(
            page_width_pdf=img.page_width_pdf,
            page_height_pdf=img.page_height_pdf,
            zoom=self.state.zoom,
        )
        for hl in self.state.highlights_on_page(page_index):
            self._add_highlight_item(hl)
        for ov in self.state.overlays_on_page(page_index):
            self._add_overlay_item(ov)

        if self.state.selected_overlay_id in self._overlay_items:
            self._overlay_items[self.state.selected_overlay_id].setSelected(True)
        if self.state.selected_highlight_id in self._highlight_items:
            self._highlight_items[self.state.selected_highlight_id].setSelected(True)

    def refresh_selected_overlay_style(self) -> None:
        sid = self.state.selected_overlay_id
        if sid and sid in self._overlay_items:
            self._overlay_items[sid].refresh_style()

    def remove_overlay_visual(self, overlay_id: str) -> None:
        item = self._overlay_items.pop(overlay_id, None)
        if item is not None:
            self._scene.removeItem(item)

    def remove_highlight_visual(self, highlight_id: str) -> None:
        item = self._highlight_items.pop(highlight_id, None)
        if item is not None:
            self._scene.removeItem(item)

    def refresh_highlight_visual(self, highlight_id: str) -> None:
        """Re-draw a highlight item after a color change."""
        item = self._highlight_items.get(highlight_id)
        if item is not None:
            item.update()

    # ---- mouse ------------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.LeftButton or self.mapper is None:
            return super().mousePressEvent(event)

        scene_pos = self.mapToScene(event.pos())

        if self.state.active_tool == "add_text":
            if self._on_page(scene_pos):
                px, py = self.mapper.screen_to_pdf(scene_pos.x(), scene_pos.y())
                px, py = self.mapper.clamp_pdf(px, py)
                self.pre_overlay_create.emit()
                overlay = TextOverlay(
                    page_index=self.state.selected_page_index,
                    x_pdf=px, y_pdf=py,
                )
                self.state.overlays.append(overlay)
                self.state.selected_overlay_id = overlay.id
                self.state.dirty = True
                item = self._add_overlay_item(overlay)
                item.setSelected(True)
                item._text.setFocus()
                self.overlay_created.emit(overlay.id)
            return

        if self.state.active_tool == "highlight":
            # If clicking an existing highlight, select it instead of starting a drag.
            for gitem in self._scene.items(scene_pos):
                if isinstance(gitem, _HighlightItem):
                    self._scene.clearSelection()
                    gitem.setSelected(True)
                    event.accept()
                    return
            if self._on_page(scene_pos):
                px, py = self.mapper.screen_to_pdf(scene_pos.x(), scene_pos.y())
                self._hl_anchor = self.mapper.clamp_pdf(px, py)
                self._clear_hl_preview()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if (
            self.state.active_tool == "highlight"
            and self._hl_anchor is not None
            and self.mapper is not None
        ):
            scene_pos = self.mapToScene(event.pos())
            px, py = self.mapper.screen_to_pdf(scene_pos.x(), scene_pos.y())
            px, py = self.mapper.clamp_pdf(px, py)
            self._update_hl_preview(px, py)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if (
            event.button() == Qt.LeftButton
            and self.state.active_tool == "highlight"
            and self._hl_anchor is not None
            and self.mapper is not None
        ):
            scene_pos = self.mapToScene(event.pos())
            px, py = self.mapper.screen_to_pdf(scene_pos.x(), scene_pos.y())
            px, py = self.mapper.clamp_pdf(px, py)
            self._finalize_highlight(px, py)
            self._hl_anchor = None
            self._clear_hl_preview()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_requested.emit(+1)
            elif delta < 0:
                self.zoom_requested.emit(-1)
            event.accept()
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            hid = self.state.selected_highlight_id
            if hid:
                self.highlight_delete_requested.emit(hid)
                event.accept()
                return
        super().keyPressEvent(event)

    # ---- highlight drag helpers ------------------------------------------

    def _update_hl_preview(self, cur_px: float, cur_py: float) -> None:
        self._clear_hl_preview()
        if self._hl_anchor is None or self.mapper is None or not self.doc.is_open:
            return
        ax, ay = self._hl_anchor
        words = self.doc.get_words(self.state.selected_page_index)
        selected = select_words(words, ax, ay, cur_px, cur_py)
        color = QColor(255, 235, 0, 90)
        for r in words_to_line_rects(selected):
            sx0, sy0 = self.mapper.pdf_to_screen(r[0], r[1])
            sx1, sy1 = self.mapper.pdf_to_screen(r[2], r[3])
            item = self._scene.addRect(
                QRectF(sx0, sy0, sx1 - sx0, sy1 - sy0),
                QPen(Qt.NoPen),
                QBrush(color),
            )
            item.setZValue(6)
            self._hl_preview.append(item)

    def _clear_hl_preview(self) -> None:
        for item in self._hl_preview:
            self._scene.removeItem(item)
        self._hl_preview.clear()

    def _finalize_highlight(self, end_px: float, end_py: float) -> None:
        if self._hl_anchor is None or not self.doc.is_open:
            return
        ax, ay = self._hl_anchor
        words = self.doc.get_words(self.state.selected_page_index)
        selected = select_words(words, ax, ay, end_px, end_py)
        rects = words_to_line_rects(selected)
        if not rects:
            return
        self.pre_highlight_create.emit()
        hl = HighlightOverlay(
            page_index=self.state.selected_page_index,
            rects=rects,
        )
        self.state.highlights.append(hl)
        self.state.selected_highlight_id = hl.id
        self.state.selected_overlay_id = None
        self.state.dirty = True
        item = self._add_highlight_item(hl)
        self._scene.clearSelection()
        item.setSelected(True)
        self.highlight_created.emit(hl.id)

    # ---- internals --------------------------------------------------------

    def _on_page(self, scene_pos: QPointF) -> bool:
        if self.mapper is None:
            return False
        return (
            0 <= scene_pos.x() <= self.mapper.pixmap_width
            and 0 <= scene_pos.y() <= self.mapper.pixmap_height
        )

    def _add_overlay_item(self, overlay: TextOverlay) -> _OverlayItem:
        item = _OverlayItem(overlay, self)
        if self.mapper is not None:
            sx, sy = self.mapper.pdf_to_screen(overlay.x_pdf, overlay.y_pdf)
            item.setPos(sx, sy)
        item.setZValue(10)
        self._scene.addItem(item)
        self._overlay_items[overlay.id] = item
        return item

    def _add_highlight_item(self, hl: HighlightOverlay) -> _HighlightItem:
        item = _HighlightItem(hl, self, self.mapper)
        self._scene.addItem(item)
        self._highlight_items[hl.id] = item
        return item

    def _show_placeholder(self) -> None:
        self._scene.setSceneRect(QRectF(0, 0, 600, 400))
        text = self._scene.addText("Open a PDF or merge PDFs to begin.")
        font = QFont()
        font.setPointSize(14)
        text.setFont(font)
        text.setDefaultTextColor(QColor("#666"))
        text.setPos(140, 180)
