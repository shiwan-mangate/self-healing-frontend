from __future__ import annotations

from typing import Callable, Optional

from nicegui import ui

from api.errors import ApiError, ErrorDisplay
from ui import theme


_DEFAULT_TIMEOUT = 3500
_LONG_TIMEOUT = 6000
_ERROR_TIMEOUT = 7000


def success(message: str, *, caption: Optional[str] = None) -> None:
    ui.notify(
        message,
        caption=caption,
        type="positive",
        icon="check_circle",
        position="bottom-right",
        timeout=_DEFAULT_TIMEOUT,
        progress=True,
    )


def info(message: str, *, caption: Optional[str] = None) -> None:
    ui.notify(
        message,
        caption=caption,
        type="info",
        icon="info",
        position="bottom-right",
        timeout=_DEFAULT_TIMEOUT,
        progress=True,
    )


def warning(message: str, *, caption: Optional[str] = None) -> None:
    ui.notify(
        message,
        caption=caption,
        type="warning",
        icon="warning_amber",
        position="bottom-right",
        timeout=_LONG_TIMEOUT,
        progress=True,
    )


def error(message: str, *, caption: Optional[str] = None) -> None:
    ui.notify(
        message,
        caption=caption,
        type="negative",
        icon="error_outline",
        position="bottom-right",
        timeout=_ERROR_TIMEOUT,
        progress=True,
        close_button="Dismiss",
    )


def api_error(exc: ApiError, *, retry: Optional[Callable[[], None]] = None) -> None:
    display = ErrorDisplay.from_error(exc)

    actions: list[dict[str, object]] = []
    if retry is not None and display.retryable:
        actions.append({"label": "Retry", "color": "white", "handler": retry})
    actions.append({"label": "Dismiss", "color": "white"})

    ui.notify(
        display.message,
        caption=display.trace or None,
        type="warning" if display.retryable else "negative",
        icon=display.icon,
        position="bottom-right",
        timeout=_ERROR_TIMEOUT,
        progress=True,
        multi_line=True,
        actions=actions,
    )


def error_card(exc: ApiError, *, on_retry: Optional[Callable[[], None]] = None) -> ui.element:
    display = ErrorDisplay.from_error(exc)

    with ui.column().classes("w-full gap-2 p-4 shr-fade-in").style(
        f"background: {display.color}12; "
        f"border: 1px solid {display.color}33; "
        f"border-radius: 12px;"
    ) as card:
        with ui.row().classes("items-start gap-3 no-wrap w-full"):
            ui.icon(display.icon, size="22px").style(f"color: {display.color}")

            with ui.column().classes("gap-1 flex-grow"):
                ui.label(display.title).classes("text-sm font-semibold").style(
                    f"color: {display.color}"
                )
                ui.label(display.message).classes("text-sm leading-snug")

        if display.details:
            with ui.expansion("Details").classes("w-full").props("dense"):
                with ui.column().classes("gap-1 py-1"):
                    for detail in display.details:
                        ui.label(detail).classes("shr-mono text-xs shr-muted")

        with ui.row().classes("items-center gap-3 w-full no-wrap"):
            if display.trace:
                ui.label(display.trace).classes("shr-mono text-xs shr-muted")
            ui.space()
            if on_retry is not None and display.retryable:
                ui.button("Try again", icon="refresh", on_click=on_retry).props(
                    "flat dense size=sm"
                ).style(f"color: {display.color}")

    return card


def inline_warning(message: str, *, icon: str = "warning_amber") -> ui.element:
    with ui.row().classes("w-full items-start gap-2 no-wrap px-3 py-2").style(
        f"background: {theme.WARNING}14; "
        f"border: 1px solid {theme.WARNING}30; "
        f"border-radius: 8px;"
    ) as row:
        ui.icon(icon, size="16px").style(f"color: {theme.WARNING}; margin-top: 2px;")
        ui.label(message).classes("text-xs leading-snug").style(f"color: {theme.WARNING}")

    return row


def warning_list(messages: list[str], *, title: str = "Warnings") -> Optional[ui.element]:
    if not messages:
        return None

    if len(messages) == 1:
        return inline_warning(messages[0])

    with ui.column().classes("w-full gap-1 px-3 py-2").style(
        f"background: {theme.WARNING}14; "
        f"border: 1px solid {theme.WARNING}30; "
        f"border-radius: 8px;"
    ) as container:
        with ui.row().classes("items-center gap-2 no-wrap"):
            ui.icon("warning_amber", size="16px").style(f"color: {theme.WARNING}")
            ui.label(f"{title} ({len(messages)})").classes("text-xs font-semibold").style(
                f"color: {theme.WARNING}"
            )

        for message in messages:
            with ui.row().classes("items-start gap-2 no-wrap pl-6"):
                ui.label("•").classes("text-xs").style(f"color: {theme.WARNING}")
                ui.label(message).classes("text-xs leading-snug").style(
                    f"color: {theme.WARNING}"
                )

    return container


async def confirm(
    message: str,
    *,
    title: str = "Are you sure?",
    confirm_label: str = "Confirm",
    cancel_label: str = "Cancel",
    danger: bool = False,
) -> bool:
    color = theme.NEGATIVE if danger else theme.PRIMARY

    with ui.dialog() as dialog, ui.card().classes("shr-surface p-5 gap-3").style(
        "min-width: 320px; max-width: 420px;"
    ):
        with ui.row().classes("items-center gap-2 no-wrap"):
            ui.icon("help_outline" if not danger else "warning_amber", size="22px").style(
                f"color: {color}"
            )
            ui.label(title).classes("text-base font-semibold")

        ui.label(message).classes("text-sm shr-muted leading-snug")

        with ui.row().classes("w-full justify-end gap-2 mt-1 no-wrap"):
            ui.button(cancel_label, on_click=lambda: dialog.submit(False)).props(
                "flat dense"
            ).classes("shr-muted")
            ui.button(confirm_label, on_click=lambda: dialog.submit(True)).props(
                "unelevated dense"
            ).style(f"background: {color}; color: white;")

    result = await dialog
    dialog.delete()
    return bool(result)


def copied(what: str = "Copied") -> None:
    ui.notify(
        what,
        type="positive",
        icon="content_copy",
        position="bottom",
        timeout=1500,
    )


def copy_to_clipboard(text: str, *, label: str = "Copied to clipboard") -> None:
    ui.clipboard.write(text)
    copied(label)