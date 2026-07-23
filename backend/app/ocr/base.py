"""Provider-agnostic OCR types.

Every provider adapter must normalize its output into these structures so the
rest of the pipeline (segmentation, grading evidence lookup, PDF annotation)
works from a single representation: text + pixel-space bounding boxes +
confidence, per page.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class BBox:
    """Axis-aligned bounding box in rendered-image pixel space (origin top-left)."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2)

    def union(self, other: "BBox") -> "BBox":
        return BBox(
            min(self.x0, other.x0),
            min(self.y0, other.y0),
            max(self.x1, other.x1),
            max(self.y1, other.y1),
        )

    @staticmethod
    def from_points(points: list[tuple[float, float]]) -> "BBox":
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        return BBox(min(xs), min(ys), max(xs), max(ys))


@dataclass
class OCRWord:
    text: str
    bbox: BBox
    confidence: float


@dataclass
class OCRLine:
    text: str
    bbox: BBox
    confidence: float
    words: list[OCRWord] = field(default_factory=list)


@dataclass
class OCRPage:
    page_number: int  # 1-based
    width: float  # rendered image width in pixels
    height: float
    lines: list[OCRLine] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)


@dataclass
class OCRResult:
    pages: list[OCRPage]

    @property
    def text(self) -> str:
        return "\n\n".join(page.text for page in self.pages)

    def numbered_lines(self) -> list[tuple[int, int, OCRLine]]:
        """Return (global_line_index, page_number, line) for evidence citation.

        Grading prompts reference lines by this global index; the annotator maps
        the index back to a bbox on the right page.
        """
        out: list[tuple[int, int, OCRLine]] = []
        idx = 0
        for page in self.pages:
            for line in page.lines:
                out.append((idx, page.page_number, line))
                idx += 1
        return out


class OCRProvider(ABC):
    """Interface all OCR backends implement."""

    @abstractmethod
    def recognize(self, page_images: list[bytes]) -> OCRResult:
        """Run OCR over rendered page images (PNG bytes), one per page."""
        raise NotImplementedError
