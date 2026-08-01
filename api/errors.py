from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

import httpx

from app.config import settings


class ErrorCode:
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    EVALUATION_NOT_FOUND = "EVALUATION_NOT_FOUND"
    GENERATION_SERVICE_UNAVAILABLE = "GENERATION_SERVICE_UNAVAILABLE"
    EVALUATION_SERVICE_UNAVAILABLE = "EVALUATION_SERVICE_UNAVAILABLE"
    APPLICATION_ERROR = "APPLICATION_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"

    UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
    BAD_REQUEST = "BAD_REQUEST"
    NOT_FOUND = "NOT_FOUND"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"

    TIMEOUT = "CLIENT_TIMEOUT"
    CONNECTION_FAILED = "CLIENT_CONNECTION_FAILED"
    MALFORMED_RESPONSE = "CLIENT_MALFORMED_RESPONSE"
    UNEXPECTED = "CLIENT_UNEXPECTED"
    FILE_TOO_LARGE = "CLIENT_FILE_TOO_LARGE"
    INVALID_FILE_TYPE = "CLIENT_INVALID_FILE_TYPE"
    INVALID_URL = "CLIENT_INVALID_URL"


_COLD_START_HINT = (
    "The backend may be waking up from idle. Wait a moment and try again."
)

_FRIENDLY_MESSAGES: dict[str, str] = {
    ErrorCode.SESSION_NOT_FOUND: (
        "That conversation no longer exists on the server. "
        "It may have expired after a period of inactivity."
    ),
    ErrorCode.EVALUATION_NOT_FOUND: (
        "No evaluation metrics were recorded for this query."
    ),
    ErrorCode.GENERATION_SERVICE_UNAVAILABLE: (
        "The answer generation service is temporarily unreachable. "
        "This usually means the language model provider is rate-limiting or down."
    ),
    ErrorCode.EVALUATION_SERVICE_UNAVAILABLE: (
        "The quality evaluation service is temporarily unreachable. "
        "The answer may still be available without its metrics."
    ),
    ErrorCode.VALIDATION_ERROR: (
        "The request was rejected because it did not match what the server expects."
    ),
    ErrorCode.APPLICATION_ERROR: (
        "The server encountered an application error while handling the request."
    ),
    ErrorCode.INTERNAL_ERROR: (
        "The server hit an unexpected error. This has been logged on the backend."
    ),
    ErrorCode.UNSUPPORTED_MEDIA_TYPE: (
        "That file type is not supported by the ingestion pipeline."
    ),
    ErrorCode.BAD_REQUEST: (
        "The request was malformed and the server could not process it."
    ),
    ErrorCode.NOT_FOUND: (
        "The requested resource was not found on the server."
    ),
    ErrorCode.SERVICE_UNAVAILABLE: (
        "The service is temporarily unavailable. " + _COLD_START_HINT
    ),
    ErrorCode.TIMEOUT: (
        "The request took too long and was cancelled. " + _COLD_START_HINT
    ),
    ErrorCode.CONNECTION_FAILED: (
        "Could not reach the backend. Check that the API is running and that "
        "your network connection is working."
    ),
    ErrorCode.MALFORMED_RESPONSE: (
        "The server returned a response this app could not understand."
    ),
    ErrorCode.UNEXPECTED: (
        "Something went wrong while talking to the backend."
    ),
    ErrorCode.FILE_TOO_LARGE: (
        f"That file exceeds the {settings.max_upload_mb} MB limit."
    ),
    ErrorCode.INVALID_FILE_TYPE: (
        "That file type is not supported."
    ),
    ErrorCode.INVALID_URL: (
        "Only http:// and https:// addresses can be ingested from a URL."
    ),
}

_STATUS_FALLBACK_CODES: dict[int, str] = {
    400: ErrorCode.BAD_REQUEST,
    404: ErrorCode.NOT_FOUND,
    413: ErrorCode.FILE_TOO_LARGE,
    415: ErrorCode.UNSUPPORTED_MEDIA_TYPE,
    422: ErrorCode.VALIDATION_ERROR,
    500: ErrorCode.INTERNAL_ERROR,
    502: ErrorCode.SERVICE_UNAVAILABLE,
    503: ErrorCode.SERVICE_UNAVAILABLE,
    504: ErrorCode.TIMEOUT,
}

