"""Azure AI Document Intelligence adapter (prebuilt-read model, handwriting-capable).

Azure returns polygons in the unit of the submitted image (pixels for PNG
input), so coordinates map directly into our pixel-space BBox.
"""
from __future__ import annotations

from .base import BBox, OCRLine, OCRPage, OCRProvider, OCRResult, OCRWord


class AzureOCRProvider(OCRProvider):
    def __init__(self, endpoint: str, key: str) -> None:
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.core.credentials import AzureKeyCredential

        self._client = DocumentIntelligenceClient(endpoint, AzureKeyCredential(key))

    def recognize(self, page_images: list[bytes]) -> OCRResult:
        pages: list[OCRPage] = []
        for page_no, png in enumerate(page_images, start=1):
            poller = self._client.begin_analyze_document("prebuilt-read", body=png)
            result = poller.result()
            for az_page in result.pages:
                words = [
                    OCRWord(
                        text=w.content,
                        bbox=_polygon_to_bbox(w.polygon),
                        confidence=w.confidence if w.confidence is not None else 0.0,
                    )
                    for w in (az_page.words or [])
                ]
                lines: list[OCRLine] = []
                for az_line in az_page.lines or []:
                    bbox = _polygon_to_bbox(az_line.polygon)
                    line_words = [w for w in words if _overlaps(w.bbox, bbox)]
                    conf = (
                        sum(w.confidence for w in line_words) / len(line_words)
                        if line_words
                        else 0.0
                    )
                    lines.append(
                        OCRLine(text=az_line.content, bbox=bbox, confidence=conf, words=line_words)
                    )
                pages.append(
                    OCRPage(
                        page_number=page_no,
                        width=az_page.width or 0,
                        height=az_page.height or 0,
                        lines=lines,
                    )
                )
        return OCRResult(pages=pages)


def _polygon_to_bbox(polygon: list[float]) -> BBox:
    points = [(polygon[i], polygon[i + 1]) for i in range(0, len(polygon), 2)]
    return BBox.from_points(points)


def _overlaps(inner: BBox, outer: BBox) -> bool:
    cx, cy = inner.center
    return outer.x0 <= cx <= outer.x1 and outer.y0 <= cy <= outer.y1
