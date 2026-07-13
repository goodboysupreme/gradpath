from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="GRADPATH_API_",
        extra="ignore",
    )

    app_name: str = "GradPath API"
    app_version: str = "0.1.0"
    cors_origins: tuple[str, ...] = ("http://localhost:3000",)
    internal_api_token: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
    openrouter_model: str | None = Field(default=None, max_length=200)
    openrouter_site_url: str = Field(
        default="http://localhost:3000",
        min_length=8,
        max_length=2_000,
    )
    openrouter_app_name: str = Field(default="GradPath", min_length=2, max_length=100)
    analysis_timeout_seconds: float = Field(default=45, ge=5, le=55)


@lru_cache
def get_settings() -> Settings:
    return Settings()
