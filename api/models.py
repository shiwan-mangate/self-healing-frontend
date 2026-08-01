from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value
    return str(value)


def _as_opt_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = value if isinstance(value, str) else str(value)
    text = text.strip()
    return text or None


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y", "on"}:
            return True
        if lowered in {"false", "0", "no", "n", "off"}:
            return False
    return default


def _as_int(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value.strip()))
        except ValueError:
            return default
    return default


def _as_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return default
    return default


def _as_opt_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _as_opt_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value.strip()))
        except ValueError:
            return None
    return None


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, Sequence):
        result: list[str] = []
        for item in value:
            text = _as_str(item).strip()
            if text:
                result.append(text)
        return result
    return []


def _as_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _as_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return datetime.now(timezone.utc)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class LivenessReport:
    status: str
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def alive(self) -> bool:
        return self.status.strip().lower() == "alive"

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "LivenessReport":
        data = _as_mapping(payload)
        return cls(status=_as_str(data.get("status"), "unknown"), raw=data)


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    status: str
    ready: bool
    checks: dict[str, bool]
    latency_ms: float
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def failed_checks(self) -> list[str]:
        return [name for name, ok in self.checks.items() if not ok]

    @property
    def passed_checks(self) -> list[str]:
        return [name for name, ok in self.checks.items() if ok]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ReadinessReport":
        data = _as_mapping(payload)
        raw_checks = _as_mapping(data.get("checks"))
        return cls(
            status=_as_str(data.get("status"), "unknown"),
            ready=_as_bool(data.get("ready")),
            checks={str(k): _as_bool(v) for k, v in raw_checks.items()},
            latency_ms=_as_float(data.get("latency_ms")),
            raw=data,
        )


@dataclass(frozen=True, slots=True)
class DocumentIngestionResponse:
    documents_processed: int
    chunks_generated: int
    chunks_persisted: int
    warnings: list[str]
    elapsed_time_sec: float
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def succeeded(self) -> bool:
        return self.chunks_persisted > 0

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DocumentIngestionResponse":
        data = _as_mapping(payload)
        return cls(
            documents_processed=_as_int(data.get("documents_processed")),
            chunks_generated=_as_int(data.get("chunks_generated")),
            chunks_persisted=_as_int(data.get("chunks_persisted")),
            warnings=_as_str_list(data.get("warnings")),
            elapsed_time_sec=_as_float(data.get("elapsed_time_sec")),
            raw=data,
        )


@dataclass(frozen=True, slots=True)
class Citation:
    inline_reference: str
    chunk_id: str
    document_id: str
    document_name: Optional[str]
    source_type: Optional[str]
    page_number: Optional[int]
    relevance_score: float

    @property
    def marker_index(self) -> Optional[int]:
        digits = "".join(ch for ch in self.inline_reference if ch.isdigit())
        return int(digits) if digits else None

    @property
    def display_name(self) -> str:
        return self.document_name or self.source_type or self.document_id

    @property
    def display_location(self) -> str:
        parts: list[str] = []
        if self.source_type:
            parts.append(self.source_type.upper())
        if self.page_number is not None:
            parts.append(f"Page {self.page_number}")
        return " · ".join(parts)

    @property
    def is_web_source(self) -> bool:
        return (self.source_type or "").strip().lower() == "web"

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Citation":
        data = _as_mapping(payload)
        return cls(
            inline_reference=_as_str(data.get("inline_reference")),
            chunk_id=_as_str(data.get("chunk_id")),
            document_id=_as_str(data.get("document_id")),
            document_name=_as_opt_str(data.get("document_name")),
            source_type=_as_opt_str(data.get("source_type")),
            page_number=_as_opt_int(data.get("page_number")),
            relevance_score=_as_float(data.get("relevance_score")),
        )


