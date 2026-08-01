from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse


def format_latency(milliseconds: float) -> str:
    if milliseconds < 0:
        return "—"
    if milliseconds < 1000:
        return f"{milliseconds:.0f} ms"

    seconds = milliseconds / 1000.0
    if seconds < 60:
        return f"{seconds:.1f} s"

    minutes = int(seconds // 60)
    remainder = seconds - (minutes * 60)
    return f"{minutes}m {remainder:.0f}s"


def format_duration_sec(seconds: float) -> str:
    return format_latency(seconds * 1000.0)


def format_percent(score: Optional[float], decimals: int = 0) -> str:
    if score is None:
        return "—"
    clamped = max(0.0, min(1.0, score))
    return f"{clamped * 100:.{decimals}f}%"


def format_score(score: Optional[float], decimals: int = 2) -> str:
    if score is None:
        return "—"
    return f"{max(0.0, min(1.0, score)):.{decimals}f}"


def format_count(value: int, singular: str, plural: Optional[str] = None) -> str:
    label = singular if value == 1 else (plural or f"{singular}s")
    return f"{value:,} {label}"


def format_bytes(size: int) -> str:
    if size < 0:
        return "—"
    if size < 1024:
        return f"{size} B"

    kilobytes = size / 1024
    if kilobytes < 1024:
        return f"{kilobytes:.0f} KB"

    megabytes = kilobytes / 1024
    if megabytes < 1024:
        return f"{megabytes:.1f} MB"

    return f"{megabytes / 1024:.2f} GB"


def format_timestamp(value: datetime, include_seconds: bool = False) -> str:
    local = value.astimezone()
    pattern = "%d %b %Y, %H:%M:%S" if include_seconds else "%d %b %Y, %H:%M"
    return local.strftime(pattern)


def format_time_only(value: datetime) -> str:
    return value.astimezone().strftime("%H:%M")


def format_relative(value: datetime) -> str:
    now = datetime.now(timezone.utc)
    reference = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    delta = (now - reference).total_seconds()

    if delta < 0:
        return "just now"
    if delta < 45:
        return "just now"
    if delta < 90:
        return "a minute ago"

    minutes = delta / 60
    if minutes < 60:
        return f"{int(minutes)} minutes ago"

    hours = minutes / 60
    if hours < 24:
        count = int(hours)
        return "an hour ago" if count == 1 else f"{count} hours ago"

    days = hours / 24
    if days < 7:
        count = int(days)
        return "yesterday" if count == 1 else f"{count} days ago"

    if days < 30:
        weeks = int(days / 7)
        return "a week ago" if weeks == 1 else f"{weeks} weeks ago"

    if days < 365:
        months = int(days / 30)
        return "a month ago" if months == 1 else f"{months} months ago"

    years = int(days / 365)
    return "a year ago" if years == 1 else f"{years} years ago"


def truncate(text: str, limit: int, ellipsis: str = "…") -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    cut = max(1, limit - len(ellipsis))
    return f"{collapsed[:cut].rstrip()}{ellipsis}"


def truncate_middle(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]

    head = (limit - 1) // 2
    tail = limit - 1 - head
    return f"{text[:head]}…{text[-tail:]}"


def format_source_label(source: str, limit: int = 48) -> str:
    cleaned = source.strip()
    parsed = urlparse(cleaned)

    if parsed.scheme in {"http", "https"} and parsed.netloc:
        path = parsed.path.rstrip("/")
        if path:
            tail = path.rsplit("/", 1)[-1]
            label = f"{parsed.netloc}/{tail}" if tail else parsed.netloc
        else:
            label = parsed.netloc
        return truncate_middle(label, limit)

    return truncate_middle(cleaned.replace("\\", "/").rsplit("/", 1)[-1], limit)


def format_filename(filename: str, limit: int = 40) -> str:
    name = filename.strip().replace("\\", "/").rsplit("/", 1)[-1]
    return truncate_middle(name, limit)


def file_extension(filename: str) -> str:
    name = filename.strip().lower()
    dot = name.rfind(".")
    return name[dot:] if dot > 0 else ""


def format_action_sequence(actions: list[str]) -> str:
    return " → ".join(action.replace("_", " ").title() for action in actions if action.strip())


def format_retry_label(retry_count: int) -> str:
    if retry_count <= 0:
        return "No retries"
    if retry_count == 1:
        return "1 retry"
    return f"{retry_count} retries"


def format_citation_marker(index: Optional[int]) -> str:
    return f"[{index}]" if index is not None else "[·]"


def humanize_key(key: str) -> str:
    return key.replace("_", " ").strip().title()


def pluralize(count: int, singular: str, plural: Optional[str] = None) -> str:
    return singular if count == 1 else (plural or f"{singular}s")