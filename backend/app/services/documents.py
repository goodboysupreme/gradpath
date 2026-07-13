import re
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from typing import Protocol
from xml.etree import ElementTree
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile, ZipInfo

import pypdf.filters as pdf_filters
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader

from app.schemas.documents import (
    DocumentExtractionResponse,
    DocumentFormat,
    DocumentKind,
)

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_REQUEST_BODY_BYTES = MAX_FILE_BYTES + 64 * 1024
MAX_EXTRACTED_CHARACTERS = 250_000
MAX_DOCX_ARCHIVE_ENTRIES = 1_000
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_DOCX_MEMBER_BYTES = 20 * 1024 * 1024
MAX_DOCX_COMPRESSION_RATIO = 100
MAX_DOCX_BLOCKS = 20_000
MAX_DOCX_NESTING_DEPTH = 10
MIN_NATIVE_TEXT_CHARACTERS = 20

PDF_MEDIA_TYPE = "application/pdf"
DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
OCTET_STREAM_MEDIA_TYPE = "application/octet-stream"
DOCX_MAIN_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
)
_ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
_FORBIDDEN_DOCX_PREFIXES = ("word/activex/", "word/embeddings/")
_FORBIDDEN_DOCX_MEMBERS = {"word/vbaproject.bin"}
_XML_DANGER_MARKERS = (b"<!DOCTYPE", b"<!ENTITY")


class DocumentExtractionError(RuntimeError):
    pass


class UnsupportedDocumentType(DocumentExtractionError):
    pass


class DocumentTypeMismatch(DocumentExtractionError):
    pass


class DocumentLimitError(DocumentExtractionError):
    pass


class EncryptedDocumentError(DocumentExtractionError):
    pass


class NoNativeTextError(DocumentExtractionError):
    pass


class UnsafeDocumentPackageError(DocumentExtractionError):
    pass


class DocumentParseError(DocumentExtractionError):
    pass


class _BlockContainer(Protocol):
    def iter_inner_content(self) -> Iterator[Paragraph | Table]: ...


@dataclass
class _DocxExtractionState:
    observed_characters: int = 0
    block_count: int = 0

    def observe_text(self, value: str) -> None:
        self.observed_characters += len(value)
        if self.observed_characters > MAX_EXTRACTED_CHARACTERS:
            raise DocumentLimitError(
                f"Extracted text exceeds the {MAX_EXTRACTED_CHARACTERS} character limit"
            )

    def observe_block(self) -> None:
        self.block_count += 1
        if self.block_count > MAX_DOCX_BLOCKS:
            raise DocumentLimitError("Document structure exceeds safe limits")


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).replace("\r\n", "\n").replace("\r", "\n")
    lines: list[str] = []
    blank_pending = False
    for raw_line in normalized.split("\n"):
        line = re.sub(r"[^\S\t]+", " ", raw_line).strip()
        line = re.sub(r"\t+", "\t", line)
        if line:
            if blank_pending and lines:
                lines.append("")
            lines.append(line)
            blank_pending = False
        elif lines:
            blank_pending = True
    return "\n".join(lines).strip()


def resolve_document_format(
    filename: str,
    content_type: str | None,
    content: bytes,
) -> DocumentFormat:
    extension = PurePosixPath(filename.replace("\\", "/")).suffix.casefold()
    extension_format = {
        ".pdf": DocumentFormat.PDF,
        ".docx": DocumentFormat.DOCX,
    }.get(extension)
    if extension_format is None:
        raise UnsupportedDocumentType("Unsupported document type")

    normalized_media_type = (content_type or "").partition(";")[0].strip().casefold()
    expected_media_type = {
        DocumentFormat.PDF: PDF_MEDIA_TYPE,
        DocumentFormat.DOCX: DOCX_MEDIA_TYPE,
    }[extension_format]
    if normalized_media_type not in {expected_media_type, OCTET_STREAM_MEDIA_TYPE}:
        raise UnsupportedDocumentType("Unsupported document type")

    if content.startswith(b"%PDF-"):
        detected_format = DocumentFormat.PDF
    elif content.startswith(_ZIP_SIGNATURES):
        detected_format = DocumentFormat.DOCX
    else:
        raise DocumentTypeMismatch("Document type does not match its content")
    if detected_format is not extension_format:
        raise DocumentTypeMismatch("Document type does not match its content")
    return detected_format


