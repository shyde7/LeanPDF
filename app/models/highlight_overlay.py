"""Highlight overlay model: a set of PDF-space rects that will become a highlight annotation."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List, Tuple


def _new_id() -> str:
    return uuid.uuid4().hex


@dataclass
class HighlightOverlay:
    page_index: int
    rects: List[Tuple[float, float, float, float]]  # (x0, y0, x1, y1) in PDF space per line
    color: Tuple[float, float, float] = (1.0, 0.92, 0.0)   # yellow
    id: str = field(default_factory=_new_id)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "page_index": self.page_index,
            "rects": [list(r) for r in self.rects],
            "color": list(self.color),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "HighlightOverlay":
        return cls(
            id=d.get("id", _new_id()),
            page_index=int(d["page_index"]),
            rects=[tuple(r) for r in d["rects"]],
            color=tuple(d.get("color", (1.0, 0.92, 0.0))),
        )
