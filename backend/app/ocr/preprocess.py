"""Document ingestion: normalize any upload (PDF or image) to per-page PNG images.

Handwriting OCR quality degrades sharply below ~300 DPI, so PDFs are rendered
at settings.render_dpi. Originals are stored untouched; rendering happens on a
copy in memory.
"""
from __future__ import annotations

from dataclasses import dataclass

import fitz  # PyMuPDF

from ..config import settings

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


@dataclass
class RenderedPage:
    page_number: int  # 1-based
    png_bytes: bytes
    width_px: int
    height_px: int
    # PDF-space page size in points; None when the source was a raster image.
    pdf_width_pt: float | None
    pdf_height_pt: float | None


def render_document(data: bytes, filename: str, dpi: int | None = None) -> list[RenderedPage]:
    dpi = dpi or settings.render_dpi
    lower = filename.lower()
    if any(lower.endswith(ext) for ext in IMAGE_EXTENSIONS):
        return [_wrap_image(data)]
    return _render_pdf(data, dpi)


def _render_pdf(data: bytes, dpi: int) -> list[RenderedPage]:
    pages: list[RenderedPage] = []
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    with fitz.open(stream=data, filetype="pdf") as doc:
        for i, page in enumerate(doc):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            pages.append(
                RenderedPage(
                    page_number=i + 1,
                    png_bytes=pix.tobytes("png"),
                    width_px=pix.width,
                    height_px=pix.height,
                    pdf_width_pt=page.rect.width,
                    pdf_height_pt=page.rect.height,
                )
            )
    return pages


def _wrap_image(data: bytes) -> RenderedPage:
    with fitz.open(stream=data) as doc:
        pix = doc[0].get_pixmap(alpha=False)
    return RenderedPage(
        page_number=1,
        png_bytes=pix.tobytes("png"),
        width_px=pix.width,
        height_px=pix.height,
        pdf_width_pt=None,
        pdf_height_pt=None,
    )


def images_to_pdf(page_images: list[bytes]) -> bytes:
    """Build a PDF from raster pages so image uploads can also be annotated."""
    out = fitz.open()
    for png in page_images:
        with fitz.open(stream=png) as img:
            rect = img[0].rect
            pdf_bytes = img.convert_to_pdf()
        with fitz.open(stream=pdf_bytes, filetype="pdf") as src:
            page = out.new_page(width=rect.width, height=rect.height)
            page.show_pdf_page(rect, src, 0)
    return out.tobytes()