@dataclass(frozen=True, slots=True)
class ChatResponse:
    query_id: str
    session_id: str
    status: str
    answer: str
    citations: list[Citation]
    confidence: float
    recovery_used: bool
    correction_path: list[str]
    retry_count: int
    latency_ms: float
    warnings: list[str]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_success(self) -> bool:
        return self.status == "success"

    @property
    def is_failed(self) -> bool:
        return self.status == "failed"

    @property
    def has_citations(self) -> bool:
        return bool(self.citations)

    @property
    def has_healing(self) -> bool:
        return self.recovery_used or bool(self.correction_path) or self.retry_count > 0

    @property
    def unique_documents(self) -> list[str]:
        seen: set[str] = set()
        names: list[str] = []
        for citation in self.citations:
            name = citation.display_name
            if name not in seen:
                seen.add(name)
                names.append(name)
        return names

    @property
    def latency_sec(self) -> float:
        return self.latency_ms / 1000.0

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ChatResponse":
        data = _as_mapping(payload)
        return cls(
            query_id=_as_str(data.get("query_id")),
            session_id=_as_str(data.get("session_id")),
            status=_as_str(data.get("status"), "failed").strip().lower(),
            answer=_as_str(data.get("answer")),
            citations=[Citation.from_dict(item) for item in _as_dict_list(data.get("citations"))],
            confidence=_clamp01(_as_float(data.get("confidence"))),
            recovery_used=_as_bool(data.get("recovery_used")),
            correction_path=_as_str_list(data.get("correction_path")),
            retry_count=_as_int(data.get("retry_count")),
            latency_ms=_as_float(data.get("latency_ms")),
            warnings=_as_str_list(data.get("warnings")),
            raw=data,
        )


@dataclass(frozen=True, slots=True)
class GroundingResult:
    is_grounded: bool
    confidence: float

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "GroundingResult":
        data = _as_mapping(payload)
        return cls(
            is_grounded=_as_bool(data.get("is_grounded")),
            confidence=_clamp01(_as_float(data.get("confidence"))),
        )


@dataclass(frozen=True, slots=True)
class HallucinationResult:
    detected: bool
    risk: str

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "HallucinationResult":
        data = _as_mapping(payload)
        return cls(
            detected=_as_bool(data.get("detected")),
            risk=_as_str(data.get("risk"), "unknown").strip().lower(),
        )


@dataclass(frozen=True, slots=True)
class ConfidenceResult:
    score: float
    retrieval_confidence: float
    grounding_confidence: float
    hallucination_risk: str

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ConfidenceResult":
        data = _as_mapping(payload)
        return cls(
            score=_clamp01(_as_float(data.get("score"))),
            retrieval_confidence=_clamp01(_as_float(data.get("retrieval_confidence"))),
            grounding_confidence=_clamp01(_as_float(data.get("grounding_confidence"))),
            hallucination_risk=_as_str(data.get("hallucination_risk"), "unknown").strip().lower(),
        )


