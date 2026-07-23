from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "sqlite:///./grader.db"
    storage_dir: str = "./storage"

    # OCR provider: "azure" | "google" | "mock"
    ocr_provider: str = "mock"
    azure_docint_endpoint: str = ""
    azure_docint_key: str = ""
    google_application_credentials: str = ""

    anthropic_api_key: str = ""
    grading_model: str = "claude-sonnet-4-20250514"
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
