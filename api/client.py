from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, Final, Mapping, Optional

import httpx

from app.config import settings
from app.constants import (
    ALLOWED_UPLOAD_EXTENSIONS,
    ALLOWED_URL_SCHEMES,
    Endpoint,
    HEADER_REQUEST_ID,
    MAX_QUERY_LENGTH,
    MAX_SESSION_ID_LENGTH,
    MAX_USER_ID_LENGTH,
    REQUEST_ID_PREFIX,
)
from api.errors import ApiError, ErrorCode
from api.models import (
    ChatResponse,
    ConversationHistory,
    DocumentIngestionResponse,
    EvaluationResponse,
    LivenessReport,
    ReadinessReport,
)

logger = logging.getLogger(__name__)

_JSON_HEADERS: Final[dict[str, str]] = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}

_ACCEPT_HEADERS: Final[dict[str, str]] = {
    "Accept": "application/json",
}

_MAX_CONNECTIONS: Final[int] = 20
_MAX_KEEPALIVE: Final[int] = 5
_KEEPALIVE_EXPIRY: Final[float] = 30.0


def _new_request_id() -> str:
    return f"{REQUEST_ID_PREFIX}_{uuid.uuid4().hex}"


def _extension_of(filename: str) -> str:
    name = filename.strip().lower()
    dot = name.rfind(".")
    return name[dot:] if dot > 0 else ""


