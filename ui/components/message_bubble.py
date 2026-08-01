from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from nicegui import ui

from api.models import ChatResponse, ChatTurn, EvaluationResponse
from app.constants import NO_EVALUATION_MESSAGE
from ui import theme
from ui.components.citation_panel import (
    citation_expander,
    citations_footer,
    no_citations_note,
)
from ui.components.healing_timeline import healing_panel, no_healing_note
from ui.components.metrics_row import metrics_row, trace_row
from ui.components.notify import copy_to_clipboard, warning_list
from ui.components.ragas_card import ragas_expander
from utils.formatters import format_time_only
from utils.markdown import is_apology, plain_text, prepare_answer


_MAX_BUBBLE_WIDTH = "min(760px, 100%)"


def _avatar(icon: str, color: str, *, size: int = 30) -> ui.element:
    with ui.element("div").classes("flex items-center justify-center").style(
        f"width: {size}px; height: {size}px; border-radius: 9px; flex-shrink: 0; "
        f"background: {color}1f; border: 1px solid {color}38;"
    ) as avatar:
        ui.icon(icon, size=f"{int(size * 0.55)}px").style(f"color: {color}")

    return avatar


def user_bubble(text: str, *, timestamp: Optional[datetime] = None) -> ui.element:
    with ui.row().classes("w-full justify-end gap-2 no-wrap shr-fade-in") as row:
        with ui.column().classes("items-end gap-1 min-w-0").style(
            f"max-width: {_MAX_BUBBLE_WIDTH};"
        ):
            with ui.element("div").classes("shr-bubble-user px-4 py-2.5").style(
                "max-width: 100%;"
            ):
                ui.label(text).classes("text-sm leading-relaxed").style(
                    "white-space: pre-wrap; word-break: break-word;"
                )

            if timestamp is not None:
                ui.label(format_time_only(timestamp)).classes(
                    "text-xs shr-muted"
                ).style("opacity: 0.6;")

        _avatar("person", theme.PRIMARY)

    return row


def assistant_answer(text: str, citations: list) -> ui.element:
    rendered = prepare_answer(text, citations)
    return ui.markdown(rendered).classes("shr-answer w-full")


def apology_notice(text: str) -> ui.element:
    with ui.row().classes("w-full items-start gap-2.5 no-wrap px-3 py-2.5").style(
        f"background: {theme.WARNING}12; border: 1px solid {theme.WARNING}2b; "
        "border-radius: 10px;"
    ) as notice:
        ui.icon("search_off", size="18px").style(
            f"color: {theme.WARNING}; margin-top: 1px;"
        )

        with ui.column().classes("gap-0.5 min-w-0"):
            ui.label("No grounded answer available").classes(
                "text-sm font-semibold"
            ).style(f"color: {theme.WARNING}")
            ui.label(text).classes("text-sm leading-snug").style(
                "color: var(--shr-text); opacity: 0.85;"
            )

    return notice


def _action_bar(
    response: ChatResponse,
    *,
    on_retry: Optional[Callable[[], None]] = None,
    on_inspect: Optional[Callable[[], None]] = None,
) -> ui.element:
    with ui.row().classes("items-center gap-1 no-wrap") as bar:
        ui.button(
            icon="content_copy",
            on_click=lambda: copy_to_clipboard(
                plain_text(response.answer), label="Answer copied"
            ),
        ).props("flat dense round size=sm").classes("shr-muted").tooltip("Copy answer")

        if on_inspect is not None:
            ui.button(icon="fact_check", on_click=on_inspect).props(
                "flat dense round size=sm"
            ).classes("shr-muted").tooltip("Open full evaluation")

        if on_retry is not None:
            ui.button(icon="refresh", on_click=on_retry).props(
                "flat dense round size=sm"
            ).classes("shr-muted").tooltip("Ask again")

    return bar


