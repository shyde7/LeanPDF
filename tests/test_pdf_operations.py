import pytest

from app.core import operations
from app.core.pdf_document import PDFDocument, PDFDocumentError
from app.models.app_state import AppState
from app.models.text_overlay import TextOverlay


def test_open_and_page_count(small_pdf):
    doc = PDFDocument()
    doc.open(small_pdf)
    assert doc.is_open
    assert doc.page_count() == 3
    doc.close()


def test_delete_page_reduces_count(small_pdf):
    doc = PDFDocument()
    doc.open(small_pdf)
    state = AppState(current_file_path=small_pdf)
    operations.delete_page(doc, state, 0)
    assert doc.page_count() == 2
    doc.close()


def test_delete_page_reindexes_overlays(small_pdf):
    doc = PDFDocument()
    doc.open(small_pdf)
    state = AppState(current_file_path=small_pdf)
    state.overlays = [
        TextOverlay(page_index=0, x_pdf=0, y_pdf=0, text="p0"),
        TextOverlay(page_index=1, x_pdf=0, y_pdf=0, text="on-deleted"),
        TextOverlay(page_index=2, x_pdf=0, y_pdf=0, text="p2"),
    ]
    operations.delete_page(doc, state, 1)
    assert doc.page_count() == 2
    remaining = sorted((o.page_index, o.text) for o in state.overlays)
    assert remaining == [(0, "p0"), (1, "p2")]
    doc.close()


def test_cannot_delete_last_page(single_page_pdf):
    doc = PDFDocument()
    doc.open(single_page_pdf)
    with pytest.raises(PDFDocumentError):
        doc.delete_page(0)
    doc.close()


def test_merge_pdfs_appends(small_pdf, two_page_pdf):
    doc = PDFDocument()
    doc.open(small_pdf)
    state = AppState(current_file_path=small_pdf)
    operations.merge_pdfs(doc, state, [two_page_pdf])
    assert doc.page_count() == 5
    doc.close()


def test_merge_when_no_doc_open_creates_new(small_pdf, two_page_pdf):
    doc = PDFDocument()
    state = AppState()
    operations.merge_pdfs(doc, state, [small_pdf, two_page_pdf])
    assert doc.is_open
    assert doc.page_count() == 5
    doc.close()


def test_move_page_down_reindexes_overlays(small_pdf):
    # small_pdf has 3 pages (A, B, C at indices 0, 1, 2).
    doc = PDFDocument()
    doc.open(small_pdf)
    state = AppState(current_file_path=small_pdf, selected_page_index=0)
    state.overlays = [
        TextOverlay(page_index=0, x_pdf=0, y_pdf=0, text="on-A"),
        TextOverlay(page_index=1, x_pdf=0, y_pdf=0, text="on-B"),
        TextOverlay(page_index=2, x_pdf=0, y_pdf=0, text="on-C"),
    ]
    # Move page 0 (A) down to index 2 → new order: B, C, A
    operations.move_page(doc, state, 0, 2)
    result = {o.text: o.page_index for o in state.overlays}
    assert result["on-A"] == 2
    assert result["on-B"] == 0
    assert result["on-C"] == 1
    assert state.selected_page_index == 2  # followed the moved page
    doc.close()


def test_move_page_up_reindexes_overlays(small_pdf):
    doc = PDFDocument()
    doc.open(small_pdf)
    state = AppState(current_file_path=small_pdf, selected_page_index=2)
    state.overlays = [
        TextOverlay(page_index=0, x_pdf=0, y_pdf=0, text="on-A"),
        TextOverlay(page_index=1, x_pdf=0, y_pdf=0, text="on-B"),
        TextOverlay(page_index=2, x_pdf=0, y_pdf=0, text="on-C"),
    ]
    # Move page 2 (C) up to index 0 → new order: C, A, B
    operations.move_page(doc, state, 2, 0)
    result = {o.text: o.page_index for o in state.overlays}
    assert result["on-C"] == 0
    assert result["on-A"] == 1
    assert result["on-B"] == 2
    assert state.selected_page_index == 0  # followed the moved page
    doc.close()


def test_open_invalid_pdf_raises(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf at all")
    doc = PDFDocument()
    with pytest.raises(PDFDocumentError):
        doc.open(str(bad))


def test_open_missing_file_raises(tmp_path):
    doc = PDFDocument()
    with pytest.raises(PDFDocumentError):
        doc.open(str(tmp_path / "nope.pdf"))


def test_save_as_writes_new_file(tmp_path, small_pdf):
    doc = PDFDocument()
    doc.open(small_pdf)
    out = tmp_path / "copy.pdf"
    doc.save_as(str(out))
    assert out.exists()
    assert out.stat().st_size > 0
    doc.close()


def test_render_thumbnail_returns_bytes(small_pdf):
    doc = PDFDocument()
    doc.open(small_pdf)
    img = doc.render_thumbnail(0)
    assert img.width > 0 and img.height > 0
    assert len(img.samples) >= img.width * img.height * 3
    doc.close()
