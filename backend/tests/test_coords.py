import fitz

from app.annotation.coords import CoordinateMapper
from app.ocr.base import BBox


def test_300dpi_scale_maps_pixels_to_points():
    # Letter page: 612x792 pt; at 300 DPI the render is 2550x3300 px.
    mapper = CoordinateMapper(image_width=2550, image_height=3300,
                              pdf_width=612, pdf_height=792)
    assert abs(mapper.scale_x - 72 / 300) < 1e-9
    assert abs(mapper.scale_y - 72 / 300) < 1e-9
    x, y = mapper.to_pdf_point(2550, 3300)
    assert (round(x, 6), round(y, 6)) == (612, 792)


def test_bbox_rect_roundtrip():
    mapper = CoordinateMapper(image_width=1000, image_height=2000,
                              pdf_width=500, pdf_height=1000)
    rect = mapper.to_pdf_rect(BBox(100, 200, 300, 400))
    assert rect == fitz.Rect(50, 100, 150, 200)


def test_for_page_uses_actual_page_size():
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    mapper = CoordinateMapper.for_page(page, 2550, 3300)
    assert abs(mapper.scale_x - 0.24) < 1e-9
    doc.close()


def test_bbox_helpers():
    b = BBox(0, 0, 10, 20)
    assert b.width == 10 and b.height == 20 and b.center == (5, 10)
    u = b.union(BBox(5, -5, 30, 10))
    assert (u.x0, u.y0, u.x1, u.y1) == (0, -5, 30, 20)
    p = BBox.from_points([(3, 4), (1, 9), (7, 2)])
    assert (p.x0, p.y0, p.x1, p.y1) == (1, 2, 7, 9)