def _page_limit(kind: DocumentKind) -> int:
    return 10 if kind is DocumentKind.RESUME else 30


def _page_limit_message(kind: DocumentKind, limit: int) -> str:
    label = "resume" if kind is DocumentKind.RESUME else "JD"
    return f"Document exceeds the {label} page limit of {limit}"


def _validated_text(value: str) -> str:
    normalized = _normalize_text(value)
    if len(normalized) > MAX_EXTRACTED_CHARACTERS:
        raise DocumentLimitError(
            f"Extracted text exceeds the {MAX_EXTRACTED_CHARACTERS} character limit"
        )
    if len(normalized) < MIN_NATIVE_TEXT_CHARACTERS:
        raise NoNativeTextError("Document has no machine-readable text; OCR is not enabled")
    return normalized


def _extract_pdf(content: bytes, kind: DocumentKind) -> DocumentExtractionResponse:
    try:
        pdf_filters.ZLIB_MAX_OUTPUT_LENGTH = MAX_DOCX_MEMBER_BYTES
        reader = PdfReader(BytesIO(content), strict=True)
        if reader.is_encrypted:
            raise EncryptedDocumentError("Encrypted documents are not supported")
        page_count = len(reader.pages)
        limit = _page_limit(kind)
        if page_count > limit:
            raise DocumentLimitError(_page_limit_message(kind, limit))

        pages: list[str] = []
        observed_characters = 0
        for page in reader.pages:
            page_text = _normalize_text(page.extract_text(extraction_mode="layout") or "")
            if page_text:
                observed_characters += len(page_text)
                if observed_characters > MAX_EXTRACTED_CHARACTERS:
                    raise DocumentLimitError(
                        f"Extracted text exceeds the {MAX_EXTRACTED_CHARACTERS} character limit"
                    )
                pages.append(page_text)
        text = _validated_text("\n\n".join(pages))
        return DocumentExtractionResponse(
            document_kind=kind,
            document_format=DocumentFormat.PDF,
            text=text,
            page_count=page_count,
            character_count=len(text),
        )
    except DocumentExtractionError:
        raise
    except Exception as exc:
        raise DocumentParseError("Document could not be parsed") from exc


def _is_unsafe_archive_path(name: str) -> bool:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    return (
        name.startswith(("/", "\\"))
        or ".." in path.parts
        or (bool(path.parts) and ":" in path.parts[0])
    )


def _validate_docx_member(info: ZipInfo) -> None:
    normalized_name = info.filename.replace("\\", "/").casefold()
    if _is_unsafe_archive_path(info.filename):
        raise UnsafeDocumentPackageError("Document package is unsafe")
    if info.flag_bits & 0x1:
        raise EncryptedDocumentError("Encrypted documents are not supported")
    if info.compress_type not in {ZIP_STORED, ZIP_DEFLATED}:
        raise UnsafeDocumentPackageError("Document package is unsafe")
    if info.file_size > MAX_DOCX_MEMBER_BYTES:
        raise DocumentLimitError("Document archive exceeds safe expansion limits")
    if info.file_size and info.file_size / max(info.compress_size, 1) > MAX_DOCX_COMPRESSION_RATIO:
        raise DocumentLimitError("Document archive exceeds safe expansion limits")
    if normalized_name in _FORBIDDEN_DOCX_MEMBERS or normalized_name.startswith(
        _FORBIDDEN_DOCX_PREFIXES
    ):
        raise UnsafeDocumentPackageError("Document package is unsafe")


