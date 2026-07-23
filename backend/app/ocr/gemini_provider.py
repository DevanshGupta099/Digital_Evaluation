import json
import fitz
import google.generativeai as genai
from .base import BBox, OCRLine, OCRPage, OCRProvider, OCRResult, OCRWord
from ..config import settings

class GeminiOCRProvider(OCRProvider):
    def __init__(self):
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
        
        # Ensure API key is configured
        genai.configure(api_key=settings.gemini_api_key)
        
        self.model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=(
                "You are an expert OCR engine. Extract all handwritten text from the image, line by line. "
                "For each line, provide the exact transcribed text and its bounding box in [ymin, xmin, ymax, xmax] "
                "format, where coordinates are integers from 0 to 1000 representing scaled positions. "
                "Respond ONLY with a JSON array of line objects. Each object must have 'text' (string) and 'box_2d' (array of 4 ints)."
            ),
            generation_config=genai.GenerationConfig(
                temperature=0.0,
                response_mime_type="application/json",
            )
        )

    def recognize(self, page_images: list[bytes]) -> OCRResult:
        pages = []
        for i, img_bytes in enumerate(page_images):
            # Use PyMuPDF's Pixmap to get image dimensions natively
            pix = fitz.Pixmap(img_bytes)
            width, height = pix.width, pix.height
            
            response = self.model.generate_content([
                {"mime_type": "image/png", "data": img_bytes},
                "Extract text lines and bounding boxes as instructed."
            ])
            
            try:
                lines_data = json.loads(response.text)
                if not isinstance(lines_data, list):
                    # Sometimes LLM might wrap it in a dict e.g. {"lines": [...]}
                    lines_data = lines_data.get("lines", []) if isinstance(lines_data, dict) else []
            except Exception:
                lines_data = []

            ocr_lines = []
            for item in lines_data:
                text = item.get("text", "")
                box = item.get("box_2d", [0, 0, 1000, 1000])
                if not text or not isinstance(box, list) or len(box) != 4:
                    continue
                    
                ymin, xmin, ymax, xmax = box
                
                # Unscale 0-1000 to actual pixels
                x0 = (xmin / 1000.0) * width
                y0 = (ymin / 1000.0) * height
                x1 = (xmax / 1000.0) * width
                y1 = (ymax / 1000.0) * height
                
                # Bounding box invariants
                x0, x1 = min(x0, x1), max(x0, x1)
                y0, y1 = min(y0, y1), max(y0, y1)
                
                # If width or height is 0, add a slight padding to prevent errors
                if x1 <= x0: x1 = x0 + 1
                if y1 <= y0: y1 = y0 + 1

                bbox = BBox(x0, y0, x1, y1)
                
                # Linearly interpolate word boxes for visualization/mapping
                words = []
                tokens = text.split()
                if tokens:
                    word_width = (x1 - x0) / len(tokens)
                    for idx, token in enumerate(tokens):
                        wx0 = x0 + idx * word_width
                        wx1 = wx0 + word_width * 0.95 # Leave small gap
                        words.append(OCRWord(text=token, bbox=BBox(wx0, y0, wx1, y1), confidence=0.9))
                
                ocr_lines.append(OCRLine(text=text, bbox=bbox, confidence=0.9, words=words))

            pages.append(OCRPage(page_number=i + 1, width=width, height=height, lines=ocr_lines))
        
        return OCRResult(pages=pages)
