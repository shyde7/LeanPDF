"""Text overlay model: a deferred text annotation drawn on top of a PDF page."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from typing import Tuple


def _new_id() -> str:
    return uuid.uuid4().hex


@dataclass
class TextOverlay:
    page_index: int
    x_pdf: float
    y_pdf: float
    text: str = "New Text"
    font_size: float = 12.0
    font_name: str = "helv"
    color: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    width: float = 120.0
    height: float = 24.0
    bold: bool = False
    id: str = field(default_factory=_new_id)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TextOverlay":
        color = d.get("color", (0.0, 0.0, 0.0))
        if isinstance(color, list):
            color = tuple(color)
        return cls(
            id=d.get("id", _new_id()),
            page_index=d["page_index"],
            x_pdf=float(d["x_pdf"]),
            y_pdf=float(d["y_pdf"]),
            text=d.get("text", ""),
            font_size=float(d.get("font_size", 12.0)),
            font_name=d.get("font_name", "helv"),
            color=color,
            width=float(d.get("width", 120.0)),
            height=float(d.get("height", 24.0)),
            bold=bool(d.get("bold", False)),
        )