def _validate_docx_archive(archive: ZipFile) -> None:
    members = archive.infolist()
    if len(members) > MAX_DOCX_ARCHIVE_ENTRIES:
        raise DocumentLimitError("Document archive exceeds safe expansion limits")

    names: set[str] = set()
    total_uncompressed = 0
    for info in members:
        normalized_name = info.filename.replace("\\", "/").casefold()
        if normalized_name in names:
            raise UnsafeDocumentPackageError("Document package is unsafe")
        names.add(normalized_name)
        _validate_docx_member(info)
        total_uncompressed += info.file_size
        if total_uncompressed > MAX_DOCX_UNCOMPRESSED_BYTES:
            raise DocumentLimitError("Document archive exceeds safe expansion limits")

    required_names = {"[content_types].xml", "word/document.xml"}
    if not required_names.issubset(names):
        raise DocumentTypeMismatch("Document type does not match its content")

    for info in members:
        normalized_name = info.filename.replace("\\", "/").casefold()
        if normalized_name.endswith((".xml", ".rels")):
            xml_content = archive.read(info)
            upper_content = xml_content.upper()
            if any(marker in upper_content for marker in _XML_DANGER_MARKERS):
                raise UnsafeDocumentPackageError("Document package is unsafe")

    try:
        content_types = ElementTree.fromstring(archive.read("[Content_Types].xml"))
    except (ElementTree.ParseError, KeyError) as exc:
        raise DocumentParseError("Document could not be parsed") from exc
    main_content_type = next(
        (
            element.attrib.get("ContentType")
            for element in content_types
            if element.attrib.get("PartName", "").casefold() == "/word/document.xml"
        ),
        None,
    )
    if main_content_type != DOCX_MAIN_CONTENT_TYPE:
        raise DocumentTypeMismatch("Document type does not match its content")


def _extract_table_lines(
    table: Table,
    state: _DocxExtractionState,
    depth: int,
) -> list[str]:
    if depth > MAX_DOCX_NESTING_DEPTH:
        raise DocumentLimitError("Document structure exceeds safe limits")
    lines: list[str] = []
    for row in table.rows:
        state.observe_block()
        cells: list[str] = []
        for cell in row.cells:
            cell_lines = _extract_container_lines(cell, state, depth + 1)
            cells.append(" ".join(cell_lines))
        line = "\t".join(cells).strip()
        if line:
            lines.append(line)
    return lines


def _extract_container_lines(
    container: _BlockContainer,
    state: _DocxExtractionState,
    depth: int = 0,
) -> list[str]:
    lines: list[str] = []
    for block in container.iter_inner_content():
        state.observe_block()
        if isinstance(block, Paragraph):
            text = _normalize_text(block.text)
            if text:
                state.observe_text(text)
                lines.append(text)
        else:
            lines.extend(_extract_table_lines(block, state, depth))
    return lines


def _extract_docx(content: bytes, kind: DocumentKind) -> DocumentExtractionResponse:
    try:
        with ZipFile(BytesIO(content)) as archive:
            _validate_docx_archive(archive)

        document = Document(BytesIO(content))
        state = _DocxExtractionState()
        header_lines: list[str] = []
        footer_lines: list[str] = []
        seen_header_parts: set[int] = set()
        seen_footer_parts: set[int] = set()
        for section in document.sections:
            for header in (section.header, section.first_page_header, section.even_page_header):
                part_identity = id(header.part)
                if part_identity not in seen_header_parts:
                    seen_header_parts.add(part_identity)
                    header_lines.extend(_extract_container_lines(header, state))
            for footer in (section.footer, section.first_page_footer, section.even_page_footer):
                part_identity = id(footer.part)
                if part_identity not in seen_footer_parts:
                    seen_footer_parts.add(part_identity)
                    footer_lines.extend(_extract_container_lines(footer, state))

        body_lines = _extract_container_lines(document, state)
        text = _validated_text("\n".join((*header_lines, *body_lines, *footer_lines)))
        return DocumentExtractionResponse(
            document_kind=kind,
            document_format=DocumentFormat.DOCX,
            text=text,
            page_count=None,
            character_count=len(text),
        )
    except DocumentExtractionError:
        raise
    except BadZipFile as exc:
        raise DocumentParseError("Document could not be parsed") from exc
    except Exception as exc:
        raise DocumentParseError("Document could not be parsed") from exc


def extract_document(
    content: bytes,
    document_format: DocumentFormat,
    kind: DocumentKind,
) -> DocumentExtractionResponse:
    if document_format is DocumentFormat.PDF:
        return _extract_pdf(content, kind)
    return _extract_docx(content, kind)
