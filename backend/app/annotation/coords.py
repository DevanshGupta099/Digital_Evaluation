"""Coordinate transforms between OCR image-pixel space and PDF point space.

OCR runs on page images rendered at N DPI (pixels, origin top-left).
PyMuPDF draws in PDF points (72/inch, origin top-left in fitz's coordinate
convention). A page rendered at `dpi` maps back with a uniform scale of
72/dpi, but we derive the scale from actual page dimensions so it stays
correct for non-standard renders and image-derived PDFs.
"""
from __future__ import annotations

from dataclasses import dataclass

import fitz

from ..ocr.base import BBox


@dataclass(frozen=True)
class CoordinateMapper:
    image_width: float
    image_height: float
    pdf_width: float
    pdf_height: float

    @property
    def scale_x(self) -> float:
        return self.pdf_width / self.image_width

    @property
    def scale_y(self) -> float:
        return self.pdf_height / self.image_height

    def to_pdf_point(self, x: float, y: float) -> tuple[float, float]:
        return (x * self.scale_x, y * self.scale_y)

    def to_pdf_rect(self, bbox: BBox) -> fitz.Rect:
        x0, y0 = self.to_pdf_point(bbox.x0, bbox.y0)
        x1, y1 = self.to_pdf_point(bbox.x1, bbox.y1)
        return fitz.Rect(x0, y0, x1, y1)

    @staticmethod
    def for_page(page: fitz.Page, image_width: float, image_height: float) -> "CoordinateMapper":
        return CoordinateMapper(
            image_width=image_width,
            image_height=image_height,
            pdf_width=page.rect.width,
            pdf_height=page.rect.height,
        )
