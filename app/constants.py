from __future__ import annotations

from enum import Enum
from typing import Final, FrozenSet, NamedTuple


APP_NAME: Final[str] = "Self-Healing RAG"
APP_TAGLINE: Final[str] = "Autonomous hallucination detection and recovery"
APP_VERSION: Final[str] = "1.0.0"


class Endpoint:
    HEALTH_LIVENESS: Final[str] = "/health/liveness"
    HEALTH_READINESS: Final[str] = "/health/readiness"
    DOCUMENTS_URL: Final[str] = "/documents/url"
    DOCUMENTS_UPLOAD: Final[str] = "/documents/upload"
    CHAT_QUERY: Final[str] = "/chat/query"
    OPENAPI: Final[str] = "/openapi.json"
    DOCS: Final[str] = "/docs"

    @staticmethod
    def evaluation(query_id: str) -> str:
        return f"/evaluation/{query_id}"

    @staticmethod
    def memory(session_id: str) -> str:
        return f"/memory/{session_id}"


class Route:
    CHAT: Final[str] = "/"
    DOCUMENTS: Final[str] = "/documents"
    EVALUATION: Final[str] = "/evaluation"
    HEALTH: Final[str] = "/health"
    ABOUT: Final[str] = "/about"


class NavItem(NamedTuple):
    label: str
    route: str
    icon: str


NAV_ITEMS: Final[tuple[NavItem, ...]] = (
    NavItem("Chat", Route.CHAT, "forum"),
    NavItem("Documents", Route.DOCUMENTS, "library_books"),
    NavItem("Evaluation", Route.EVALUATION, "fact_check"),
    NavItem("Health", Route.HEALTH, "monitor_heart"),
    NavItem("About", Route.ABOUT, "info"),
)


class ResponseStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class HallucinationRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RecoveryAction(str, Enum):
    REWRITE_QUERY = "rewrite_query"
    RETRY_RETRIEVAL = "retry_retrieval"
    WEB_SEARCH = "web_search"
    MERGE_CONTEXT = "merge_context"
    STRICT_GROUNDING = "strict_grounding"
    ASK_CLARIFICATION = "ask_clarification"
    LOG_KNOWLEDGE_GAP = "log_knowledge_gap"
    STOP = "stop"


class ActionMeta(NamedTuple):
    label: str
    icon: str
    color: str
    description: str


RECOVERY_ACTION_META: Final[dict[str, ActionMeta]] = {
    RecoveryAction.REWRITE_QUERY.value: ActionMeta(
        "Rewrite Query",
        "edit_note",
        "#8b7cf6",
        "Expanded the question with an LLM to improve vector matching.",
    ),
    RecoveryAction.RETRY_RETRIEVAL.value: ActionMeta(
        "Retry Retrieval",
        "refresh",
        "#4a9eff",
        "Re-ran the vector search against the knowledge base.",
    ),
    RecoveryAction.WEB_SEARCH.value: ActionMeta(
        "Web Search",
        "travel_explore",
        "#22c9a8",
        "Fetched external evidence because internal knowledge was insufficient.",
    ),
    RecoveryAction.MERGE_CONTEXT.value: ActionMeta(
        "Merge Context",
        "merge_type",
        "#3fb9d4",
        "Fused internal and web evidence into a single deduplicated context.",
    ),
    RecoveryAction.STRICT_GROUNDING.value: ActionMeta(
        "Strict Grounding",
        "gpp_maybe",
        "#f0a848",
        "Tightened prompt constraints after fabricated claims were detected.",
    ),
    RecoveryAction.ASK_CLARIFICATION.value: ActionMeta(
        "Ask Clarification",
        "help_outline",
        "#e8b04b",
        "Requested more detail because the system remained uncertain.",
    ),
    RecoveryAction.LOG_KNOWLEDGE_GAP.value: ActionMeta(
        "Log Knowledge Gap",
        "bookmark_add",
        "#c084d8",
        "Recorded the missing topic for future automated ingestion.",
    ),
    RecoveryAction.STOP.value: ActionMeta(
        "Stop",
        "block",
        "#8a93a6",
        "Halted recovery after exhausting the retry budget.",
    ),
}

UNKNOWN_ACTION_META: Final[ActionMeta] = ActionMeta(
    "Unknown Step",
    "help_center",
    "#8a93a6",
    "An unrecognised recovery action reported by the backend.",
)


def action_meta(action: str) -> ActionMeta:
    return RECOVERY_ACTION_META.get(action.strip().lower(), UNKNOWN_ACTION_META)


class StatusMeta(NamedTuple):
    label: str
    icon: str
    color: str


RESPONSE_STATUS_META: Final[dict[str, StatusMeta]] = {
    ResponseStatus.SUCCESS.value: StatusMeta("Success", "check_circle", "#22c9a8"),
    ResponseStatus.PARTIAL.value: StatusMeta("Partial", "error_outline", "#f0a848"),
    ResponseStatus.FAILED.value: StatusMeta("Failed", "cancel", "#f0605f"),
}

