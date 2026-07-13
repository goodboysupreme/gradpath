from collections.abc import Callable
from typing import Any

import pytest
from anyio import Event, create_task_group, run, sleep

import app.services.document_executor as executor_module
from app.schemas.documents import (
    DocumentExtractionResponse,
    DocumentFormat,
    DocumentKind,
)
from app.services.document_executor import (
    DocumentExtractionCapacityError,
    DocumentExtractionExecutionError,
    DocumentExtractionExecutor,
)


def extracted_response() -> DocumentExtractionResponse:
    text = "Native document text with sufficient content."
    return DocumentExtractionResponse(
        document_kind=DocumentKind.RESUME,
        document_format=DocumentFormat.PDF,
        text=text,
        page_count=1,
        character_count=len(text),
    )


def test_document_executor_rejects_work_when_its_capacity_is_full(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        started = Event()
        release = Event()

        async def blocked_run_sync(
            function: Callable[..., Any],
            *args: object,
            cancellable: bool = False,
            limiter: object | None = None,
        ) -> DocumentExtractionResponse:
            del function, args, cancellable, limiter
            started.set()
            await release.wait()
            return extracted_response()

        monkeypatch.setattr(executor_module, "run_sync", blocked_run_sync)
        executor = DocumentExtractionExecutor(concurrency=1, timeout_seconds=1)

        async def first_extraction() -> None:
            await executor.extract(b"document", DocumentFormat.PDF, DocumentKind.RESUME)

        async with create_task_group() as task_group:
            task_group.start_soon(first_extraction)
            await started.wait()
            with pytest.raises(DocumentExtractionCapacityError):
                await executor.extract(b"document", DocumentFormat.PDF, DocumentKind.RESUME)
            release.set()

    run(scenario)


def test_document_executor_converts_timeout_to_sanitized_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def slow_run_sync(
        function: Callable[..., Any],
        *args: object,
        cancellable: bool = False,
        limiter: object | None = None,
    ) -> DocumentExtractionResponse:
        del function, args, cancellable, limiter
        await sleep(1)
        return extracted_response()

    monkeypatch.setattr(executor_module, "run_sync", slow_run_sync)
    executor = DocumentExtractionExecutor(concurrency=1, timeout_seconds=0.01)

    async def scenario() -> None:
        with pytest.raises(DocumentExtractionExecutionError, match="timed out"):
            await executor.extract(b"document", DocumentFormat.PDF, DocumentKind.RESUME)

    run(scenario)
