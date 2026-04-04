"""Application configuration via environment variables and Pydantic Settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """TenderClaw application settings loaded from env / .env file."""

    model_config = SettingsConfigDict(
        env_prefix="TENDERCLAW_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server
    host: str = "localhost"
    port: int = 7000
    dev: bool = False

    # Default AI model
    default_model: str = "claude-sonnet-4-20250514"

    # Logging
    log_level: str = "INFO"

    # API keys (no prefix — standard env var names)
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    xai_api_key: str = Field(default="", alias="XAI_API_KEY")
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")


# Singleton — import this everywhere
settings = Settings()