_RETRYABLE_CODES: frozenset[str] = frozenset({
    ErrorCode.TIMEOUT,
    ErrorCode.CONNECTION_FAILED,
    ErrorCode.SERVICE_UNAVAILABLE,
    ErrorCode.GENERATION_SERVICE_UNAVAILABLE,
    ErrorCode.EVALUATION_SERVICE_UNAVAILABLE,
    ErrorCode.INTERNAL_ERROR,
})

_NOT_FOUND_CODES: frozenset[str] = frozenset({
    ErrorCode.SESSION_NOT_FOUND,
    ErrorCode.EVALUATION_NOT_FOUND,
    ErrorCode.NOT_FOUND,
})

_COLD_START_CODES: frozenset[str] = frozenset({
    ErrorCode.TIMEOUT,
    ErrorCode.CONNECTION_FAILED,
    ErrorCode.SERVICE_UNAVAILABLE,
})

_MAX_DETAIL_ITEMS = 5
_MAX_RAW_BODY_CHARS = 400


def _format_validation_detail(item: Mapping[str, Any]) -> Optional[str]:
    message = str(item.get("msg", "")).strip()
    if not message:
        return None

    location = item.get("loc")
    if isinstance(location, Sequence) and not isinstance(location, (str, bytes)):
        parts = [str(p) for p in location if str(p) not in {"body", "query", "path"}]
        field_path = ".".join(parts)
    else:
        field_path = ""

    return f"{field_path}: {message}" if field_path else message


def _extract_details(payload: Mapping[str, Any]) -> list[str]:
    raw = payload.get("details")
    if raw is None:
        raw = payload.get("detail")

    if raw is None:
        return []

    if isinstance(raw, str):
        stripped = raw.strip()
        return [stripped] if stripped else []

    if isinstance(raw, Mapping):
        formatted = _format_validation_detail(raw)
        return [formatted] if formatted else []

    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        results: list[str] = []
        for item in raw[:_MAX_DETAIL_ITEMS]:
            if isinstance(item, Mapping):
                formatted = _format_validation_detail(item)
                if formatted:
                    results.append(formatted)
            else:
                text = str(item).strip()
                if text:
                    results.append(text)
        return results

    return []


