from __future__ import annotations

import logging
from typing import Optional

from api.client import api_client
from api.errors import ApiError, ErrorCode
from api.models import DocumentIngestionResponse
from app import state
from app.state import IngestionRecord
from utils.formatters import format_source_label

logger = logging.getLogger(__name__)


class IngestionOutcome:
    def __init__(
        self,
        *,
        source: str,
        kind: str,
        response: Optional[DocumentIngestionResponse] = None,
        error: Optional[ApiError] = None,
    ) -> None:
        self.source = source
        self.kind = kind
        self.response = response
        self.error = error

    @property
    def succeeded(self) -> bool:
        return self.response is not None and self.response.chunks_persisted > 0

    @property
    def completed_without_content(self) -> bool:
        return self.response is not None and self.response.chunks_persisted == 0

    @property
    def failed(self) -> bool:
        return self.error is not None

    @property
    def chunks(self) -> int:
        return self.response.chunks_persisted if self.response else 0

    @property
    def documents(self) -> int:
        return self.response.documents_processed if self.response else 0

    @property
    def elapsed_sec(self) -> float:
        return self.response.elapsed_time_sec if self.response else 0.0

    @property
    def warnings(self) -> list[str]:
        return list(self.response.warnings) if self.response else []

    @property
    def label(self) -> str:
        return format_source_label(self.source)

    @property
    def message(self) -> str:
        if self.error is not None:
            return _error_message(self.error, self.kind)

        if self.completed_without_content:
            return _empty_message(self.kind)

        return (
            f"{self.chunks:,} chunks stored from "
            f"{self.documents} document{'s' if self.documents != 1 else ''} "
            f"in {self.elapsed_sec:.1f}s"
        )


def _error_message(exc: ApiError, kind: str) -> str:
    if exc.code == ErrorCode.UNSUPPORTED_MEDIA_TYPE:
        return "That file type is not supported by the ingestion pipeline."

    if exc.code == ErrorCode.INVALID_FILE_TYPE:
        return exc.message

    if exc.code == ErrorCode.FILE_TOO_LARGE:
        return exc.message

    if exc.code == ErrorCode.INVALID_URL:
        return exc.message

    if exc.is_cold_start_suspect:
        noun = "page" if kind == "url" else "file"
        return (
            f"The backend did not finish processing this {noun} in time. "
            "Large sources and cold starts can both cause this — try again."
        )

    if exc.code == ErrorCode.INTERNAL_ERROR:
        if kind == "url":
            return (
                "The server could not process that page. It may be unreachable, "
                "protected, or contain no extractable text."
            )
        return (
            "The server could not process that file. It may be corrupted, "
            "encrypted, or contain no extractable text."
        )

    return exc.message


def _empty_message(kind: str) -> str:
    if kind == "url":
        return (
            "The page was fetched but produced no usable text. "
            "It may rely on JavaScript rendering or block automated access."
        )
    return (
        "The file was read but produced no usable text. "
        "It may be a scanned image without an embedded text layer."
    )


def _record_outcome(outcome: IngestionOutcome) -> IngestionRecord:
    record = IngestionRecord(
        source=outcome.source,
        kind=outcome.kind,
        succeeded=outcome.succeeded,
        documents_processed=outcome.documents,
        chunks_persisted=outcome.chunks,
        elapsed_time_sec=outcome.elapsed_sec,
        warnings=outcome.warnings,
        error=outcome.message if (outcome.failed or outcome.completed_without_content) else None,
    )

    state.append_ingestion(record)
    return record


async def ingest_url(source: str) -> IngestionOutcome:
    logger.info("Ingesting URL: %s", source)

    try:
        response = await api_client.ingest_url(source)
    except ApiError as exc:
        logger.warning(
            "URL ingestion failed | source=%s | code=%s | request_id=%s",
            source, exc.code, exc.request_id,
        )
        outcome = IngestionOutcome(source=source, kind="url", error=exc)
        _record_outcome(outcome)
        return outcome
    except Exception:
        logger.exception("Unexpected failure ingesting URL %s", source)
        outcome = IngestionOutcome(
            source=source,
            kind="url",
            error=ApiError.client_side(ErrorCode.UNEXPECTED),
        )
        _record_outcome(outcome)
        return outcome

    outcome = IngestionOutcome(source=source, kind="url", response=response)

    logger.info(
        "URL ingestion complete | source=%s | docs=%d | chunks=%d | %.1fs",
        source, response.documents_processed, response.chunks_persisted,
        response.elapsed_time_sec,
    )

    _record_outcome(outcome)
    return outcome


async def ingest_file(
    filename: str,
    content: bytes,
    content_type: Optional[str] = None,
) -> IngestionOutcome:
    logger.info("Ingesting file: %s (%d bytes)", filename, len(content))

    try:
        response = await api_client.ingest_file(
            filename=filename,
            content=content,
            content_type=content_type,
        )
    except ApiError as exc:
        logger.warning(
            "File ingestion failed | file=%s | code=%s | request_id=%s",
            filename, exc.code, exc.request_id,
        )
        outcome = IngestionOutcome(source=filename, kind="file", error=exc)
        _record_outcome(outcome)
        return outcome
    except Exception:
        logger.exception("Unexpected failure ingesting file %s", filename)
        outcome = IngestionOutcome(
            source=filename,
            kind="file",
            error=ApiError.client_side(ErrorCode.UNEXPECTED),
        )
        _record_outcome(outcome)
        return outcome

    outcome = IngestionOutcome(source=filename, kind="file", response=response)

    logger.info(
        "File ingestion complete | file=%s | docs=%d | chunks=%d | %.1fs",
        filename, response.documents_processed, response.chunks_persisted,
        response.elapsed_time_sec,
    )

    _record_outcome(outcome)
    return outcome


def history() -> list[IngestionRecord]:
    return state.load_ingestion_log()


def clear_history() -> None:
    state.clear_ingestion_log()


def totals() -> dict[str, int]:
    records = state.load_ingestion_log()

    return {
        "attempts": len(records),
        "successful": sum(1 for r in records if r.succeeded),
        "failed": sum(1 for r in records if not r.succeeded),
        "documents": sum(r.documents_processed for r in records if r.succeeded),
        "chunks": sum(r.chunks_persisted for r in records if r.succeeded),
    }