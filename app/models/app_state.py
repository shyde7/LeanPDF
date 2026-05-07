"""In-memory app state shared across UI and core."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .highlight_overlay import HighlightOverlay
from .text_overlay import TextOverlay


@dataclass
class AppState:
    current_file_path: Optional[str] = None
    selected_page_index: int = 0
    zoom: float = 1.0
    dirty: bool = False
    active_tool: str = "select"  # "select" | "add_text" | "highlight"
    overlays: List[TextOverlay] = field(default_factory=list)
    selected_overlay_id: Optional[str] = None
    highlights: List[HighlightOverlay] = field(default_factory=list)
    selected_highlight_id: Optional[str] = None

    # ---- text overlays ------------------------------------------------

    def overlays_on_page(self, page_index: int) -> List[TextOverlay]:
        return [o for o in self.overlays if o.page_index == page_index]

    def find_overlay(self, overlay_id: str) -> Optional[TextOverlay]:
        for o in self.overlays:
            if o.id == overlay_id:
                return o
        return None

    def remove_overlay(self, overlay_id: str) -> None:
        self.overlays = [o for o in self.overlays if o.id != overlay_id]
        if self.selected_overlay_id == overlay_id:
            self.selected_overlay_id = None

    # ---- highlights ---------------------------------------------------

    def highlights_on_page(self, page_index: int) -> List[HighlightOverlay]:
        return [h for h in self.highlights if h.page_index == page_index]

    def find_highlight(self, highlight_id: str) -> Optional[HighlightOverlay]:
        for h in self.highlights:
            if h.id == highlight_id:
                return h
        return None

    def remove_highlight(self, highlight_id: str) -> None:
        self.highlights = [h for h in self.highlights if h.id != highlight_id]
        if self.selected_highlight_id == highlight_id:
            self.selected_highlight_id = None

    # ---- reindexing ---------------------------------------------------

    def reindex_after_page_delete(self, deleted_page: int) -> None:
        new_overlays = []
        for o in self.overlays:
            if o.page_index == deleted_page:
                continue
            if o.page_index > deleted_page:
                o.page_index -= 1
            new_overlays.append(o)
        self.overlays = new_overlays

        new_highlights = []
        for h in self.highlights:
            if h.page_index == deleted_page:
                continue
            if h.page_index > deleted_page:
                h.page_index -= 1
            new_highlights.append(h)
        self.highlights = new_highlights

    def reindex_after_page_move(self, from_idx: int, to_idx: int) -> None:
        if from_idx == to_idx:
            return
        for items in (self.overlays, self.highlights):
            for o in items:
                if o.page_index == from_idx:
                    o.page_index = to_idx
                elif from_idx < to_idx and from_idx < o.page_index <= to_idx:
                    o.page_index -= 1
                elif from_idx > to_idx and to_idx <= o.page_index < from_idx:
                    o.page_index += 1
