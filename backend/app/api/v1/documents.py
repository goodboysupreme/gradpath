from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.dependencies import (
    get_document_extraction_executor,
    require_internal_authentication,
)
from app.schemas.documents import DocumentExtractionResponse, DocumentKind
from app.services.document_executor import (
    DocumentExtractionCapacityError,
    DocumentExtractionExecutionError,
    DocumentExtractionExecutor,
)
from app.services.documents import (
    MAX_FILE_BYTES,
    DocumentLimitError,
    DocumentParseError,
    DocumentTypeMismatch,
    EncryptedDocumentError,
    NoNativeTextError,
    UnsafeDocumentPackageError,
    UnsupportedDocumentType,
    resolve_document_format,
)

router = APIRouter()
_UPLOAD_CHUNK_BYTES = 64 * 1024


async def _read_bounded_upload(upload: UploadFile) -> bytes:
    content = bytearray()
    while True:
        remaining = MAX_FILE_BYTES - len(content)
        chunk = await upload.read(min(_UPLOAD_CHUNK_BYTES, remaining + 1))
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > MAX_FILE_BYTES:
            raise DocumentLimitError("Uploaded file exceeds the 10 MiB limit")
    if not content:
        raise DocumentParseError("Uploaded file is empty")
    return bytes(content)


@router.post(
    "/documents/extract",
    response_model=DocumentExtractionResponse,
    dependencies=[Depends(require_internal_authentication)],
)
async def extract_document_text(
    request: Request,
    executor: Annotated[
        DocumentExtractionExecutor,
        Depends(get_document_extraction_executor),
    ],
) -> DocumentExtractionResponse:
    try:
        form = await request.form(max_files=1, max_fields=1, max_part_size=1_024)
    except StarletteHTTPException as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid document upload form",
        ) from exc

    try:
        file_values = form.getlist("file")
        if len(file_values) != 1 or not isinstance(file_values[0], UploadFile):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Exactly one document file is required",
            )
        kind_values = form.getlist("kind")
        if len(kind_values) != 1 or not isinstance(kind_values[0], str):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Exactly one document kind is required",
            )
        if len(form.multi_items()) != 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Only kind and file fields are accepted",
            )

        try:
            kind = DocumentKind(kind_values[0])
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Unsupported document kind",
            ) from exc

        upload = file_values[0]
        filename = upload.filename or ""
        content_type = upload.content_type
        try:
            try:
                content = await _read_bounded_upload(upload)
            except DocumentLimitError as exc:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=str(exc),
                ) from exc
            except DocumentParseError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=str(exc),
                ) from exc
        finally:
            await upload.close()

        try:
            document_format = resolve_document_format(
                filename,
                content_type,
                content,
            )
            return await executor.extract(content, document_format, kind)
        except (UnsupportedDocumentType, DocumentTypeMismatch) as exc:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=str(exc),
            ) from exc
        except DocumentLimitError as exc:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=str(exc),
            ) from exc
        except (
            DocumentParseError,
            EncryptedDocumentError,
            NoNativeTextError,
            UnsafeDocumentPackageError,
        ) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc
        except DocumentExtractionCapacityError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Document extraction capacity is exhausted",
                headers={"Retry-After": "1"},
            ) from exc
        except DocumentExtractionExecutionError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Document extraction worker failed",
            ) from exc
    finally:
        await form.close()
