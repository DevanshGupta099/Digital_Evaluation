"""Stage 5: draw grading marks onto a copy of the original script PDF.

Consumes evidence-linked grading output (line indices -> OCR bounding boxes)
and draws vector graphics at exact coordinates via PyMuPDF:
  - green tick next to lines cited as correct / mark-awarding
  - red cross next to lines cited as wrong
  - red underline beneath lines cited as incomplete / missing something
  - circled "awarded/total" badge near the start of each question segment
  - running total box on the last page
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import fitz

from ..ocr.base import BBox, OCRResult
from .coords import CoordinateMapper

GREEN = (0.0, 0.55, 0.1)
RED = (0.85, 0.1, 0.1)
BLUE = (0.1, 0.2, 0.7)


class AnnotationKind(str, Enum):
    TICK = "tick"
    CROSS = "cross"
    UNDERLINE = "underline"
    MARKS_BADGE = "marks_badge"


@dataclass
class Annotation:
    kind: AnnotationKind
    page_number: int  # 1-based
    bbox: BBox  # image-pixel space bbox of the target line/region
    label: str = ""  # e.g. "3/5" for MARKS_BADGE


class ScriptAnnotator:
    def __init__(self, pdf_bytes: bytes, ocr: OCRResult) -> None:
        self._doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        self._mappers: dict[int, CoordinateMapper] = {}
        for page in ocr.pages:
            if page.page_number <= len(self._doc) and page.width and page.height:
                self._mappers[page.page_number] = CoordinateMapper.for_page(
                    self._doc[page.page_number - 1], page.width, page.height
                )

    def apply(self, annotations: list[Annotation]) -> None:
        for ann in annotations:
            mapper = self._mappers.get(ann.page_number)
            if mapper is None or ann.page_number > len(self._doc):
                continue
            page = self._doc[ann.page_number - 1]
            rect = mapper.to_pdf_rect(ann.bbox)
            if ann.kind is AnnotationKind.TICK:
                self._draw_tick(page, rect)
            elif ann.kind is AnnotationKind.CROSS:
                self._draw_cross(page, rect)
            elif ann.kind is AnnotationKind.UNDERLINE:
                self._draw_underline(page, rect)
            elif ann.kind is AnnotationKind.MARKS_BADGE:
                self._draw_marks_badge(page, rect, ann.label)

    def add_total(self, awarded: float, total: float) -> None:
        page = self._doc[-1]
        rect = fitz.Rect(page.rect.width - 170, page.rect.height - 70,
                         page.rect.width - 20, page.rect.height - 25)
        page.draw_rect(rect, color=BLUE, width=1.5)
        page.insert_textbox(
            rect, f"Total: {_fmt(awarded)} / {_fmt(total)}",
            fontsize=14, color=BLUE, align=fitz.TEXT_ALIGN_CENTER,
        )

    def tobytes(self) -> bytes:
        return self._doc.tobytes()

    # -- drawing primitives (all coordinates already in PDF points) --

    def _draw_tick(self, page: fitz.Page, line_rect: fitz.Rect) -> None:
        size = max(10.0, min(18.0, line_rect.height))
        x = min(line_rect.x1 + 6, page.rect.width - size - 2)
        y = line_rect.y0 + line_rect.height / 2
        p1 = fitz.Point(x, y)
        p2 = fitz.Point(x + size * 0.35, y + size * 0.4)
        p3 = fitz.Point(x + size, y - size * 0.5)
        page.draw_line(p1, p2, color=GREEN, width=2.2)
        page.draw_line(p2, p3, color=GREEN, width=2.2)

    def _draw_cross(self, page: fitz.Page, line_rect: fitz.Rect) -> None:
        size = max(10.0, min(16.0, line_rect.height))
        x = min(line_rect.x1 + 6, page.rect.width - size - 2)
        y = line_rect.y0 + (line_rect.height - size) / 2
        page.draw_line(fitz.Point(x, y), fitz.Point(x + size, y + size), color=RED, width=2.2)
        page.draw_line(fitz.Point(x + size, y), fitz.Point(x, y + size), color=RED, width=2.2)

    def _draw_underline(self, page: fitz.Page, line_rect: fitz.Rect) -> None:
        y = min(line_rect.y1 + 2, page.rect.height - 2)
        page.draw_line(
            fitz.Point(line_rect.x0, y), fitz.Point(line_rect.x1, y), color=RED, width=1.8
        )

    def _draw_marks_badge(self, page: fitz.Page, anchor: fitz.Rect, label: str) -> None:
        radius = 16.0
        cx = max(radius + 2, anchor.x0 - radius - 8)
        cy = anchor.y0 + anchor.height / 2
        center = fitz.Point(cx, cy)
        page.draw_circle(center, radius, color=RED, width=1.8)
        box = fitz.Rect(cx - radius, cy - 8, cx + radius, cy + 12)
        page.insert_textbox(box, label, fontsize=10, color=RED, align=fitz.TEXT_ALIGN_CENTER)


def _fmt(value: float) -> str:
    return f"{value:g}"
