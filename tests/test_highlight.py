import pymupdf
import pytest

from app.core.pdf_document import PDFDocument
from app.core.text_layer import extract_words, select_words, words_to_line_rects
from app.models.app_state import AppState
from app.models.highlight_overlay import HighlightOverlay
from app.services.export_service import export_pdf


# ---- text_layer unit tests ------------------------------------------------

def test_select_words_basic():
    words = [
        (10.0, 10.0, 50.0, 20.0, "hello", 0, 0, 0),
        (60.0, 10.0, 100.0, 20.0, "world", 0, 0, 1),
        (10.0, 30.0, 50.0, 40.0, "below", 0, 1, 0),
    ]
    # Select only the first line.
    selected = select_words(words, 0, 0, 110, 25)
    assert len(selected) == 2
    assert selected[0][4] == "hello"
    assert selected[1][4] == "world"


def test_select_words_inverted_drag():
    words = [(10.0, 10.0, 50.0, 20.0, "hi", 0, 0, 0)]
    # Drag from bottom-right to top-left — should still hit.
    selected = select_words(words, 60, 30, 0, 0)
    assert len(selected) == 1


def test_select_words_empty_when_degenerate():
    words = [(10.0, 10.0, 50.0, 20.0, "hi", 0, 0, 0)]
    assert select_words(words, 5, 5, 5, 5) == []   # zero-area rect


def test_words_to_line_rects_merges_per_line():
    words = [
        (10.0, 10.0, 40.0, 20.0, "a", 0, 0, 0),
        (45.0, 10.0, 80.0, 20.0, "b", 0, 0, 1),
        (10.0, 25.0, 60.0, 35.0, "c", 0, 1, 0),
    ]
    rects = words_to_line_rects(words)
    assert len(rects) == 2
    # First line spans both words.
    assert rects[0][0] == 10.0
    assert rects[0][2] == 80.0


# ---- highlight model round-trip -------------------------------------------

def test_highlight_overlay_round_trip():
    hl = HighlightOverlay(
        page_index=1,
        rects=[(10.0, 20.0, 100.0, 30.0), (10.0, 35.0, 80.0, 45.0)],
        color=(0.55, 0.93, 0.55),
    )
    d = hl.to_dict()
    restored = HighlightOverlay.from_dict(d)
    assert restored.id == hl.id
    assert restored.page_index == 1
    assert len(restored.rects) == 2
    assert restored.color == (0.55, 0.93, 0.55)


# ---- AppState reindexing ---------------------------------------------------

def test_highlight_reindex_after_page_delete():
    state = AppState()
    state.highlights = [
        HighlightOverlay(page_index=0, rects=[(0, 0, 10, 10)]),
        HighlightOverlay(page_index=1, rects=[(0, 0, 10, 10)]),  # deleted
        HighlightOverlay(page_index=2, rects=[(0, 0, 10, 10)]),
    ]
    state.reindex_after_page_delete(1)
    assert len(state.highlights) == 2
    assert state.highlights[0].page_index == 0
    assert state.highlights[1].page_index == 1


# ---- export flattens highlights -------------------------------------------

def test_export_flattens_highlights(tmp_path, small_pdf):
    doc = PDFDocument()
    doc.open(small_pdf)
    state = AppState(current_file_path=small_pdf)

    # Page 0 of small_pdf has text "A" at (50, 50).  Highlight around it.
    hl = HighlightOverlay(page_index=0, rects=[(30.0, 30.0, 200.0, 80.0)])
    state.highlights.append(hl)

    out = str(tmp_path / "hl_out.pdf")
    export_pdf(doc, state, out)

    assert state.highlights == []
    assert state.dirty is False

    # Verify the saved PDF has an annotation on page 0.
    with pymupdf.open(out) as reopened:
        annots = list(reopened[0].annots())
        assert len(annots) >= 1

    doc.close()
