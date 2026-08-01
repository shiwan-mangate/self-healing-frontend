from __future__ import annotations

from typing import Iterable, Optional

from nicegui import ui

from app.constants import (
    COLOR_NEUTRAL,
    RecoveryAction,
    action_meta,
)
from ui import theme
from utils.formatters import format_retry_label


_TERMINAL_ACTIONS: frozenset[str] = frozenset({
    RecoveryAction.STOP.value,
    RecoveryAction.ASK_CLARIFICATION.value,
})

_LEARNING_ACTIONS: frozenset[str] = frozenset({
    RecoveryAction.LOG_KNOWLEDGE_GAP.value,
})


def normalize_path(correction_path: Iterable[str]) -> list[str]:
    return [step.strip().lower() for step in correction_path if step and step.strip()]


def _step_dot(color: str, icon: str, *, dimmed: bool = False) -> None:
    opacity = "0.55" if dimmed else "1"
    with ui.element("div").classes("flex items-center justify-center").style(
        f"width: 30px; height: 30px; border-radius: 50%; flex-shrink: 0; "
        f"background: {color}1f; border: 1.5px solid {color}55; opacity: {opacity};"
    ):
        ui.icon(icon, size="16px").style(f"color: {color}")


def _connector(color: str) -> None:
    ui.element("div").style(
        f"width: 2px; height: 14px; margin-left: 14px; border-radius: 1px; "
        f"background: linear-gradient(to bottom, {color}55, {color}22);"
    )


def timeline_step(
    action: str,
    *,
    index: int,
    is_last: bool,
    show_description: bool = True,
) -> None:
    meta = action_meta(action)
    dimmed = action in _TERMINAL_ACTIONS

    with ui.row().classes("w-full items-start gap-3 no-wrap"):
        _step_dot(meta.color, meta.icon, dimmed=dimmed)

        with ui.column().classes("gap-0 flex-grow min-w-0 pt-1"):
            with ui.row().classes("items-center gap-2 no-wrap"):
                ui.label(meta.label).classes("text-sm font-medium leading-tight").style(
                    f"color: {meta.color}"
                )
                ui.label(f"Step {index}").classes("shr-mono text-xs shr-muted").style(
                    "opacity: 0.7;"
                )

            if show_description:
                ui.label(meta.description).classes(
                    "text-xs shr-muted leading-snug"
                )

    if not is_last:
        _connector(meta.color)


def healing_timeline(
    correction_path: Iterable[str],
    *,
    show_descriptions: bool = True,
) -> Optional[ui.element]:
    steps = normalize_path(correction_path)
    if not steps:
        return None

    with ui.column().classes("w-full gap-0") as container:
        for position, action in enumerate(steps, start=1):
            timeline_step(
                action,
                index=position,
                is_last=position == len(steps),
                show_description=show_descriptions,
            )

    return container


def compact_path(correction_path: Iterable[str], *, limit: int = 6) -> Optional[ui.element]:
    steps = normalize_path(correction_path)
    if not steps:
        return None

    visible = steps[:limit]
    overflow = len(steps) - len(visible)

    with ui.row().classes("items-center gap-1 no-wrap flex-wrap") as container:
        for position, action in enumerate(visible):
            meta = action_meta(action)

            with ui.row().classes("items-center gap-1 no-wrap px-2 py-1").style(
                f"background: {meta.color}1a; border: 1px solid {meta.color}33; "
                "border-radius: 999px;"
            ).tooltip(meta.description):
                ui.icon(meta.icon, size="13px").style(f"color: {meta.color}")
                ui.label(meta.label).classes("text-xs font-medium").style(
                    f"color: {meta.color}"
                )

            if position < len(visible) - 1 or overflow > 0:
                ui.icon("chevron_right", size="14px").classes("shr-muted").style(
                    "opacity: 0.5;"
                )

        if overflow > 0:
            ui.label(f"+{overflow}").classes("text-xs shr-muted font-medium")

    return container