class ApiClient:
    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is not None and not self._client.is_closed:
            return self._client

        async with self._lock:
            if self._client is not None and not self._client.is_closed:
                return self._client

            self._client = httpx.AsyncClient(
                base_url=settings.api_base_url,
                timeout=httpx.Timeout(settings.timeout_read),
                limits=httpx.Limits(
                    max_connections=_MAX_CONNECTIONS,
                    max_keepalive_connections=_MAX_KEEPALIVE,
                    keepalive_expiry=_KEEPALIVE_EXPIRY,
                ),
                follow_redirects=True,
                headers={"User-Agent": "SelfHealingRAG-UI/1.0"},
            )
            logger.info("HTTP client initialised for %s", settings.api_base_url)
            return self._client

    async def aclose(self) -> None:
        async with self._lock:
            if self._client is not None and not self._client.is_closed:
                await self._client.aclose()
                logger.info("HTTP client closed.")
            self._client = None

    async def _request(
        self,
        method: str,
        path: str,
        *,
        timeout: float,
        json_body: Optional[Mapping[str, Any]] = None,
        files: Optional[Mapping[str, Any]] = None,
        accept_status: tuple[int, ...] = (200,),
    ) -> tuple[dict[str, Any], int]:
        client = await self._get_client()
        request_id = _new_request_id()

        headers: dict[str, str] = dict(_ACCEPT_HEADERS if files else _JSON_HEADERS)
        if files:
            headers.pop("Content-Type", None)
        headers[HEADER_REQUEST_ID] = request_id

        started = time.perf_counter()

        try:
            response = await client.request(
                method,
                path,
                json=json_body,
                files=files,
                headers=headers,
                timeout=httpx.Timeout(timeout),
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.warning(
                "Request failed | %s %s | request_id=%s | elapsed=%.0fms | %s",
                method, path, request_id, elapsed_ms, exc,
            )
            raise ApiError.from_exception(exc, endpoint=path, request_id=request_id) from exc

        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "%s %s | status=%d | request_id=%s | elapsed=%.0fms",
            method, path, response.status_code, request_id, elapsed_ms,
        )

        if response.status_code not in accept_status:
            raise ApiError.from_response(response, endpoint=path)

        if not response.content:
            return {}, response.status_code

        try:
            payload = response.json()
        except ValueError as exc:
            raise ApiError.client_side(
                ErrorCode.MALFORMED_RESPONSE,
                details=[f"{method} {path} returned non-JSON content."],
            ) from exc

        if not isinstance(payload, Mapping):
            raise ApiError.client_side(
                ErrorCode.MALFORMED_RESPONSE,
                details=[f"{method} {path} returned {type(payload).__name__}, expected an object."],
            )

        return dict(payload), response.status_code

    async def check_liveness(self) -> LivenessReport:
        payload, _ = await self._request(
            "GET",
            Endpoint.HEALTH_LIVENESS,
            timeout=settings.timeout_health,
        )
        return LivenessReport.from_dict(payload)

    async def check_readiness(self) -> ReadinessReport:
        payload, _ = await self._request(
            "GET",
            Endpoint.HEALTH_READINESS,
            timeout=settings.timeout_health,
            accept_status=(200, 503),
        )
        return ReadinessReport.from_dict(payload)

    async def warm_up(self) -> bool:
        if not settings.should_warm_up:
            return True
        try:
            report = await self.check_liveness()
            return report.alive
        except ApiError as exc:
            logger.info("Warm-up ping did not succeed: %s", exc.code)
            return False

    async def query(
        self,
        *,
        query: str,
        session_id: str,
        user_id: Optional[str] = None,
        query_id: Optional[str] = None,
    ) -> ChatResponse:
        cleaned_query = query.strip()
        if not cleaned_query:
            raise ApiError.client_side(
                ErrorCode.VALIDATION_ERROR,
                message="Enter a question before sending.",
            )
        if len(cleaned_query) > MAX_QUERY_LENGTH:
            raise ApiError.client_side(
                ErrorCode.VALIDATION_ERROR,
                message=f"Questions are limited to {MAX_QUERY_LENGTH:,} characters.",
                details=[f"Current length: {len(cleaned_query):,} characters."],
            )

        cleaned_session = session_id.strip()
        if not cleaned_session:
            raise ApiError.client_side(
                ErrorCode.VALIDATION_ERROR,
                message="A conversation must be selected before sending a question.",
            )

        body: dict[str, Any] = {
            "query": cleaned_query,
            "session_id": cleaned_session[:MAX_SESSION_ID_LENGTH],
        }
        if user_id:
            body["user_id"] = user_id.strip()[:MAX_USER_ID_LENGTH]
        if query_id:
            body["query_id"] = query_id.strip()

        payload, _ = await self._request(
            "POST",
            Endpoint.CHAT_QUERY,
            timeout=settings.timeout_chat,
            json_body=body,
        )
        return ChatResponse.from_dict(payload)

    async def get_evaluation(self, query_id: str) -> EvaluationResponse:
        cleaned = query_id.strip()
        if not cleaned:
            raise ApiError.client_side(
                ErrorCode.VALIDATION_ERROR,
                message="A query ID is required to load evaluation metrics.",
            )

        payload, _ = await self._request(
            "GET",
            Endpoint.evaluation(cleaned),
            timeout=settings.timeout_read,
        )
        return EvaluationResponse.from_dict(payload)

    async def get_evaluation_with_retry(self, query_id: str) -> Optional[EvaluationResponse]:
        attempts = settings.eval_fetch_retries + 1

        for attempt in range(attempts):
            try:
                return await self.get_evaluation(query_id)
            except ApiError as exc:
                is_last = attempt == attempts - 1
                if is_last:
                    logger.info(
                        "Evaluation unavailable for query_id=%s after %d attempt(s): %s",
                        query_id, attempts, exc.code,
                    )
                    return None
                if not (exc.is_not_found or exc.is_retryable):
                    return None
                await asyncio.sleep(settings.eval_retry_delay)

        return None

    async def get_history(self, session_id: str) -> ConversationHistory:
        cleaned = session_id.strip()
        if not cleaned:
            raise ApiError.client_side(
                ErrorCode.VALIDATION_ERROR,
                message="A conversation ID is required to load history.",
            )

        payload, _ = await self._request(
            "GET",
            Endpoint.memory(cleaned),
            timeout=settings.timeout_read,
        )
        return ConversationHistory.from_dict(payload)

    async def ingest_url(self, source: str) -> DocumentIngestionResponse:
        cleaned = source.strip()
        if not cleaned:
            raise ApiError.client_side(
                ErrorCode.INVALID_URL,
                message="Enter a URL to ingest.",
            )

        lowered = cleaned.lower()
        if not any(lowered.startswith(f"{scheme}://") for scheme in ALLOWED_URL_SCHEMES):
            raise ApiError.client_side(
                ErrorCode.INVALID_URL,
                details=[f"Received: {cleaned[:120]}"],
            )

        payload, _ = await self._request(
            "POST",
            Endpoint.DOCUMENTS_URL,
            timeout=settings.timeout_ingest,
            json_body={"source": cleaned},
        )
        return DocumentIngestionResponse.from_dict(payload)

    async def ingest_file(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: Optional[str] = None,
    ) -> DocumentIngestionResponse:
        name = filename.strip()
        if not name:
            raise ApiError.client_side(
                ErrorCode.INVALID_FILE_TYPE,
                message="The uploaded file has no name.",
            )

        extension = _extension_of(name)
        if extension not in ALLOWED_UPLOAD_EXTENSIONS:
            supported = ", ".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))
            raise ApiError.client_side(
                ErrorCode.INVALID_FILE_TYPE,
                message=f"{extension or 'That file type'} is not supported.",
                details=[f"Supported types: {supported}"],
            )

        if not content:
            raise ApiError.client_side(
                ErrorCode.INVALID_FILE_TYPE,
                message="The uploaded file is empty.",
            )

        if len(content) > settings.max_upload_bytes:
            size_mb = len(content) / (1024 * 1024)
            raise ApiError.client_side(
                ErrorCode.FILE_TOO_LARGE,
                details=[f"{name} is {size_mb:.1f} MB."],
            )

        files = {
            "file": (name, content, content_type or "application/octet-stream"),
        }

        payload, _ = await self._request(
            "POST",
            Endpoint.DOCUMENTS_UPLOAD,
            timeout=settings.timeout_ingest,
            files=files,
        )
        return DocumentIngestionResponse.from_dict(payload)


api_client: Final[ApiClient] = ApiClient()