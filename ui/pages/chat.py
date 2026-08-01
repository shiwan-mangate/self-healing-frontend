from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from nicegui import ui

from api.errors import ApiError
from api.models import ChatTurn
from app.constants import (
    EMPTY_CHAT_BODY,
    EMPTY_CHAT_HEADLINE,
    Route,
    SAMPLE_QUESTIONS,
)
from services import chat_service, session_service
from services.chat_service import ChatController
from ui import layout, theme
from ui.components.message_bubble import (
    assistant_bubble,
    error_bubble,
    history_bubble,
    user_bubble,
)
from ui.components.notify import api_error, warning
from ui.components.session_sidebar import SessionSidebar, session_header
from ui.components.skeleton import ThinkingIndicator, list_skeleton

logger = logging.getLogger(__name__)

_CHAT_WIDTH_STYLE = f"max-width: {theme.CHAT_MAX_WIDTH}px; margin-left: auto; margin-right: auto;"


class ChatPage:
    def __init__(self) -> None:
        self.controller = ChatController(session_service.get_active_id())
        self.sidebar: Optional[SessionSidebar] = None
        self.scroll: Optional[ui.scroll_area] = None
        self.messages: Optional[ui.element] = None
        self.header_slot: Optional[ui.element] = None
        self.composer: Optional[ui.textarea] = None
        self.send_button: Optional[ui.button] = None
        self.thinking: Optional[ThinkingIndicator] = None
        self.history_loaded = False

    def build(self) -> None:
        with layout.full_height_shell(Route.CHAT):
            with ui.row().classes(
                "w-full gap-0 no-wrap items-stretch shr-fill"
            ).style("flex: 1 1 auto; min-height: 0; overflow: hidden;"):
                self.sidebar = SessionSidebar(
                    on_select=self._handle_session_change,
                    on_create=self._handle_session_change,
                )
                sidebar_element = self.sidebar.build()
                sidebar_element.classes(add="shr-session-panel")

                self._build_panel()

        ui.timer(0.1, self._load_history, once=True)

    def _build_panel(self) -> None:
        with ui.column().classes("gap-0 no-wrap shr-flex-min").style(
            "flex: 1 1 0%; min-width: 0; min-height: 0; height: 100%;"
        ):
            self.header_slot = ui.column().classes("w-full gap-0 shr-fill").style(
                "flex-shrink: 0;"
            )
            self._render_header()

            self.scroll = (
                ui.scroll_area()
                .classes("w-full shr-scroll shr-fill")
                .style("flex: 1 1 auto; min-height: 0;")
            )
            with self.scroll:
                self.messages = ui.column().classes(
                    "w-full gap-4 px-4 py-5 shr-fill"
                ).style(_CHAT_WIDTH_STYLE)

            self._build_composer()

    def _render_header(self) -> None:
        if self.header_slot is None:
            return

        self.header_slot.clear()
        record = session_service.find(self.controller.session_id)
        if record is None:
            return

        with self.header_slot:
            session_header(record, on_rename=self._handle_rename)

    def _build_composer(self) -> None:
        with ui.column().classes("w-full gap-1 px-4 py-3 shr-fill").style(
            "border-top: 1px solid var(--shr-border); "
            "background: var(--shr-surface); flex-shrink: 0;"
        ):
            with ui.row().classes(
                "w-full items-end gap-2 no-wrap shr-fill"
            ).style(_CHAT_WIDTH_STYLE):
                self.composer = (
                    ui.textarea(placeholder="Ask a question about your documents…")
                    .props("outlined dense autogrow input-class=text-sm")
                    .classes("shr-flex-min")
                    .style("flex: 1 1 auto; max-height: 160px;")
                )
                self.composer.on("keydown", self._handle_key, ["key", "shiftKey"])

                self.send_button = (
                    ui.button(icon="send", on_click=self._handle_send)
                    .props("unelevated round")
                    .style(
                        f"background: {theme.PRIMARY}; color: white; flex-shrink: 0;"
                    )
                    .tooltip("Send (Enter)")
                )

            with ui.row().classes(
                "w-full items-center gap-2 no-wrap shr-fill"
            ).style(_CHAT_WIDTH_STYLE):
                ui.label("Enter to send · Shift+Enter for a new line").classes(
                    "text-xs shr-muted"
                ).style("opacity: 0.7; white-space: nowrap;")
                ui.space()
                ui.label(
                    "Answers are verified for grounding and hallucination"
                ).classes("text-xs shr-muted hidden md:block").style(
                    "opacity: 0.7; white-space: nowrap;"
                )

    async def _handle_key(self, event) -> None:
        args = event.args or {}
        if args.get("key") != "Enter" or args.get("shiftKey"):
            return
        await self._handle_send()

    def _handle_rename(self) -> None:
        record = session_service.find(self.controller.session_id)
        if record is None or self.sidebar is None:
            return
        self.sidebar.open_rename(record)

    def _handle_session_change(self, session_id: str) -> None:
        self.controller.set_session(session_id)
        self.history_loaded = False
        self._render_header()

        if self.messages is not None:
            self.messages.clear()

        ui.timer(0.05, self._load_history, once=True)

    async def _load_history(self) -> None:
        if self.messages is None or self.history_loaded:
            return

        self.history_loaded = True
        self.messages.clear()

        with self.messages:
            placeholder = ui.column().classes("w-full gap-3 shr-fill")
            with placeholder:
                list_skeleton(3)

        try:
            history = await session_service.sync_from_server(self.controller.session_id)
        except Exception:
            logger.exception("History load failed")
            history = None

        placeholder.delete()

        if history is None or history.is_empty:
            self._render_empty_state()
            return

        with self.messages:
            for message in history.messages:
                history_bubble(message.role, message.content, message.timestamp)

            with ui.row().classes("w-full items-center gap-2 no-wrap py-1 shr-fill"):
                ui.element("div").style(
                    "flex: 1 1 auto; height: 1px; background: var(--shr-border);"
                )
                ui.label("Earlier messages restored from the server").classes(
                    "text-xs shr-muted"
                ).style("opacity: 0.65; white-space: nowrap; flex-shrink: 0;")
                ui.element("div").style(
                    "flex: 1 1 auto; height: 1px; background: var(--shr-border);"
                )

        self._scroll_to_bottom()

    def _render_empty_state(self) -> None:
        if self.messages is None:
            return

        with self.messages:
            with ui.column().classes(
                "w-full items-center justify-center gap-3 py-16 px-4 shr-fill"
            ):
                ui.icon("autorenew", size="42px").style(
                    f"color: {theme.PRIMARY}; opacity: 0.6;"
                )
                ui.label(EMPTY_CHAT_HEADLINE).classes("text-lg font-semibold")
                ui.label(EMPTY_CHAT_BODY).classes(
                    "text-sm shr-muted text-center leading-snug"
                ).style("max-width: 28rem;")

                with ui.column().classes("gap-2 mt-3 w-full items-center").style(
                    "max-width: 26rem;"
                ):
                    for question in SAMPLE_QUESTIONS:
                        chip = (
                            ui.row()
                            .classes(
                                "w-full items-center gap-2 no-wrap px-3 py-2 "
                                "shr-clickable shr-fill"
                            )
                            .style(
                                "background: var(--shr-surface-alt); "
                                "border: 1px solid var(--shr-border); "
                                "border-radius: 8px;"
                            )
                        )
                        with chip:
                            ui.icon("north_east", size="14px").classes(
                                "shr-muted"
                            ).style("flex-shrink: 0;")
                            ui.label(question).classes("text-sm")

                        chip.on("click", lambda q=question: self._use_sample(q))

    def _use_sample(self, question: str) -> None:
        if self.composer is not None:
            self.composer.set_value(question)
            self.composer.run_method("focus")

    async def _handle_send(self) -> None:
        if self.composer is None or self.messages is None:
            return

        if self.controller.is_busy:
            warning("Please wait for the current answer to finish.")
            return

        question = (self.composer.value or "").strip()
        problem = chat_service.validate_question(question)
        if problem:
            warning(problem)
            return

        if not self.controller.turns:
            self.messages.clear()

        self.composer.set_value("")
        self._set_sending(True)

        with self.messages:
            user_bubble(question, timestamp=datetime.now(timezone.utc))
            self.thinking = ThinkingIndicator(on_cancel=self._handle_cancel)
            self.thinking.build()

        self._scroll_to_bottom()

        try:
            turn = await self.controller.submit(question)
        except RuntimeError:
            warning("A query is already in progress.")
            self._dismiss_thinking()
            self._set_sending(False)
            return
        except ApiError as exc:
            api_error(exc)
            turn = ChatTurn.pending(question).with_error(exc.message)
        finally:
            self._dismiss_thinking()
            self._set_sending(False)

        with self.messages:
            if turn.response is not None:
                query_id = turn.response.query_id
                assistant_bubble(
                    turn.response,
                    turn.evaluation,
                    on_retry=lambda q=question: self._retry(q),
                    on_inspect=lambda qid=query_id: self._inspect(qid),
                )
            else:
                error_bubble(
                    turn.error or "The question could not be answered.",
                    on_retry=lambda q=question: self._retry(q),
                )

        if self.sidebar is not None:
            self.sidebar.refresh()

        self._render_header()
        self._scroll_to_bottom()

    def _dismiss_thinking(self) -> None:
        if self.thinking is not None:
            self.thinking.dismiss()
            self.thinking = None

    def _handle_cancel(self) -> None:
        self.controller.cancel()

    async def _retry(self, question: str) -> None:
        if self.controller.is_busy:
            warning("Please wait for the current answer to finish.")
            return
        if self.composer is not None:
            self.composer.set_value(question)
        await self._handle_send()

    def _inspect(self, query_id: str) -> None:
        ui.navigate.to(f"{Route.EVALUATION}?query_id={query_id}")

    def _set_sending(self, sending: bool) -> None:
        if self.send_button is not None:
            if sending:
                self.send_button.props("loading disable")
            else:
                self.send_button.props(remove="loading")
                self.send_button.props(remove="disable")

        if self.composer is not None:
            if sending:
                self.composer.props("readonly")
            else:
                self.composer.props(remove="readonly")

    def _scroll_to_bottom(self) -> None:
        if self.scroll is not None:
            ui.timer(0.05, lambda: self.scroll.scroll_to(percent=1.0), once=True)


@ui.page(Route.CHAT)
def chat_page() -> None:
    page = ChatPage()
    page.build()