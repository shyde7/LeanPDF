"""Word extraction and hit-testing for the highlight tool.

PyMuPDF page.get_text("words") returns tuples:
    (x0, y0, x1, y1, "word", block_no, line_no, word_no)
Coordinates are in PDF space (points, y=0 at top, increasing downward).
"""
from __future__ import annotations

from collections import defaultdict
from typing import List, Tuple

import pymupdf

Word = Tuple[float, float, float, float, str, int, int, int]


def extract_words(doc: pymupdf.Document, page_index: int) -> List[Word]:
    return doc[page_index].get_text("words")


def select_words(
    words: List[Word],
    x0: float, y0: float,
    x1: float, y1: float,
) -> List[Word]:
    """Return words whose bounding box overlaps the given PDF-space rect.
    Handles inverted drag coordinates (x0 > x1 or y0 > y1).
    """
    rx0, ry0 = min(x0, x1), min(y0, y1)
    rx1, ry1 = max(x0, x1), max(y0, y1)
    if rx0 == rx1 or ry0 == ry1:
        return []
    return [
        w for w in words
        if w[0] < rx1 and w[2] > rx0 and w[1] < ry1 and w[3] > ry0
    ]


def words_to_line_rects(words: List[Word]) -> List[Tuple[float, float, float, float]]:
    """Merge words into one bounding rect per line (block+line group).

    Returns rects ordered top-to-bottom as they appear on the page.
    """
    if not words:
        return []
    lines: dict = defaultdict(list)
    for w in words:
        lines[(w[5], w[6])].append(w)
    rects = []
    for key in sorted(lines):
        lw = lines[key]
        rects.append((
            min(w[0] for w in lw),
            min(w[1] for w in lw),
            max(w[2] for w in lw),
            max(w[3] for w in lw),
        ))
    return rects
