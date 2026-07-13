from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from app.schemas.base import CamelContractModel


class DocumentKind(StrEnum):
    RESUME = "resume"
    JD = "jd"


class DocumentFormat(StrEnum):
    PDF = "pdf"
    DOCX = "docx"


class DocumentExtractionResponse(CamelContractModel):
    document_kind: DocumentKind
    document_format: DocumentFormat
    text: str = Field(min_length=1, max_length=250_000)
    page_count: int | None = Field(default=None, ge=1, le=30)
    character_count: int = Field(ge=1, le=250_000)
    extraction_method: Literal["native_text"] = "native_text"
    layout_preserved: Literal[False] = False
    extraction_version: Literal["native-text-v1"] = "native-text-v1"

    @model_validator(mode="after")
    def metadata_matches_text_and_format(self) -> "DocumentExtractionResponse":
        if self.character_count != len(self.text):
            raise ValueError("character_count must equal the extracted text length")
        if self.document_format is DocumentFormat.PDF and self.page_count is None:
            raise ValueError("PDF extraction requires a page count")
        if self.document_format is DocumentFormat.DOCX and self.page_count is not None:
            raise ValueError("DOCX extraction cannot claim a rendered page count")
        return self