@dataclass(frozen=True, slots=True)
class RagasResult:
    faithfulness: Optional[float]
    answer_relevancy: Optional[float]
    context_recall: Optional[float]
    context_precision: Optional[float]

    @property
    def live_metrics(self) -> dict[str, Optional[float]]:
        return {
            "faithfulness": self.faithfulness,
            "answer_relevancy": self.answer_relevancy,
        }

    @property
    def benchmark_metrics(self) -> dict[str, Optional[float]]:
        return {
            "context_precision": self.context_precision,
            "context_recall": self.context_recall,
        }

    def get(self, key: str) -> Optional[float]:
        return {
            "faithfulness": self.faithfulness,
            "answer_relevancy": self.answer_relevancy,
            "context_recall": self.context_recall,
            "context_precision": self.context_precision,
        }.get(key)

    @property
    def has_any(self) -> bool:
        return any(
            value is not None
            for value in (
                self.faithfulness,
                self.answer_relevancy,
                self.context_recall,
                self.context_precision,
            )
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "RagasResult":
        data = _as_mapping(payload)
        return cls(
            faithfulness=_as_opt_float(data.get("faithfulness")),
            answer_relevancy=_as_opt_float(data.get("answer_relevancy")),
            context_recall=_as_opt_float(data.get("context_recall")),
            context_precision=_as_opt_float(data.get("context_precision")),
        )


@dataclass(frozen=True, slots=True)
class EvaluationResponse:
    grounding: GroundingResult
    hallucination: HallucinationResult
    confidence: ConfidenceResult
    ragas: RagasResult
    retry_recommended: bool
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def passed(self) -> bool:
        return self.grounding.is_grounded and not self.hallucination.detected

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EvaluationResponse":
        data = _as_mapping(payload)
        return cls(
            grounding=GroundingResult.from_dict(_as_mapping(data.get("grounding"))),
            hallucination=HallucinationResult.from_dict(_as_mapping(data.get("hallucination"))),
            confidence=ConfidenceResult.from_dict(_as_mapping(data.get("confidence"))),
            ragas=RagasResult.from_dict(_as_mapping(data.get("ragas"))),
            retry_recommended=_as_bool(data.get("retry_recommended")),
            raw=data,
        )


@dataclass(frozen=True, slots=True)
class SessionInfo:
    session_id: str
    created_at: datetime
    last_activity: datetime
    message_count: int
    active: bool

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SessionInfo":
        data = _as_mapping(payload)
        return cls(
            session_id=_as_str(data.get("session_id")),
            created_at=_as_datetime(data.get("created_at")),
            last_activity=_as_datetime(data.get("last_activity")),
            message_count=_as_int(data.get("message_count")),
            active=_as_bool(data.get("active"), True),
        )


@dataclass(frozen=True, slots=True)
class ConversationMessage:
    message_id: str
    role: str
    content: str
    timestamp: datetime

    @property
    def is_user(self) -> bool:
        return self.role == "user"

    @property
    def is_assistant(self) -> bool:
        return self.role == "assistant"

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ConversationMessage":
        data = _as_mapping(payload)
        return cls(
            message_id=_as_str(data.get("message_id")),
            role=_as_str(data.get("role"), "assistant").strip().lower(),
            content=_as_str(data.get("content")),
            timestamp=_as_datetime(data.get("timestamp")),
        )


@dataclass(frozen=True, slots=True)
class ConversationHistory:
    session: SessionInfo
    messages: list[ConversationMessage]
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def is_empty(self) -> bool:
        return not self.messages

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ConversationHistory":
        data = _as_mapping(payload)
        return cls(
            session=SessionInfo.from_dict(_as_mapping(data.get("session"))),
            messages=[
                ConversationMessage.from_dict(item)
                for item in _as_dict_list(data.get("messages"))
            ],
            raw=data,
        )


@dataclass(frozen=True, slots=True)
class ChatTurn:
    question: str
    response: Optional[ChatResponse]
    evaluation: Optional[EvaluationResponse]
    asked_at: datetime
    error: Optional[str] = None

    @property
    def failed(self) -> bool:
        return self.response is None

    @property
    def query_id(self) -> Optional[str]:
        return self.response.query_id if self.response else None

    @property
    def confidence(self) -> float:
        if self.evaluation is not None:
            return self.evaluation.confidence.score
        if self.response is not None:
            return self.response.confidence
        return 0.0

    @classmethod
    def pending(cls, question: str) -> "ChatTurn":
        return cls(
            question=question,
            response=None,
            evaluation=None,
            asked_at=datetime.now(timezone.utc),
        )

    def with_result(
        self,
        response: ChatResponse,
        evaluation: Optional[EvaluationResponse],
    ) -> "ChatTurn":
        return ChatTurn(
            question=self.question,
            response=response,
            evaluation=evaluation,
            asked_at=self.asked_at,
            error=None,
        )

    def with_error(self, message: str) -> "ChatTurn":
        return ChatTurn(
            question=self.question,
            response=None,
            evaluation=None,
            asked_at=self.asked_at,
            error=message,
        )