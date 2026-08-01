from abc import ABC, abstractmethod
import asyncio
from app.ingestion.schemas import NormalizedOCRResponse, NormalizedOCRWord

class OCRProvider(ABC):
    @abstractmethod
    async def process_image(self, image_path: str) -> NormalizedOCRResponse:
        """
        Processes an image and returns the normalized OCR data.
        """
        pass

class MockOCRProvider(OCRProvider):
    async def process_image(self, image_path: str) -> NormalizedOCRResponse:
        """
        A mock provider that simulates network delay and returns dummy data.
        Useful for testing the pipeline without incurring API costs.
        """
        # Simulate network delay
        await asyncio.sleep(0.5)
        
        # Return dummy normalized data
        words = [
            NormalizedOCRWord(
                text="Mock",
                bbox=[10.0, 10.0, 50.0, 20.0],
                line_id="line_1",
                confidence=0.99
            ),
            NormalizedOCRWord(
                text="OCR",
                bbox=[70.0, 10.0, 40.0, 20.0],
                line_id="line_1",
                confidence=0.95
            )
        ]
        
        return NormalizedOCRResponse(
            words=words,
            reading_order=["line_1"]
        )

# Factory to get the active provider based on config
def get_ocr_provider() -> OCRProvider:
    # In the future, this can read from settings.OCR_PROVIDER and return
    # GeminiOCRProvider() or GoogleCloudVisionProvider()
    return MockOCRProvider()