UNKNOWN_STATUS_META: Final[StatusMeta] = StatusMeta("Unknown", "help_outline", "#8a93a6")


def status_meta(status: str) -> StatusMeta:
    return RESPONSE_STATUS_META.get(status.strip().lower(), UNKNOWN_STATUS_META)


RISK_META: Final[dict[str, StatusMeta]] = {
    HallucinationRisk.LOW.value: StatusMeta("Low Risk", "verified", "#22c9a8"),
    HallucinationRisk.MEDIUM.value: StatusMeta("Medium Risk", "warning_amber", "#f0a848"),
    HallucinationRisk.HIGH.value: StatusMeta("High Risk", "dangerous", "#f0605f"),
}

UNKNOWN_RISK_META: Final[StatusMeta] = StatusMeta("Unknown Risk", "help_outline", "#8a93a6")


def risk_meta(risk: str) -> StatusMeta:
    return RISK_META.get(risk.strip().lower(), UNKNOWN_RISK_META)


CONFIDENCE_HIGH: Final[float] = 0.75
CONFIDENCE_MEDIUM: Final[float] = 0.50

COLOR_HIGH: Final[str] = "#22c9a8"
COLOR_MEDIUM: Final[str] = "#f0a848"
COLOR_LOW: Final[str] = "#f0605f"
COLOR_NEUTRAL: Final[str] = "#8a93a6"


def score_color(score: float) -> str:
    if score >= CONFIDENCE_HIGH:
        return COLOR_HIGH
    if score >= CONFIDENCE_MEDIUM:
        return COLOR_MEDIUM
    return COLOR_LOW


def score_label(score: float) -> str:
    if score >= CONFIDENCE_HIGH:
        return "High"
    if score >= CONFIDENCE_MEDIUM:
        return "Moderate"
    return "Low"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class RagasMetricMeta(NamedTuple):
    key: str
    label: str
    icon: str
    live: bool
    description: str


RAGAS_METRICS: Final[tuple[RagasMetricMeta, ...]] = (
    RagasMetricMeta(
        "faithfulness",
        "Faithfulness",
        "anchor",
        True,
        "How well the answer's claims are supported by the retrieved context.",
    ),
    RagasMetricMeta(
        "answer_relevancy",
        "Answer Relevancy",
        "center_focus_strong",
        True,
        "How directly the answer addresses the original question.",
    ),
    RagasMetricMeta(
        "context_precision",
        "Context Precision",
        "filter_center_focus",
        False,
        "Density of relevant versus irrelevant retrieved chunks.",
    ),
    RagasMetricMeta(
        "context_recall",
        "Context Recall",
        "playlist_add_check",
        False,
        "Whether all required ground-truth information was retrieved.",
    ),
)

BENCHMARK_ONLY_NOTE: Final[str] = "Benchmark only — not computed in live mode"


ALLOWED_UPLOAD_EXTENSIONS: Final[FrozenSet[str]] = frozenset({
    ".pdf", ".docx", ".pptx", ".txt", ".log",
    ".csv", ".md", ".markdown", ".html", ".htm",
})

UPLOAD_ACCEPT_ATTR: Final[str] = ",".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))

ALLOWED_URL_SCHEMES: Final[FrozenSet[str]] = frozenset({"http", "https"})


MAX_QUERY_LENGTH: Final[int] = 10000
MAX_SESSION_ID_LENGTH: Final[int] = 100
MAX_USER_ID_LENGTH: Final[int] = 100
MAX_SESSION_TITLE_LENGTH: Final[int] = 60
MAX_STORED_SESSIONS: Final[int] = 50
MAX_INGESTION_LOG_ENTRIES: Final[int] = 100
MAX_QUERY_LOG_ENTRIES: Final[int] = 30

HEADER_REQUEST_ID: Final[str] = "X-Request-ID"
REQUEST_ID_PREFIX: Final[str] = "ui"


class StorageKey:
    SESSIONS: Final[str] = "sessions"
    ACTIVE_SESSION: Final[str] = "active_session_id"
    INGESTION_LOG: Final[str] = "ingestion_log"
    DARK_MODE: Final[str] = "dark_mode"
    USER_ID: Final[str] = "user_id"
    QUERY_LOG: Final[str] = "query_log"


DEFAULT_SESSION_TITLE: Final[str] = "New conversation"

EMPTY_CHAT_HEADLINE: Final[str] = "Ask the knowledge base"
EMPTY_CHAT_BODY: Final[str] = (
    "Every answer is verified for grounding and hallucination. "
    "When verification fails, the system repairs itself and shows you how."
)

SAMPLE_QUESTIONS: Final[tuple[str, ...]] = (
    "What is retrieval-augmented generation?",
    "How does the system detect hallucinations?",
    "Summarise the ingested documents.",
)

COLD_START_MESSAGE: Final[str] = (
    "The backend is waking up from idle. The first request can take up to "
    "{seconds} seconds — later ones are much faster."
)

NO_EVALUATION_MESSAGE: Final[str] = (
    "No evaluation metrics were recorded for this query."
)