import fitz

from app.annotation.annotator import Annotation, AnnotationKind, ScriptAnnotator
from app.ocr.base import BBox, OCRLine, OCRPage, OCRResult


def _blank_pdf(pages: int = 1) -> bytes:
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page(width=612, height=792)
    return doc.tobytes()


def _ocr(pages: int = 1) -> OCRResult:
    return OCRResult(pages=[
        OCRPage(page_number=i + 1, width=2550, height=3300,
                lines=[OCRLine(text="hello world", bbox=BBox(200, 300, 1200, 360),
                               confidence=0.9)])
        for i in range(pages)
    ])


def test_annotations_add_drawings():
    pdf = _blank_pdf()
    annotator = ScriptAnnotator(pdf, _ocr())
    annotator.apply([
        Annotation(AnnotationKind.TICK, 1, BBox(200, 300, 1200, 360)),
        Annotation(AnnotationKind.CROSS, 1, BBox(200, 500, 1200, 560)),
        Annotation(AnnotationKind.UNDERLINE, 1, BBox(200, 700, 1200, 760)),
        Annotation(AnnotationKind.MARKS_BADGE, 1, BBox(200, 300, 1200, 360), label="3/5"),
    ])
    annotator.add_total(7.5, 10)
    out = annotator.tobytes()
    with fitz.open(stream=out, filetype="pdf") as doc:
        drawings = doc[0].get_drawings()
        assert len(drawings) >= 5  # tick(2 lines merged), cross, underline, circle, total box
        text = doc[0].get_text()
        assert "3/5" in text
        assert "Total: 7.5 / 10" in text


def test_annotation_on_missing_page_is_skipped():
    annotator = ScriptAnnotator(_blank_pdf(1), _ocr(1))
    annotator.apply([Annotation(AnnotationKind.TICK, 5, BBox(0, 0, 10, 10))])
    with fitz.open(stream=annotator.tobytes(), filetype="pdf") as doc:
        assert len(doc) == 1


def test_original_untouched_annotation_on_copy():
    pdf = _blank_pdf()
    annotator = ScriptAnnotator(pdf, _ocr())
    annotator.apply([Annotation(AnnotationKind.CROSS, 1, BBox(200, 300, 1200, 360))])
    out = annotator.tobytes()
    assert out != pdf
    with fitz.open(stream=pdf, filetype="pdf") as doc:
        assert doc[0].get_drawings() == []
