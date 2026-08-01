from __future__ import annotations

import time
from typing import Callable, Optional

from nicegui import ui

from app.config import settings
from ui import theme


_STAGE_LABELS: tuple[tuple[float, str], ...] = (
    (0.0, "Sending your question…"),
    (2.0, "Building conversation context…"),
    (5.0, "Searching the knowledge base…"),
    (11.0, "Generating the answer…"),
    (20.0, "Verifying grounding and checking for hallucinations…"),
    (34.0, "Scoring answer quality…"),
    (48.0, "Attempting self-healing recovery…"),
    (72.0, "Still working — the backend may be waking from idle…"),
)


def _stage_for(elapsed: float) -> str:
    label = _STAGE_LABELS[0][1]
    for threshold, text in _STAGE_LABELS:
        if elapsed >= threshold:
            label = text
        else:
            break
    return label


def shimmer_bar(width: str = "100%", height: str = "12px") -> ui.element:
    return (
        ui.element("div")
        .classes("shr-pulse")
        .style(
            f"width: {width}; height: {height}; border-radius: 6px; "
            "background: var(--shr-surface-alt); flex-shrink: 0;"
        )
    )


def text_skeleton(lines: int = 3) -> ui.element:
    widths = ("100%", "94%", "88%", "72%", "96%", "60%")

    with ui.column().classes("w-full gap-2") as container:
        for index in range(max(1, lines)):
            shimmer_bar(width=widths[index % len(widths)])

    return container


def card_skeleton(*, lines: int = 3, show_header: bool = True) -> ui.element:
    with ui.column().classes("w-full gap-3 p-4 shr-surface") as container:
        if show_header:
            with ui.row().classes("items-center gap-3 no-wrap w-full"):
                (
                    ui.element("div")
                    .classes("shr-pulse")
                    .style(
                        "width: 28px; height: 28px; border-radius: 8px; "
                        "background: var(--shr-surface-alt); flex-shrink: 0;"
                    )
                )
                shimmer_bar(width="40%", height="14px")
        text_skeleton(lines)

    return container


def metric_skeleton(count: int = 4) -> ui.element:
    with ui.row().classes("w-full gap-3 no-wrap") as container:
        for _ in range(max(1, count)):
            with ui.column().classes("gap-2 p-3 flex-grow shr-surface-alt"):
                shimmer_bar(width="55%", height="10px")
                shimmer_bar(width="80%", height="18px")

    return container


def list_skeleton(rows: int = 4) -> ui.element:
    with ui.column().classes("w-full gap-2") as container:
        for _ in range(max(1, rows)):
            with ui.row().classes("items-center gap-3 no-wrap w-full p-3 shr-surface-alt"):
                (
                    ui.element("div")
                    .classes("shr-pulse")
                    .style(
                        "width: 20px; height: 20px; border-radius: 5px; "
                        "background: var(--shr-surface); flex-shrink: 0;"
                    )
                )
                with ui.column().classes("gap-2 flex-grow"):
                    shimmer_bar(width="62%", height="11px")
                    shimmer_bar(width="38%", height="9px")

    return container


def typing_dots(*, color: str = theme.PRIMARY) -> ui.element:
    with ui.row().classes("items-center gap-1 no-wrap") as container:
        for delay in (0.0, 0.18, 0.36):
            (
                ui.element("div")
                .style(
                    f"width: 6px; height: 6px; border-radius: 50%; "
                    f"background: {color}; opacity: 0.85; "
                    f"animation: shrPulse 1.2s ease-in-out {delay}s infinite;"
                )
            )

    return container


class ThinkingIndicator:
    def __init__(
        self,
        *,
        on_cancel: Optional[Callable[[], None]] = None,
        show_stages: bool = True,
    ) -> None:
        self._started = time.perf_counter()
        self._on_cancel = on_cancel
        self._show_stages = show_stages
        self._stage_label: Optional[ui.label] = None
        self._timer_label: Optional[ui.label] = None
        self._timer: Optional[ui.timer] = None
        self._container: Optional[ui.element] = None
        self._cold_hint_shown = False
        self._cold_hint: Optional[ui.element] = None

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self._started

    def build(self) -> ui.element:
        with ui.column().classes(
            "w-full gap-2 p-4 shr-bubble-assistant shr-fade-in"
        ) as container:
            with ui.row().classes("items-center gap-3 no-wrap w-full"):
                typing_dots()

                self._stage_label = ui.label(_STAGE_LABELS[0][1]).classes(
                    "text-sm shr-muted"
                )

                ui.space()

                self._timer_label = ui.label("0.0s").classes(
                    "shr-mono text-xs shr-muted"
                )

                if self._on_cancel is not None:
                    ui.button(icon="stop_circle", on_click=self._handle_cancel).props(
                        "flat dense round size=sm"
                    ).classes("shr-muted").tooltip("Cancel request")

            if self._show_stages:
                text_skeleton(2)

        self._container = container
        self._timer = ui.timer(0.1, self._tick)
        return container

    def _tick(self) -> None:
        elapsed = self.elapsed

        if self._timer_label is not None:
            self._timer_label.set_text(f"{elapsed:.1f}s")

        if self._stage_label is not None:
            self._stage_label.set_text(_stage_for(elapsed))

        if (
            not self._cold_hint_shown
            and settings.should_warm_up
            and elapsed >= 25.0
            and self._container is not None
        ):
            self._cold_hint_shown = True
            with self._container:
                with ui.row().classes("items-center gap-2 no-wrap").style(
                    f"color: {theme.WARNING};"
                ) as hint:
                    ui.icon("bedtime", size="14px")
                    ui.label(
                        f"First request after idle can take up to "
                        f"{settings.cold_start_estimate}s."
                    ).classes("text-xs")
                self._cold_hint = hint

    def _handle_cancel(self) -> None:
        if self._on_cancel is not None:
            self._on_cancel()
        self.stop()

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.deactivate()
            self._timer = None

    def dismiss(self) -> None:
        self.stop()
        if self._container is not None:
            self._container.delete()
            self._container = None


class ProgressPanel:
    def __init__(self, title: str, *, icon: str = "hourglass_top") -> None:
        self._title = title
        self._icon = icon
        self._started = time.perf_counter()
        self._label: Optional[ui.label] = None
        self._timer_label: Optional[ui.label] = None
        self._timer: Optional[ui.timer] = None
        self._container: Optional[ui.element] = None

    def build(self) -> ui.element:
        with ui.column().classes("w-full gap-3 p-4 shr-surface shr-fade-in") as container:
            with ui.row().classes("items-center gap-3 no-wrap w-full"):
                ui.spinner(size="sm").style(f"color: {theme.PRIMARY}")

                with ui.column().classes("gap-0 flex-grow"):
                    ui.label(self._title).classes("text-sm font-medium")
                    self._label = ui.label("Starting…").classes("text-xs shr-muted")

                self._timer_label = ui.label("0.0s").classes("shr-mono text-xs shr-muted")

            ui.linear_progress(value=None, size="3px").props("indeterminate").style(
                f"color: {theme.PRIMARY}"
            )

        self._container = container
        self._timer = ui.timer(0.1, self._tick)
        return container

    def _tick(self) -> None:
        if self._timer_label is not None:
            self._timer_label.set_text(f"{time.perf_counter() - self._started:.1f}s")

    def set_status(self, text: str) -> None:
        if self._label is not None:
            self._label.set_text(text)

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.deactivate()
            self._timer = None

    def dismiss(self) -> None:
        self.stop()
        if self._container is not None:
            self._container.delete()
            self._container = None