class ApiError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: Optional[int] = None,
        request_id: Optional[str] = None,
        details: Optional[list[str]] = None,
        server_message: Optional[str] = None,
        endpoint: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.request_id = request_id
        self.details = details or []
        self.server_message = server_message
        self.endpoint = endpoint

    def __str__(self) -> str:
        return self.message

    def __repr__(self) -> str:
        return (
            f"ApiError(code={self.code!r}, status={self.status_code!r}, "
            f"request_id={self.request_id!r}, message={self.message!r})"
        )

    @property
    def is_retryable(self) -> bool:
        return self.code in _RETRYABLE_CODES

    @property
    def is_not_found(self) -> bool:
        return self.code in _NOT_FOUND_CODES

    @property
    def is_validation(self) -> bool:
        return self.code == ErrorCode.VALIDATION_ERROR

    @property
    def is_cold_start_suspect(self) -> bool:
        return self.code in _COLD_START_CODES

    @property
    def is_client_side(self) -> bool:
        return self.status_code is None

    @property
    def title(self) -> str:
        if self.is_not_found:
            return "Not found"
        if self.is_validation:
            return "Invalid request"
        if self.code == ErrorCode.TIMEOUT:
            return "Request timed out"
        if self.code == ErrorCode.CONNECTION_FAILED:
            return "Cannot reach backend"
        if self.is_retryable:
            return "Service unavailable"
        return "Request failed"

    @property
    def detail_text(self) -> str:
        return "\n".join(self.details)

    @property
    def trace_text(self) -> str:
        parts: list[str] = []
        if self.status_code is not None:
            parts.append(f"HTTP {self.status_code}")
        parts.append(self.code)
        if self.request_id:
            parts.append(self.request_id)
        return " · ".join(parts)

    def full_text(self) -> str:
        segments = [self.message]
        if self.details:
            segments.append(self.detail_text)
        segments.append(self.trace_text)
        return "\n\n".join(segment for segment in segments if segment)

    @classmethod
    def from_response(
        cls,
        response: httpx.Response,
        *,
        endpoint: Optional[str] = None,
    ) -> "ApiError":
        status = response.status_code
        fallback_code = _STATUS_FALLBACK_CODES.get(status, ErrorCode.UNEXPECTED)

        payload: Mapping[str, Any] = {}
        try:
            parsed = response.json()
            if isinstance(parsed, Mapping):
                payload = parsed
        except (json.JSONDecodeError, ValueError):
            payload = {}

        code = str(payload.get("error_code") or fallback_code).strip() or fallback_code
        server_message = str(payload.get("message") or "").strip() or None
        request_id = str(payload.get("request_id") or "").strip() or None

        if request_id is None:
            header_id = response.headers.get("X-Request-ID", "").strip()
            request_id = header_id or None

        details = _extract_details(payload)

        message = _FRIENDLY_MESSAGES.get(code)
        if message is None:
            message = server_message or _FRIENDLY_MESSAGES.get(
                fallback_code, _FRIENDLY_MESSAGES[ErrorCode.UNEXPECTED]
            )

        if not payload and response.text:
            snippet = response.text.strip()[:_MAX_RAW_BODY_CHARS]
            if snippet and not details:
                details = [snippet]

        return cls(
            code=code,
            message=message,
            status_code=status,
            request_id=request_id,
            details=details,
            server_message=server_message,
            endpoint=endpoint,
        )

    @classmethod
    def from_exception(
        cls,
        exc: Exception,
        *,
        endpoint: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> "ApiError":
        if isinstance(exc, ApiError):
            return exc

        if isinstance(exc, httpx.TimeoutException):
            code = ErrorCode.TIMEOUT
        elif isinstance(exc, (httpx.ConnectError, httpx.NetworkError)):
            code = ErrorCode.CONNECTION_FAILED
        elif isinstance(exc, (json.JSONDecodeError, ValueError)):
            code = ErrorCode.MALFORMED_RESPONSE
        elif isinstance(exc, httpx.HTTPError):
            code = ErrorCode.UNEXPECTED
        else:
            code = ErrorCode.UNEXPECTED

        detail = str(exc).strip()

        return cls(
            code=code,
            message=_FRIENDLY_MESSAGES[code],
            status_code=None,
            request_id=request_id,
            details=[detail] if detail else [],
            server_message=None,
            endpoint=endpoint,
        )

    @classmethod
    def client_side(
        cls,
        code: str,
        *,
        message: Optional[str] = None,
        details: Optional[list[str]] = None,
    ) -> "ApiError":
        resolved = message or _FRIENDLY_MESSAGES.get(
            code, _FRIENDLY_MESSAGES[ErrorCode.UNEXPECTED]
        )
        return cls(code=code, message=resolved, details=details or [])


@dataclass(frozen=True, slots=True)
class ErrorDisplay:
    title: str
    message: str
    details: list[str] = field(default_factory=list)
    trace: str = ""
    icon: str = "error_outline"
    color: str = "#f0605f"
    retryable: bool = False

    @classmethod
    def from_error(cls, error: ApiError) -> "ErrorDisplay":
        if error.is_not_found:
            icon, color = "search_off", "#8a93a6"
        elif error.is_validation:
            icon, color = "rule", "#f0a848"
        elif error.code == ErrorCode.TIMEOUT:
            icon, color = "hourglass_disabled", "#f0a848"
        elif error.code == ErrorCode.CONNECTION_FAILED:
            icon, color = "cloud_off", "#f0605f"
        elif error.is_retryable:
            icon, color = "cloud_off", "#f0a848"
        else:
            icon, color = "error_outline", "#f0605f"

        return cls(
            title=error.title,
            message=error.message,
            details=error.details,
            trace=error.trace_text,
            icon=icon,
            color=color,
            retryable=error.is_retryable,
        )