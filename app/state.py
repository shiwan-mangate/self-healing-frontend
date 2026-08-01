from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from nicegui import app

from app.constants import (
    DEFAULT_SESSION_TITLE,
    MAX_INGESTION_LOG_ENTRIES,
    MAX_SESSION_TITLE_LENGTH,
    MAX_STORED_SESSIONS,
    StorageKey,
)

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: Any) -> datetime:
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


def _clean_title(value: str) -> str:
    collapsed = " ".join(value.split())
    if len(collapsed) <= MAX_SESSION_TITLE_LENGTH:
        return collapsed
    return f"{collapsed[: MAX_SESSION_TITLE_LENGTH - 1].rstrip()}…"


@dataclass(slots=True)
class SessionRecord:
    session_id: str
    title: str
    created_at: str
    last_used: str
    message_count: int = 0

    @property
    def created_dt(self) -> datetime:
        return _parse_iso(self.created_at)

    @property
    def last_used_dt(self) -> datetime:
        return _parse_iso(self.last_used)

    @property
    def is_untitled(self) -> bool:
        return self.title == DEFAULT_SESSION_TITLE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Optional["SessionRecord"]:
        session_id = str(payload.get("session_id", "")).strip()
        if not session_id:
            return None

        title = str(payload.get("title", "")).strip() or DEFAULT_SESSION_TITLE
        created = str(payload.get("created_at", "")).strip() or _now_iso()
        last_used = str(payload.get("last_used", "")).strip() or created

        raw_count = payload.get("message_count", 0)
        try:
            count = max(0, int(raw_count))
        except (TypeError, ValueError):
            count = 0

        return cls(
            session_id=session_id,
            title=_clean_title(title),
            created_at=created,
            last_used=last_used,
            message_count=count,
        )

    @classmethod
    def new(cls, title: Optional[str] = None) -> "SessionRecord":
        stamp = _now_iso()
        return cls(
            session_id=f"ui-{uuid.uuid4().hex[:20]}",
            title=_clean_title(title) if title else DEFAULT_SESSION_TITLE,
            created_at=stamp,
            last_used=stamp,
            message_count=0,
        )


@dataclass(slots=True)
class IngestionRecord:
    source: str
    kind: str
    succeeded: bool
    documents_processed: int = 0
    chunks_persisted: int = 0
    elapsed_time_sec: float = 0.0
    warnings: list[str] = field(default_factory=list)
    error: Optional[str] = None
    ingested_at: str = field(default_factory=_now_iso)

    @property
    def ingested_dt(self) -> datetime:
        return _parse_iso(self.ingested_at)

    @property
    def is_url(self) -> bool:
        return self.kind == "url"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Optional["IngestionRecord"]:
        source = str(payload.get("source", "")).strip()
        if not source:
            return None

        raw_warnings = payload.get("warnings")
        warnings = (
            [str(w) for w in raw_warnings if str(w).strip()]
            if isinstance(raw_warnings, list)
            else []
        )

        def _int(key: str) -> int:
            try:
                return max(0, int(payload.get(key, 0)))
            except (TypeError, ValueError):
                return 0

        try:
            elapsed = max(0.0, float(payload.get("elapsed_time_sec", 0.0)))
        except (TypeError, ValueError):
            elapsed = 0.0

        error = payload.get("error")

        return cls(
            source=source,
            kind=str(payload.get("kind", "file")).strip().lower() or "file",
            succeeded=bool(payload.get("succeeded", False)),
            documents_processed=_int("documents_processed"),
            chunks_persisted=_int("chunks_persisted"),
            elapsed_time_sec=elapsed,
            warnings=warnings,
            error=str(error).strip() if error else None,
            ingested_at=str(payload.get("ingested_at", "")).strip() or _now_iso(),
        )


def _storage() -> Any:
    return app.storage.user


def _read_list(key: str) -> list[dict[str, Any]]:
    raw = _storage().get(key)
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, Mapping)]


def _write_list(key: str, items: list[dict[str, Any]]) -> None:
    _storage()[key] = items


def load_sessions() -> list[SessionRecord]:
    records: list[SessionRecord] = []
    for payload in _read_list(StorageKey.SESSIONS):
        record = SessionRecord.from_dict(payload)
        if record is not None:
            records.append(record)

    records.sort(key=lambda r: r.last_used, reverse=True)
    return records


