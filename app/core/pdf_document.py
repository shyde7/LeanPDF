"""Thin wrapper around a pymupdf.Document with rendering and edit ops.

No UI / Qt code lives here. Returned image data is raw RGB(A) bytes plus
size/stride metadata so the UI layer can wrap them in QImage.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple

import pymupdf

from ..models.highlight_overlay import HighlightOverlay
from ..models.text_overlay import TextOverlay
from .render_cache import RenderCache


THUMBNAIL_ZOOM = 0.18


@dataclass
class RenderedImage:
    width: int
    height: int
    stride: int
    samples: bytes  # RGB bytes, 3 channels
    page_width_pdf: float
    page_height_pdf: float


class PDFDocumentError(Exception):
    pass


class EncryptedPDFError(PDFDocumentError):
    pass


class PDFDocument:
    def __init__(self) -> None:
        self._doc: Optional[pymupdf.Document] = None
        self._path: Optional[str] = None
        self._version: int = 0
        self._cache = RenderCache(max_entries=128)

    # ---- lifecycle ----------------------------------------------------

    def open(self, path: str) -> None:
        if not os.path.exists(path):
            raise PDFDocumentError(f"File not found: {path}")
        try:
            doc = pymupdf.open(path)
        except Exception as exc:  # pymupdf raises a variety of errors
            raise PDFDocumentError(f"Could not open PDF: {exc}") from exc
        if doc.needs_pass:
            doc.close()
            raise EncryptedPDFError("PDF is password-protected")
        if doc.page_count == 0:
            doc.close()
            raise PDFDocumentError("PDF has no pages")
        self.close()
        self._doc = doc
        self._path = path
        self._version += 1
        self._cache.clear()

    def open_from_paths_as_new(self, paths: Sequence[str]) -> None:
        """Create a fresh in-memory doc by appending the given PDFs."""
        if not paths:
            raise PDFDocumentError("No PDFs provided")
        new_doc = pymupdf.open()  # empty
        try:
            for p in paths:
                with pymupdf.open(p) as src:
                    if src.needs_pass:
                        raise EncryptedPDFError(f"Encrypted: {p}")
                    new_doc.insert_pdf(src)
        except EncryptedPDFError:
            new_doc.close()
            raise
        except Exception as exc:
            new_doc.close()
            raise PDFDocumentError(f"Failed building merged document: {exc}") from exc
        self.close()
        self._doc = new_doc
        self._path = None
        self._version += 1
        self._cache.clear()

    def close(self) -> None:
        if self._doc is not None:
            try:
                self._doc.close()
            except Exception:
                pass
        self._doc = None
        self._path = None
        self._cache.clear()

    # ---- info ---------------------------------------------------------

    @property
    def is_open(self) -> bool:
        return self._doc is not None

    @property
    def path(self) -> Optional[str]:
        return self._path

    @property
    def version(self) -> int:
        return self._version

    def page_count(self) -> int:
        if self._doc is None:
            return 0
        return self._doc.page_count

    def page_size_pdf(self, page_index: int) -> Tuple[float, float]:
        self._require_open()
        rect = self._doc[page_index].rect
        return (rect.width, rect.height)

    # ---- rendering ----------------------------------------------------

    def render_page(self, page_index: int, zoom: float) -> RenderedImage:
        self._require_open()
        key = self._cache.make_key(id(self._doc), page_index, zoom, self._version, "page")
        cached = self._cache.get(key)
        if cached is not None:
            return cached  # type: ignore[return-value]
        page = self._doc[page_index]
        mat = pymupdf.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        rect = page.rect
        img = RenderedImage(
            width=pix.width,
            height=pix.height,
            stride=pix.stride,
            samples=bytes(pix.samples),
            page_width_pdf=rect.width,
            page_height_pdf=rect.height,
        )
        self._cache.put(key, img)
        return img

    def render_thumbnail(self, page_index: int) -> RenderedImage:
        self._require_open()
        key = self._cache.make_key(id(self._doc), page_index, THUMBNAIL_ZOOM, self._version, "thumb")
        cached = self._cache.get(key)
        if cached is not None:
            return cached  # type: ignore[return-value]
        page = self._doc[page_index]
        mat = pymupdf.Matrix(THUMBNAIL_ZOOM, THUMBNAIL_ZOOM)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        rect = page.rect
        img = RenderedImage(
            width=pix.width,
            height=pix.height,
            stride=pix.stride,
            samples=bytes(pix.samples),
            page_width_pdf=rect.width,
            page_height_pdf=rect.height,
        )
        self._cache.put(key, img)
        return img

    # ---- editing ------------------------------------------------------

    def delete_page(self, page_index: int) -> None:
        self._require_open()
        if self._doc.page_count <= 1:
            raise PDFDocumentError("Cannot delete the last remaining page")
        if not (0 <= page_index < self._doc.page_count):
            raise PDFDocumentError("Page index out of range")
        self._doc.delete_page(page_index)
        self._bump_version()

    def move_page(self, from_index: int, to_index: int) -> None:
        self._require_open()
        count = self._doc.page_count
        if not (0 <= from_index < count) or not (0 <= to_index < count):
            raise PDFDocumentError("Page index out of range")
        if from_index == to_index:
            return
        self._doc.move_page(from_index, to_index)
        self._bump_version()

    def merge_pdfs(self, paths: Sequence[str]) -> None:
        self._require_open()
        if not paths:
            raise PDFDocumentError("No PDFs to merge")
        for p in paths:
            try:
                with pymupdf.open(p) as src:
                    if src.needs_pass:
                        raise EncryptedPDFError(f"Encrypted PDF cannot be merged: {p}")
                    self._doc.insert_pdf(src)
            except EncryptedPDFError:
                raise
            except Exception as exc:
                raise PDFDocumentError(f"Failed to merge {p}: {exc}") from exc
        self._bump_version()

    def apply_text_overlays(self, overlays: Iterable[TextOverlay]) -> None:
        """Flatten overlays into the in-memory document."""
        self._require_open()
        any_applied = False
        for ov in overlays:
            if not (0 <= ov.page_index < self._doc.page_count):
                continue
            page = self._doc[ov.page_index]
            rect = pymupdf.Rect(
                ov.x_pdf,
                ov.y_pdf,
                ov.x_pdf + max(ov.width, 1.0),
                ov.y_pdf + max(ov.height, ov.font_size + 4),
            )
            font_name = "hebo" if ov.bold else (ov.font_name or "helv")
            try:
                rc = page.insert_textbox(
                    rect,
                    ov.text,
                    fontsize=ov.font_size,
                    fontname=font_name,
                    color=tuple(ov.color),
                    align=0,
                )
                if rc < 0:
                    # Text didn't fit; fall back to anchored insert at top-left baseline.
                    page.insert_text(
                        (ov.x_pdf, ov.y_pdf + ov.font_size),
                        ov.text,
                        fontsize=ov.font_size,
                        fontname=font_name,
                        color=tuple(ov.color),
                    )
            except Exception as exc:
                raise PDFDocumentError(f"Failed inserting text overlay: {exc}") from exc
            any_applied = True
        if any_applied:
            self._bump_version()

    # ---- saving -------------------------------------------------------

    def save_as(self, path: str) -> None:
        self._require_open()
        same_file = self._path is not None and os.path.abspath(path) == os.path.abspath(self._path)
        try:
            if same_file:
                # Avoid destructive in-place write: write to temp then replace.
                tmp_path = path + ".tmp_leanpdf"
                self._doc.save(tmp_path, garbage=4, deflate=True, clean=True)
                self._doc.close()
                self._doc = None
                os.replace(tmp_path, path)
                self._doc = pymupdf.open(path)
            else:
                self._doc.save(path, garbage=4, deflate=True, clean=True)
        except Exception as exc:
            raise PDFDocumentError(f"Save failed: {exc}") from exc
        self._path = path
        self._bump_version()

    # ---- text extraction (for highlight tool) -------------------------

    def get_words(self, page_index: int) -> list:
        """Return word tuples (x0,y0,x1,y1,text,block,line,word) in PDF space."""
        self._require_open()
        return self._doc[page_index].get_text("words")

    def apply_highlights(self, highlights: Iterable[HighlightOverlay]) -> None:
        """Burn highlight annotations into the in-memory document."""
        self._require_open()
        any_applied = False
        for hl in highlights:
            if not (0 <= hl.page_index < self._doc.page_count):
                continue
            page = self._doc[hl.page_index]
            for rect in hl.rects:
                r = pymupdf.Rect(*rect)
                try:
                    annot = page.add_highlight_annot(r)
                    annot.set_colors(stroke=tuple(hl.color))
                    annot.update()
                    any_applied = True
                except Exception as exc:
                    raise PDFDocumentError(f"Failed adding highlight: {exc}") from exc
        if any_applied:
            self._bump_version()

    # ---- snapshot / restore (used by undo stack) ----------------------

    def snapshot_bytes(self) -> bytes:
        self._require_open()
        return bytes(self._doc.tobytes())

    def restore_from_bytes(self, data: bytes, file_path: Optional[str] = None) -> None:
        new_doc = pymupdf.open(stream=data, filetype="pdf")
        if self._doc is not None:
            try:
                self._doc.close()
            except Exception:
                pass
        self._doc = new_doc
        self._path = file_path
        self._bump_version()

    # ---- internals ----------------------------------------------------

    def _require_open(self) -> None:
        if self._doc is None:
            raise PDFDocumentError("No document is open")

    def _bump_version(self) -> None:
        self._version += 1
        self._cache.clear()
