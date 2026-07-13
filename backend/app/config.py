from functools import lru_cache
from secrets import compare_digest
from typing import Self

from pydantic import Field, SecretStr, model_validator
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
    source_ingestion_token: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
    openrouter_model: str | None = Field(default=None, max_length=200)
    openrouter_site_url: str = Field(
        default="http://localhost:3000",
        min_length=8,
        max_length=2_000,
    )
    openrouter_app_name: str = Field(default="GradPath", min_length=2, max_length=100)
    analysis_timeout_seconds: float = Field(default=45, ge=5, le=55)

    @model_validator(mode="after")
    def trust_credentials_are_distinct(self) -> Self:
        internal_token = (
            self.internal_api_token.get_secret_value().strip()
            if self.internal_api_token is not None
            else ""
        )
        source_token = (
            self.source_ingestion_token.get_secret_value().strip()
            if self.source_ingestion_token is not None
            else ""
        )
        if internal_token and source_token and compare_digest(internal_token, source_token):
            raise ValueError("Internal and source ingestion tokens must be different")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