def recovery_badge(
    *,
    recovery_used: bool,
    retry_count: int,
    step_count: int = 0,
) -> Optional[ui.element]:
    if not recovery_used and retry_count == 0 and step_count == 0:
        return None

    color = theme.SECONDARY

    with ui.row().classes("items-center gap-1.5 no-wrap px-2 py-1").style(
        f"background: {color}1a; border: 1px solid {color}38; border-radius: 999px;"
    ).tooltip(
        "The self-healing subsystem detected a quality problem and attempted recovery."
    ) as badge:
        ui.icon("healing", size="14px").style(f"color: {color}")
        ui.label("Self-healed").classes("text-xs font-semibold").style(f"color: {color}")

        if retry_count > 0:
            ui.label("·").classes("text-xs").style(f"color: {color}; opacity: 0.6;")
            ui.label(format_retry_label(retry_count)).classes("text-xs").style(
                f"color: {color}"
            )

    return badge


def _summary_line(correction_path: list[str], retry_count: int) -> str:
    if not correction_path:
        if retry_count > 0:
            return (
                f"The workflow retried {format_retry_label(retry_count).lower()} "
                "before returning this answer."
            )
        return "Recovery was engaged but no corrective steps were recorded."

    used_web = RecoveryAction.WEB_SEARCH.value in correction_path
    used_rewrite = RecoveryAction.REWRITE_QUERY.value in correction_path
    stopped = RecoveryAction.STOP.value in correction_path
    logged_gap = RecoveryAction.LOG_KNOWLEDGE_GAP.value in correction_path

    if stopped:
        base = "Recovery exhausted its retry budget and stopped"
    elif used_web and used_rewrite:
        base = "The query was rewritten and external sources were consulted"
    elif used_web:
        base = "Internal evidence was insufficient, so external sources were consulted"
    elif used_rewrite:
        base = "The query was rewritten to improve evidence retrieval"
    else:
        base = "Corrective steps were applied before answering"

    if logged_gap:
        base += ", and the missing topic was recorded for future ingestion"

    return f"{base}."


def healing_panel(
    correction_path: Iterable[str],
    *,
    retry_count: int = 0,
    recovery_used: bool = False,
    title: str = "Self-healing trace",
) -> Optional[ui.element]:
    steps = normalize_path(correction_path)

    if not steps and not recovery_used and retry_count == 0:
        return None

    color = theme.SECONDARY

    with ui.column().classes("w-full gap-3 p-4").style(
        f"background: {color}0d; border: 1px solid {color}2b; border-radius: 12px;"
    ) as panel:
        with ui.row().classes("w-full items-center gap-2 no-wrap"):
            ui.icon("healing", size="18px").style(f"color: {color}")
            ui.label(title).classes("text-sm font-semibold").style(f"color: {color}")
            ui.space()
            if retry_count > 0:
                ui.label(format_retry_label(retry_count)).classes(
                    "shr-mono text-xs"
                ).style(f"color: {color}; opacity: 0.85;")

        ui.label(_summary_line(steps, retry_count)).classes(
            "text-xs shr-muted leading-snug"
        )

        if steps:
            ui.element("div").classes("w-full").style(
                f"height: 1px; background: {color}22;"
            )
            healing_timeline(steps)

    return panel


def no_healing_note() -> ui.element:
    with ui.row().classes("items-center gap-2 no-wrap px-3 py-2").style(
        f"background: {theme.POSITIVE}12; border: 1px solid {theme.POSITIVE}2b; "
        "border-radius: 8px;"
    ) as note:
        ui.icon("verified", size="15px").style(f"color: {theme.POSITIVE}")
        ui.label("Answered on the first attempt — no recovery was needed.").classes(
            "text-xs"
        ).style(f"color: {theme.POSITIVE}")

    return note


def knowledge_gap_note(topic: Optional[str] = None) -> ui.element:
    color = "#c084d8"

    with ui.row().classes("items-start gap-2 no-wrap px-3 py-2").style(
        f"background: {color}12; border: 1px solid {color}2b; border-radius: 8px;"
    ) as note:
        ui.icon("bookmark_add", size="15px").style(f"color: {color}; margin-top: 1px;")

        with ui.column().classes("gap-0"):
            ui.label("Knowledge gap recorded").classes("text-xs font-semibold").style(
                f"color: {color}"
            )
            detail = (
                f"'{topic}' was missing from the knowledge base."
                if topic
                else "A missing topic was logged for future automated ingestion."
            )
            ui.label(detail).classes("text-xs leading-snug").style(
                f"color: {color}; opacity: 0.85;"
            )

    return note