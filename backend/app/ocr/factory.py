from __future__ import annotations

from ..config import settings
from .base import OCRProvider


def get_ocr_provider(name: str | None = None) -> OCRProvider:
    name = name or settings.ocr_provider
    if name == "azure":
        from .azure_provider import AzureOCRProvider

        return AzureOCRProvider(settings.azure_docint_endpoint, settings.azure_docint_key)
    if name == "google":
        from .google_provider import GoogleVisionOCRProvider

        return GoogleVisionOCRProvider()
    if name == "mock":
        from .mock_provider import MockOCRProvider

        return MockOCRProvider()
    raise ValueError(f"Unknown OCR provider: {name}")
