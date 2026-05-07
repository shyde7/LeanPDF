import pymupdf

from app.core.pdf_document import PDFDocument
from app.models.app_state import AppState
from app.models.text_overlay import TextOverlay
from app.core import operations
from app.services.export_service import export_pdf


def test_overlay_dataclass_round_trip():
    ov = TextOverlay(page_index=2, x_pdf=100.0, y_pdf=150.0, text="hi", font_size=14.0)
    d = ov.to_dict()
    restored = TextOverlay.from_dict(d)
    assert restored.page_index == 2
    assert restored.text == "hi"
    assert restored.font_size == 14.0
    assert restored.id == ov.id


def test_reindex_after_page_delete_removes_and_shifts():
    state = AppState()
    state.overlays = [
        TextOverlay(page_index=0, x_pdf=0, y_pdf=0, text="a"),
        TextOverlay(page_index=1, x_pdf=0, y_pdf=0, text="b"),
        TextOverlay(page_index=2, x_pdf=0, y_pdf=0, text="c"),
        TextOverlay(page_index=2, x_pdf=0, y_pdf=0, text="c2"),
    ]
    state.reindex_after_page_delete(1)
    pages = sorted(o.page_index for o in state.overlays)
    texts = sorted(o.text for o in state.overlays)
    assert pages == [0, 1, 1]
    assert texts == ["a", "c", "c2"]


def test_export_flattens_overlay_text(tmp_path, small_pdf):
    doc = PDFDocument()
    doc.open(small_pdf)
    state = AppState(current_file_path=small_pdf)

    overlay = TextOverlay(
        page_index=0,
        x_pdf=80,
        y_pdf=100,
        text="HelloOverlay",
        font_size=14.0,
        width=200,
        height=30,
    )
    operations.add_text_overlay(state, overlay)

    out = str(tmp_path / "out.pdf")
    export_pdf(doc, state, out)

    assert state.overlays == []
    assert state.dirty is False
    assert state.current_file_path == out

    with pymupdf.open(out) as reopened:
        text = reopened[0].get_text()
        assert "HelloOverlay" in text
    doc.close()
