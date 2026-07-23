"""Deterministic mock OCR provider for local development and tests.

Lays out injected text as evenly spaced lines with plausible bounding boxes so
the full pipeline (segmentation -> grading -> annotation) can run end-to-end
without cloud credentials.
"""
from __future__ import annotations

from .base import BBox, OCRLine, OCRPage, OCRProvider, OCRResult, OCRWord


class MockOCRProvider(OCRProvider):
    def __init__(
        self,
        page_texts: list[str] | None = None,
        page_size: tuple[int, int] = (2550, 3300),  # 8.5x11in at 300dpi
        confidence: float = 0.95,
    ) -> None:
        self._page_texts = page_texts or []
        self._page_size = page_size
        self._confidence = confidence

    def recognize(self, page_images: list[bytes]) -> OCRResult:
        width, height = self._page_size
        pages: list[OCRPage] = []
        for i in range(len(page_images)):
            text = self._page_texts[i] if i < len(self._page_texts) else ""
            lines = self._layout_lines(text, width)
            pages.append(OCRPage(page_number=i + 1, width=width, height=height, lines=lines))
        return OCRResult(pages=pages)

    def _layout_lines(self, text: str, width: int) -> list[OCRLine]:
        margin_x, top, line_height = 200.0, 300.0, 90.0
        lines: list[OCRLine] = []
        for i, raw in enumerate(t for t in text.splitlines() if t.strip()):
            y0 = top + i * line_height
            x = margin_x
            words: list[OCRWord] = []
            for token in raw.split():
                w = 40.0 * len(token)
                words.append(
                    OCRWord(
                        text=token,
                        bbox=BBox(x, y0, min(x + w, width - margin_x), y0 + line_height * 0.7),
                        confidence=self._confidence,
                    )
                )
                x += w + 25.0
            bbox = BBox(margin_x, y0, min(x, width - margin_x), y0 + line_height * 0.7)
            lines.append(
                OCRLine(text=raw.strip(), bbox=bbox, confidence=self._confidence, words=words)
            )
        return lines
