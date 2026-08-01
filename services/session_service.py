from __future__ import annotations

import logging
from typing import Optional

from api.client import api_client
from api.errors import ApiError
from api.models import ConversationHistory
from app import state
from app.state import SessionRecord
from utils.markdown import preview

logger = logging.getLogger(__name__)


def get_active() -> SessionRecord:
    return state.ensure_active_session()


def get_active_id() -> str:
    return get_active().session_id


def list_sessions() -> list[SessionRecord]:
    return state.load_sessions()


def find(session_id: str) -> Optional[SessionRecord]:
    return state.find_session(session_id)


def create(title: Optional[str] = None) -> SessionRecord:
    return state.create_session(title)


def select(session_id: str) -> Optional[SessionRecord]:
    record = state.find_session(session_id)
    if record is None:
        return None
    state.set_active_session_id(session_id)
    return record


def rename(session_id: str, title: str) -> Optional[SessionRecord]:
    return state.rename_session(session_id, title)


def delete(session_id: str) -> SessionRecord:
    state.delete_session(session_id)
    return state.ensure_active_session()


def clear_all() -> SessionRecord:
    state.clear_sessions()
    return state.ensure_active_session()


def register_turn(session_id: str, question: str) -> None:
    record = state.find_session(session_id)
    if record is None:
        return

    new_count = record.message_count + 2

    if record.is_untitled:
        state.update_session(
            session_id,
            title=preview(question, limit=48),
            message_count=new_count,
            touch=True,
        )
    else:
        state.update_session(session_id, message_count=new_count, touch=True)


def touch(session_id: str) -> None:
    state.update_session(session_id, touch=True)


async def load_history(session_id: str) -> Optional[ConversationHistory]:
    try:
        history = await api_client.get_history(session_id)
    except ApiError as exc:
        if exc.is_not_found:
            logger.info("No server history for session %s", session_id)
            return None
        raise

    state.update_session(
        session_id,
        message_count=len(history.messages),
        touch=False,
    )

    return history


async def sync_from_server(session_id: str) -> Optional[ConversationHistory]:
    try:
        return await load_history(session_id)
    except ApiError as exc:
        logger.warning(
            "Could not sync session %s from server: %s", session_id, exc.code
        )
        return None


def get_user_id() -> str:
    return state.get_user_id()


def exists_locally(session_id: str) -> bool:
    return state.find_session(session_id) is not None


def import_session(session_id: str, *, title: Optional[str] = None) -> Optional[SessionRecord]:
    cleaned = session_id.strip()
    if not cleaned:
        return None

    existing = state.find_session(cleaned)
    if existing is not None:
        state.set_active_session_id(cleaned)
        return existing

    record = SessionRecord.new(title)
    record.session_id = cleaned

    records = state.load_sessions()
    records.insert(0, record)
    state.save_sessions(records)
    state.set_active_session_id(cleaned)

    logger.info("Imported external session %s", cleaned)
    return record