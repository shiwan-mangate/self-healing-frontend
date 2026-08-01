from __future__ import annotations

from typing import Awaitable, Callable, Optional
from urllib.parse import urlparse

from nicegui import ui

from ui import theme
from ui.components.notify import error
from utils.formatters import format_source_label


UrlHandler = Callable[[str], Awaitable[None]]


_EXAMPLE_URLS: tuple[tuple[str, str], ...] = (
    (
        "Wikipedia article",
        "https://en.wikipedia.org/wiki/Retrieval-augmented_generation",
    ),
    (
        "Documentation page",
        "https://docs.python.org/3/tutorial/introduction.html",
    ),
)

_BLOCKED_HOSTS: frozenset[str] = frozenset({
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
})


def normalize_url(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""

    lowered = cleaned.lower()
    if lowered.startswith("http://") or lowered.startswith("https://"):
        return cleaned

    if "://" in cleaned:
        return cleaned

    return f"https://{cleaned}"


def validate_url(value: str) -> Optional[str]:
    cleaned = value.strip()
    if not cleaned:
        return "Enter a URL to ingest."

    parsed = urlparse(cleaned)

    if parsed.scheme not in {"http", "https"}:
        return "Only http:// and https:// addresses can be ingested."

    if not parsed.netloc:
        return "That does not look like a valid web address."

    hostname = (parsed.hostname or "").lower()

    if hostname in _BLOCKED_HOSTS:
        return (
            "Local addresses cannot be ingested — the backend runs on a "
            "different machine and would not reach your computer."
        )

    if "." not in hostname and hostname not in _BLOCKED_HOSTS:
        return "That hostname does not look complete."

    return None


class UrlIngestField:
    def __init__(
        self,
        *,
        on_submit: UrlHandler,
        show_examples: bool = True,
    ) -> None:
        self._on_submit = on_submit
        self._show_examples = show_examples
        self._input: Optional[ui.input] = None
        self._button: Optional[ui.button] = None
        self._hint: Optional[ui.label] = None
        self._busy = False

    def build(self) -> ui.element:
        with ui.column().classes("w-full gap-2") as container:
            with ui.row().classes("w-full items-start gap-2 no-wrap"):
                self._input = (
                    ui.input(placeholder="https://example.com/article")
                    .props("dense outlined clearable")
                    .classes("flex-grow")
                )
                self._input.on("keydown.enter", self._handle_submit)
                self._input.on_value_change(self._handle_change)

                self._button = (
                    ui.button("Ingest", icon="download", on_click=self._handle_submit)
                    .props("unelevated no-caps")
                    .style(
                        f"background: {theme.PRIMARY}; color: white; "
                        "border-radius: 8px; height: 40px;"
                    )
                )

            self._hint = ui.label(
                "The page is fetched, parsed, chunked and embedded into the "
                "knowledge base."
            ).classes("text-xs shr-muted")

            if self._show_examples:
                self._build_examples()

        return container

    def _build_examples(self) -> None:
        with ui.row().classes("items-center gap-1.5 no-wrap flex-wrap"):
            ui.label("Try:").classes("text-xs shr-muted")

            for label, url in _EXAMPLE_URLS:
                chip = (
                    ui.row()
                    .classes("items-center gap-1 no-wrap px-2 py-1 shr-clickable")
                    .style(
                        f"background: {theme.PRIMARY}12; "
                        f"border: 1px solid {theme.PRIMARY}2b; border-radius: 999px;"
                    )
                    .tooltip(url)
                )
                with chip:
                    ui.icon("link", size="12px").style(f"color: {theme.PRIMARY}")
                    ui.label(label).classes("text-xs").style(f"color: {theme.PRIMARY}")

                chip.on("click", lambda u=url: self._set_value(u))

    def _set_value(self, url: str) -> None:
        if self._input is not None:
            self._input.set_value(url)
            self._clear_error()

    def _handle_change(self, event) -> None:
        raw = (event.value or "").strip()
        if not raw:
            self._clear_error()
            return

        problem = validate_url(normalize_url(raw))
        if problem:
            self._show_error(problem)
        else:
            self._clear_error()

    def _show_error(self, message: str) -> None:
        if self._input is not None:
            self._input.props("error")
            self._input.props(f'error-message="{message}"')

    def _clear_error(self) -> None:
        if self._input is not None:
            self._input.props(remove="error")
            self._input.props(remove="error-message")

    async def _handle_submit(self) -> None:
        if self._busy or self._input is None:
            return

        raw = (self._input.value or "").strip()
        normalized = normalize_url(raw)

        problem = validate_url(normalized)
        if problem:
            self._show_error(problem)
            error(problem)
            return

        self._clear_error()
        self._set_busy(True)

        try:
            await self._on_submit(normalized)
            self._input.set_value("")
        finally:
            self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy

        if self._input is not None:
            self._input.props("disable" if busy else "")
            if not busy:
                self._input.props(remove="disable")

        if self._button is not None:
            if busy:
                self._button.props("loading disable")
            else:
                self._button.props(remove="loading")
                self._button.props(remove="disable")

    @property
    def is_busy(self) -> bool:
        return self._busy


def url_result_row(
    source: str,
    *,
    succeeded: bool,
    chunks: int = 0,
    elapsed_sec: float = 0.0,
    message: Optional[str] = None,
) -> ui.element:
    color = theme.POSITIVE if succeeded else theme.NEGATIVE
    icon = "check_circle" if succeeded else "error_outline"

    with ui.row().classes("w-full items-center gap-3 no-wrap px-3 py-2").style(
        f"background: {color}0f; border: 1px solid {color}2b; border-radius: 8px;"
    ) as row:
        ui.icon(icon, size="18px").style(f"color: {color}")

        with ui.column().classes("gap-0 flex-grow min-w-0"):
            ui.link(
                format_source_label(source),
                source,
                new_tab=True,
            ).classes("text-sm font-medium no-underline ellipsis").style(
                f"color: {color}"
            ).tooltip(source)

            detail = message or (
                f"{chunks:,} chunks stored in {elapsed_sec:.1f}s"
                if succeeded
                else "Ingestion failed"
            )
            ui.label(detail).classes("text-xs shr-muted")

    return row


def url_note() -> ui.element:
    with ui.row().classes("w-full items-start gap-2 no-wrap px-3 py-2").style(
        "background: var(--shr-surface-alt); border-radius: 8px;"
    ) as note:
        ui.icon("info_outline", size="15px").classes("shr-muted").style(
            "margin-top: 1px;"
        )
        ui.label(
            "Pages behind a login, heavy JavaScript rendering, or aggressive "
            "bot protection may return little or no usable text."
        ).classes("text-xs shr-muted leading-snug")

    return note