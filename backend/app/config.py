from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings, loaded from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "sqlite:///./grader.db"
    storage_dir: str = "./storage"

    # OCR provider: "azure" | "google" | "mock"
    ocr_provider: str = Field(default="gemini")
    azure_docint_endpoint: str = ""
    azure_docint_key: str = ""
    google_application_credentials: str = ""

    # --- Stage 4: Dual-pass grading LLMs ---
    # Pass 1 (primary): Google Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-pro"

    # Pass 2 (independent cross-check): Groq
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"

    # Shared grading parameters
    grading_temperature: float = 0.0
    grading_passes: int = 2
    # Marks disagreement (fraction of question total) above which a question is flagged.
    disagreement_threshold: float = 0.15
    # Minimum evaluation confidence before a question requires human review.
    confidence_threshold: float = 0.75
    # Minimum OCR word confidence before text is considered legible.
    ocr_confidence_threshold: float = 0.60

    render_dpi: int = 300


settings = Settings()
