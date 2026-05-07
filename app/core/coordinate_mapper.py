"""Convert between screen-space (rendered pixmap) and PDF-space coordinates.

PyMuPDF renders a page using a zoom matrix, so screen pixels = pdf_units * zoom.
PDF coordinates use a top-left origin in PyMuPDF's Page API (y grows downward),
which matches the rendered pixmap's pixel space — no Y-flip needed here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class CoordinateMapper:
    page_width_pdf: float
    page_height_pdf: float
    zoom: float = 1.0

    @property
    def pixmap_width(self) -> float:
        return self.page_width_pdf * self.zoom

    @property
    def pixmap_height(self) -> float:
        return self.page_height_pdf * self.zoom

    def screen_to_pdf(self, sx: float, sy: float) -> Tuple[float, float]:
        if self.zoom == 0:
            raise ValueError("zoom must be non-zero")
        return (sx / self.zoom, sy / self.zoom)

    def pdf_to_screen(self, px: float, py: float) -> Tuple[float, float]:
        return (px * self.zoom, py * self.zoom)

    def clamp_pdf(self, px: float, py: float) -> Tuple[float, float]:
        cx = max(0.0, min(self.page_width_pdf, px))
        cy = max(0.0, min(self.page_height_pdf, py))
        return (cx, cy)
