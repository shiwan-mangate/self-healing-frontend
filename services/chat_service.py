from __future__ import annotations

import asyncio
import logging
from typing import Optional

from api.client import api_client
from api.errors import ApiError, ErrorCode
from api.models import ChatResponse, ChatTurn, EvaluationResponse
from app import state
from app.constants import MAX_QUERY_LENGTH
from app.state import QueryRecord
from services import session_service
from utils.markdown import preview

logger = logging.getLogger(__name__)


class QueryCancelled(Exception):
    pass


def validate_question(question: str) -> Optional[str]:
    cleaned = question.strip()

    if not cleaned:
        return "Enter a question before sending."

    if len(cleaned) > MAX_QUERY_LENGTH:
        return (
            f"Questions are limited to {MAX_QUERY_LENGTH:,} characters. "
            f"Yours is {len(cleaned):,}."
        )

    return None


async def _fetch_evaluation(query_id: str) -> Optional[EvaluationResponse]:
    if not query_id:
        return None

    try:
        return await api_client.get_evaluation_with_retry(query_id)
    except Exception:
        logger.exception("Unexpected failure fetching evaluation for %s", query_id)
        return None


def _record_query(
    response: ChatResponse,
    question: str,
    evaluation: Optional[EvaluationResponse],
) -> None:
    if not response.query_id:
        return

    confidence = (
        evaluation.confidence.score if evaluation is not None else response.confidence
    )

    try:
        state.append_query(
            QueryRecord(
                query_id=response.query_id,
                session_id=response.session_id,
                question=preview(question, limit=120),
                status=response.status,
                confidence=confidence,
                recovery_used=response.recovery_used,
                retry_count=response.retry_count,
            )
        )
    except Exception:
        logger.exception("Could not record query %s locally", response.query_id)


async def ask(
    question: str,
    session_id: str,
    *,
    fetch_evaluation: bool = True,
) -> ChatTurn:
    cleaned = question.strip()
    turn = ChatTurn.pending(cleaned)

    problem = validate_question(cleaned)
    if problem:
        return turn.with_error(problem)

    user_id = session_service.get_user_id()

    logger.info(
        "Submitting query | session=%s | length=%d", session_id, len(cleaned)
    )

    try:
        response: ChatResponse = await api_client.query(
            query=cleaned,
            session_id=session_id,
            user_id=user_id,
        )
    except asyncio.CancelledError:
        raise QueryCancelled from None
    except ApiError as exc:
        logger.warning(
            "Query failed | session=%s | code=%s | request_id=%s",
            session_id, exc.code, exc.request_id,
        )
        return turn.with_error(_error_message(exc))
    except Exception:
        logger.exception("Unexpected query failure for session %s", session_id)
        return turn.with_error(
            "An unexpected problem occurred while contacting the backend."
        )

    session_service.register_turn(session_id, cleaned)

    evaluation: Optional[EvaluationResponse] = None
    if fetch_evaluation and response.query_id:
        try:
            evaluation = await _fetch_evaluation(response.query_id)
        except asyncio.CancelledError:
            logger.info("Evaluation fetch cancelled; returning answer without metrics.")

    _record_query(response, cleaned, evaluation)

    logger.info(
        "Query complete | query_id=%s | status=%s | retries=%d | "
        "recovery=%s | latency=%.0fms | evaluation=%s",
        response.query_id,
        response.status,
        response.retry_count,
        response.recovery_used,
        response.latency_ms,
        evaluation is not None,
    )

    return turn.with_result(response, evaluation)


def _error_message(exc: ApiError) -> str:
    if exc.code == ErrorCode.SESSION_NOT_FOUND:
        return (
            "This conversation no longer exists on the server. "
            "Start a new one to continue."
        )

    if exc.code == ErrorCode.GENERATION_SERVICE_UNAVAILABLE:
        return (
            "The answer generation service is temporarily unreachable. "
            "This usually clears within a minute."
        )

    if exc.code == ErrorCode.EVALUATION_SERVICE_UNAVAILABLE:
        return (
            "The quality evaluation service is temporarily unreachable, "
            "so this question could not be completed."
        )

    if exc.is_cold_start_suspect:
        return (
            "The backend did not respond in time. It may be waking up from idle — "
            "try again in a moment."
        )

    if exc.is_validation:
        detail = exc.detail_text
        return (
            f"The question was rejected by the server.\n{detail}"
            if detail
            else "The question was rejected by the server."
        )

    return exc.message


async def refetch_evaluation(turn: ChatTurn) -> ChatTurn:
    if turn.response is None or not turn.response.query_id:
        return turn

    evaluation = await _fetch_evaluation(turn.response.query_id)
    if evaluation is None:
        return turn

    _record_query(turn.response, turn.question, evaluation)

    return turn.with_result(turn.response, evaluation)


def recent_queries() -> list[QueryRecord]:
    return state.load_query_log()


def find_query(query_id: str) -> Optional[QueryRecord]:
    return state.find_query(query_id)


def clear_query_log() -> None:
    state.clear_query_log()


class ChatController:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.turns: list[ChatTurn] = []
        self._task: Optional[asyncio.Task] = None

    @property
    def is_busy(self) -> bool:
        return self._task is not None and not self._task.done()

    def set_session(self, session_id: str) -> None:
        self.cancel()
        self.session_id = session_id
        self.turns = []

    def cancel(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
            logger.info("Query cancelled by user | session=%s", self.session_id)
        self._task = None

    async def submit(self, question: str) -> ChatTurn:
        if self.is_busy:
            raise RuntimeError("A query is already in progress.")

        self._task = asyncio.create_task(ask(question, self.session_id))

        try:
            turn = await self._task
        except (asyncio.CancelledError, QueryCancelled):
            turn = ChatTurn.pending(question.strip()).with_error(
                "The request was cancelled."
            )
        finally:
            self._task = None

        self.turns.append(turn)
        return turn

    async def retry_last(self) -> Optional[ChatTurn]:
        if not self.turns or self.is_busy:
            return None

        question = self.turns[-1].question
        return await self.submit(question)

    def clear(self) -> None:
        self.cancel()
        self.turns = []

    def replace_turn(self, index: int, turn: ChatTurn) -> None:
        if 0 <= index < len(self.turns):
            self.turns[index] = turn