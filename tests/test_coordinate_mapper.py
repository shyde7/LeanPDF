import pytest

from app.core.coordinate_mapper import CoordinateMapper


def test_round_trip_at_zoom_1():
    m = CoordinateMapper(page_width_pdf=612, page_height_pdf=792, zoom=1.0)
    px, py = m.screen_to_pdf(100, 200)
    sx, sy = m.pdf_to_screen(px, py)
    assert (sx, sy) == (100, 200)


def test_round_trip_at_zoom_2():
    m = CoordinateMapper(page_width_pdf=612, page_height_pdf=792, zoom=2.0)
    px, py = m.screen_to_pdf(300, 400)
    assert px == 150
    assert py == 200
    sx, sy = m.pdf_to_screen(px, py)
    assert (sx, sy) == (300, 400)


def test_round_trip_fractional_zoom():
    m = CoordinateMapper(page_width_pdf=400, page_height_pdf=500, zoom=0.75)
    for sx, sy in [(0, 0), (10, 20), (399 * 0.75, 499 * 0.75)]:
        px, py = m.screen_to_pdf(sx, sy)
        rsx, rsy = m.pdf_to_screen(px, py)
        assert rsx == pytest.approx(sx)
        assert rsy == pytest.approx(sy)


def test_clamp_pdf():
    m = CoordinateMapper(page_width_pdf=100, page_height_pdf=200, zoom=1.0)
    assert m.clamp_pdf(-5, -5) == (0, 0)
    assert m.clamp_pdf(150, 250) == (100, 200)
    assert m.clamp_pdf(50, 80) == (50, 80)


def test_zero_zoom_raises():
    m = CoordinateMapper(page_width_pdf=100, page_height_pdf=200, zoom=0.0)
    with pytest.raises(ValueError):
        m.screen_to_pdf(1, 1)


def test_pixmap_dimensions():
    m = CoordinateMapper(page_width_pdf=100, page_height_pdf=200, zoom=1.5)
    assert m.pixmap_width == 150
    assert m.pixmap_height == 300