def assistant_bubble(
    response: ChatResponse,
    evaluation: Optional[EvaluationResponse] = None,
    *,
    on_retry: Optional[Callable[[], None]] = None,
    on_inspect: Optional[Callable[[], None]] = None,
    show_trace: bool = True,
) -> ui.element:
    refused = is_apology(response.answer)

    with ui.row().classes("w-full justify-start gap-2 no-wrap shr-fade-in") as row:
        _avatar("auto_awesome", theme.SECONDARY)

        with ui.column().classes("gap-2 min-w-0 flex-grow").style(
            f"max-width: {_MAX_BUBBLE_WIDTH};"
        ):
            with ui.column().classes("shr-bubble-assistant px-4 py-3 gap-3 w-full"):
                if refused:
                    apology_notice(response.answer)
                else:
                    assistant_answer(response.answer, response.citations)

                if response.warnings:
                    warning_list(response.warnings)

                if not refused and not response.has_citations:
                    no_citations_note()

                if response.has_citations:
                    citations_footer(response.citations)

            metrics_row(response, evaluation)

            with ui.column().classes("w-full gap-1.5"):
                citation_expander(response.citations)

                if response.has_healing:
                    with ui.expansion(
                        "Self-healing trace",
                        icon="healing",
                    ).classes("w-full shr-surface-alt").props("dense expand-separator"):
                        with ui.column().classes("w-full pt-2 pb-1"):
                            healing_panel(
                                response.correction_path,
                                retry_count=response.retry_count,
                                recovery_used=response.recovery_used,
                                title="Recovery steps",
                            )

                if evaluation is not None:
                    ragas_expander(evaluation.ragas)
                else:
                    with ui.row().classes("items-center gap-2 no-wrap px-3 py-1.5"):
                        ui.icon("info_outline", size="14px").classes("shr-muted")
                        ui.label(NO_EVALUATION_MESSAGE).classes("text-xs shr-muted")

            with ui.row().classes("w-full items-center gap-3 no-wrap"):
                _action_bar(response, on_retry=on_retry, on_inspect=on_inspect)
                ui.space()
                if show_trace:
                    trace_row(response.query_id)

    return row


def error_bubble(
    message: str,
    *,
    detail: Optional[str] = None,
    on_retry: Optional[Callable[[], None]] = None,
) -> ui.element:
    with ui.row().classes("w-full justify-start gap-2 no-wrap shr-fade-in") as row:
        _avatar("error_outline", theme.NEGATIVE)

        with ui.column().classes("gap-2 min-w-0 flex-grow").style(
            f"max-width: {_MAX_BUBBLE_WIDTH};"
        ):
            with ui.column().classes("px-4 py-3 gap-2 w-full").style(
                f"background: {theme.NEGATIVE}0f; "
                f"border: 1px solid {theme.NEGATIVE}2b; "
                "border-radius: 8px 16px 16px 16px;"
            ):
                ui.label("This question could not be answered").classes(
                    "text-sm font-semibold"
                ).style(f"color: {theme.NEGATIVE}")

                ui.label(message).classes("text-sm leading-snug")

                if detail:
                    ui.label(detail).classes("shr-mono text-xs shr-muted").style(
                        "opacity: 0.75;"
                    )

                if on_retry is not None:
                    with ui.row().classes("items-center gap-2 mt-1"):
                        ui.button("Try again", icon="refresh", on_click=on_retry).props(
                            "flat dense size=sm"
                        ).style(f"color: {theme.NEGATIVE}")

    return row


def turn_bubbles(
    turn: ChatTurn,
    *,
    on_retry: Optional[Callable[[], None]] = None,
    on_inspect: Optional[Callable[[], None]] = None,
) -> None:
    user_bubble(turn.question, timestamp=turn.asked_at)

    if turn.response is not None:
        assistant_bubble(
            turn.response,
            turn.evaluation,
            on_retry=on_retry,
            on_inspect=on_inspect,
        )
    elif turn.error:
        error_bubble(turn.error, on_retry=on_retry)


def history_bubble(role: str, content: str, timestamp: datetime) -> ui.element:
    if role == "user":
        return user_bubble(content, timestamp=timestamp)

    with ui.row().classes("w-full justify-start gap-2 no-wrap shr-fade-in") as row:
        _avatar("auto_awesome", theme.SECONDARY)

        with ui.column().classes("gap-1 min-w-0 flex-grow").style(
            f"max-width: {_MAX_BUBBLE_WIDTH};"
        ):
            with ui.column().classes("shr-bubble-assistant px-4 py-3 w-full"):
                ui.markdown(content).classes("shr-answer w-full")

            ui.label(format_time_only(timestamp)).classes("text-xs shr-muted").style(
                "opacity: 0.6;"
            )

    return row