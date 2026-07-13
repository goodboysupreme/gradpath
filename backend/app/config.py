import re
from functools import lru_cache
from secrets import compare_digest
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schemas.request_context import MAX_HMAC_SECRET_BYTES, MIN_HMAC_SECRET_BYTES

_REQUEST_CONTEXT_KEY_ID = re.compile(
    r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,62}[A-Za-z0-9])?",
    re.ASCII,
)
_MAX_REQUEST_CONTEXT_KEYS = 16


def _secret_bytes(secret: SecretStr | None) -> bytes | None:
    if secret is None:
        return None
    value = secret.get_secret_value().strip()
    return value.encode("utf-8") if value else None


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
    request_context_signing_keys: dict[str, SecretStr] = Field(
        default_factory=dict,
        max_length=_MAX_REQUEST_CONTEXT_KEYS,
    )
    audit_pseudonym_secret: SecretStr | None = None
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
        credentials: list[tuple[str, bytes]] = []
        legacy_credentials = (
            ("internal API token", self.internal_api_token),
            ("source ingestion token", self.source_ingestion_token),
            ("OpenRouter API key", self.openrouter_api_key),
        )
        for label, secret in legacy_credentials:
            value = _secret_bytes(secret)
            if value is not None:
                credentials.append((label, value))

        for key_id, secret in self.request_context_signing_keys.items():
            if _REQUEST_CONTEXT_KEY_ID.fullmatch(key_id) is None:
                raise ValueError(
                    "Request-context key IDs must be 1-64 ASCII letters, digits, dots, "
                    "underscores, or hyphens and must start and end with a letter or digit"
                )
            value = secret.get_secret_value()
            secret_length = len(value.encode("utf-8"))
            if (
                value != value.strip()
                or not MIN_HMAC_SECRET_BYTES <= secret_length <= MAX_HMAC_SECRET_BYTES
            ):
                raise ValueError(
                    "Request-context signing secrets must be 32-1,024 UTF-8 bytes and have "
                    "no surrounding whitespace"
                )
            credentials.append((f"request-context signing key {key_id}", value.encode("utf-8")))

        if self.audit_pseudonym_secret is not None:
            audit_secret = self.audit_pseudonym_secret.get_secret_value()
            if (
                audit_secret != audit_secret.strip()
                or not MIN_HMAC_SECRET_BYTES
                <= len(audit_secret.encode("utf-8"))
                <= MAX_HMAC_SECRET_BYTES
            ):
                raise ValueError(
                    "The audit pseudonym secret must be 32-1,024 UTF-8 bytes and have no "
                    "surrounding whitespace"
                )
            credentials.append(("audit pseudonym secret", audit_secret.encode("utf-8")))

        for index, (label, value) in enumerate(credentials):
            for other_label, other_value in credentials[index + 1 :]:
                if compare_digest(value, other_value):
                    raise ValueError(
                        f"Configured security credentials must be distinct: {label} and "
                        f"{other_label}"
                    )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
