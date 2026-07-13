from anyio import BrokenWorkerProcess, CapacityLimiter, WouldBlock, fail_after
from anyio.to_process import run_sync

from app.schemas.documents import DocumentExtractionResponse, DocumentFormat, DocumentKind
from app.services.documents import extract_document


class DocumentExtractionCapacityError(RuntimeError):
    pass


class DocumentExtractionExecutionError(RuntimeError):
    pass


class DocumentExtractionExecutor:
    def __init__(self, *, concurrency: int = 2, timeout_seconds: float = 15) -> None:
        self._limiter = CapacityLimiter(concurrency)
        self._timeout_seconds = timeout_seconds

    async def extract(
        self,
        content: bytes,
        document_format: DocumentFormat,
        kind: DocumentKind,
    ) -> DocumentExtractionResponse:
        try:
            self._limiter.acquire_nowait()
        except WouldBlock as exc:
            raise DocumentExtractionCapacityError(
                "Document extraction capacity is exhausted"
            ) from exc

        try:
            try:
                with fail_after(self._timeout_seconds):
                    return await run_sync(
                        extract_document,
                        content,
                        document_format,
                        kind,
                        cancellable=True,
                    )
            except TimeoutError as exc:
                raise DocumentExtractionExecutionError("Document extraction timed out") from exc
            except BrokenWorkerProcess as exc:
                raise DocumentExtractionExecutionError("Document extraction worker failed") from exc
        finally:
            self._limiter.release()
