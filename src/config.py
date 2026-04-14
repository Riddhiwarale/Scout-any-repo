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

    # --- Anthropic ---
    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")

    # --- Models ---
    orchestrator_model: str = Field(
        "claude-3-7-sonnet-20250219", alias="ORCHESTRATOR_MODEL"
    )
    explore_model: str = Field(
        "claude-3-5-haiku-20241022", alias="EXPLORE_MODEL"
    )
    compactor_model: str = Field(
        "claude-3-5-haiku-20241022", alias="COMPACTOR_MODEL"
    )

    # --- Context management ---
    context_threshold: float = Field(0.70, alias="CONTEXT_THRESHOLD")
    orchestrator_context_window: int = Field(
        200_000, alias="ORCHESTRATOR_CONTEXT_WINDOW"
    )

    # --- Repository ---
    repo_path: str = Field(".", alias="REPO_PATH")

    # --- API server ---
    host: str = Field("0.0.0.0", alias="HOST")
    port: int = Field(8000, alias="PORT")


settings = Settings()