def save_sessions(records: list[SessionRecord]) -> None:
    ordered = sorted(records, key=lambda r: r.last_used, reverse=True)
    trimmed = ordered[:MAX_STORED_SESSIONS]
    _write_list(StorageKey.SESSIONS, [record.to_dict() for record in trimmed])


def find_session(session_id: str) -> Optional[SessionRecord]:
    target = session_id.strip()
    for record in load_sessions():
        if record.session_id == target:
            return record
    return None


def create_session(title: Optional[str] = None) -> SessionRecord:
    record = SessionRecord.new(title)
    records = load_sessions()
    records.insert(0, record)
    save_sessions(records)
    set_active_session_id(record.session_id)
    logger.info("Created session %s", record.session_id)
    return record


def update_session(
    session_id: str,
    *,
    title: Optional[str] = None,
    message_count: Optional[int] = None,
    touch: bool = True,
) -> Optional[SessionRecord]:
    records = load_sessions()
    updated: Optional[SessionRecord] = None

    for record in records:
        if record.session_id != session_id.strip():
            continue

        if title is not None:
            cleaned = _clean_title(title)
            if cleaned:
                record.title = cleaned

        if message_count is not None:
            record.message_count = max(0, message_count)

        if touch:
            record.last_used = _now_iso()

        updated = record
        break

    if updated is not None:
        save_sessions(records)

    return updated


def rename_session(session_id: str, title: str) -> Optional[SessionRecord]:
    cleaned = _clean_title(title)
    if not cleaned:
        return find_session(session_id)
    return update_session(session_id, title=cleaned, touch=False)


def title_from_question(session_id: str, question: str) -> Optional[SessionRecord]:
    record = find_session(session_id)
    if record is None or not record.is_untitled:
        return record
    return update_session(session_id, title=question, touch=False)


def delete_session(session_id: str) -> None:
    target = session_id.strip()
    records = [record for record in load_sessions() if record.session_id != target]
    save_sessions(records)

    if get_active_session_id() == target:
        _storage()[StorageKey.ACTIVE_SESSION] = records[0].session_id if records else ""

    logger.info("Deleted session %s", target)


def clear_sessions() -> None:
    _write_list(StorageKey.SESSIONS, [])
    _storage()[StorageKey.ACTIVE_SESSION] = ""


def get_active_session_id() -> str:
    value = _storage().get(StorageKey.ACTIVE_SESSION, "")
    return str(value).strip() if value else ""


def set_active_session_id(session_id: str) -> None:
    _storage()[StorageKey.ACTIVE_SESSION] = session_id.strip()


def ensure_active_session() -> SessionRecord:
    records = load_sessions()
    active_id = get_active_session_id()

    if active_id:
        for record in records:
            if record.session_id == active_id:
                return record

    if records:
        set_active_session_id(records[0].session_id)
        return records[0]

    return create_session()


def load_ingestion_log() -> list[IngestionRecord]:
    records: list[IngestionRecord] = []
    for payload in _read_list(StorageKey.INGESTION_LOG):
        record = IngestionRecord.from_dict(payload)
        if record is not None:
            records.append(record)

    records.sort(key=lambda r: r.ingested_at, reverse=True)
    return records


def append_ingestion(record: IngestionRecord) -> None:
    records = load_ingestion_log()
    records.insert(0, record)
    trimmed = records[:MAX_INGESTION_LOG_ENTRIES]
    _write_list(StorageKey.INGESTION_LOG, [item.to_dict() for item in trimmed])


def clear_ingestion_log() -> None:
    _write_list(StorageKey.INGESTION_LOG, [])


def get_user_id() -> str:
    value = _storage().get(StorageKey.USER_ID)
    if isinstance(value, str) and value.strip():
        return value.strip()

    generated = f"ui-user-{uuid.uuid4().hex[:16]}"
    _storage()[StorageKey.USER_ID] = generated
    return generated


def is_dark_mode() -> bool:
    value = _storage().get(StorageKey.DARK_MODE)
    return True if value is None else bool(value)


def set_dark_mode(enabled: bool) -> None:
    _storage()[StorageKey.DARK_MODE] = bool(enabled)


def toggle_dark_mode() -> bool:
    enabled = not is_dark_mode()
    set_dark_mode(enabled)
    return enabled