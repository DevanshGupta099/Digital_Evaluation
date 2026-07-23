"""Google Cloud Vision adapter using DOCUMENT_TEXT_DETECTION (handwriting-tuned).

Vision returns vertex coordinates in image pixel space; words are grouped into
lines by paragraph, matching our OCRLine granularity closely enough for
evidence citation and annotation placement.
"""
from __future__ import annotations

from .base import BBox, OCRLine, OCRPage, OCRProvider, OCRResult, OCRWord


class GoogleVisionOCRProvider(OCRProvider):
    def __init__(self) -> None:
        from google.cloud import vision

        self._client = vision.ImageAnnotatorClient()
        self._vision = vision

    def recognize(self, page_images: list[bytes]) -> OCRResult:
        pages: list[OCRPage] = []
        for page_no, png in enumerate(page_images, start=1):
            image = self._vision.Image(content=png)
            response = self._client.document_text_detection(image=image)
            if response.error.message:
                raise RuntimeError(f"Google Vision OCR failed: {response.error.message}")
            annotation = response.full_text_annotation
            for g_page in annotation.pages:
                lines: list[OCRLine] = []
                for block in g_page.blocks:
                    for paragraph in block.paragraphs:
                        words: list[OCRWord] = []
                        for g_word in paragraph.words:
                            text = "".join(s.text for s in g_word.symbols)
                            words.append(
                                OCRWord(
                                    text=text,
                                    bbox=_vertices_to_bbox(g_word.bounding_box.vertices),
                                    confidence=g_word.confidence,
                                )
                            )
                        if not words:
                            continue
                        bbox = words[0].bbox
                        for w in words[1:]:
                            bbox = bbox.union(w.bbox)
                        conf = sum(w.confidence for w in words) / len(words)
                        lines.append(
                            OCRLine(
                                text=" ".join(w.text for w in words),
                                bbox=bbox,
                                confidence=conf,
                                words=words,
                            )
                        )
                pages.append(
                    OCRPage(
                        page_number=page_no,
                        width=g_page.width,
                        height=g_page.height,
                        lines=lines,
                    )
                )
        return OCRResult(pages=pages)


def _vertices_to_bbox(vertices) -> BBox:
    return BBox.from_points([(v.x, v.y) for v in vertices])
