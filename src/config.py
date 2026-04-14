"""
Central configuration loaded from environment variables / .env file.
All other modules import `settings` from here.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Groq ---
    groq_api_key: str = Field(..., alias="GROQ_API_KEY")

    # --- Models (all served via Groq) ---
    orchestrator_model: str = Field(
        "llama-3.3-70b-versatile", alias="ORCHESTRATOR_MODEL"
    )
    explore_model: str = Field(
        "llama-3.1-8b-instant", alias="EXPLORE_MODEL"
    )
    compactor_model: str = Field(
        "llama-3.1-8b-instant", alias="COMPACTOR_MODEL"
    )

    # --- Context management ---
    context_threshold: float = Field(0.70, alias="CONTEXT_THRESHOLD")
    # llama-3.3-70b-versatile supports 128k context
    orchestrator_context_window: int = Field(
        128_000, alias="ORCHESTRATOR_CONTEXT_WINDOW"
    )

    # --- Repository ---
    repo_path: str = Field(".", alias="REPO_PATH")

    # --- API server ---
    host: str = Field("0.0.0.0", alias="HOST")
    port: int = Field(8000, alias="PORT")


settings = Settings()
