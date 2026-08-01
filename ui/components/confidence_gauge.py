from __future__ import annotations

import math
from typing import Optional

from nicegui import ui

from app.constants import COLOR_NEUTRAL, score_color, score_label
from ui import theme
from utils.formatters import format_percent, format_score


_ARC_RADIUS = 42.0
_ARC_CIRCUMFERENCE = 2 * math.pi * _ARC_RADIUS


def _dash_offset(score: float, sweep: float = 1.0) -> float:
    visible = _ARC_CIRCUMFERENCE * sweep
    return visible - (visible * max(0.0, min(1.0, score)))


def gauge(
    score: Optional[float],
    *,
    size: int = 108,
    label: str = "Confidence",
    caption: Optional[str] = None,
    show_label: bool = True,
) -> ui.element:
    has_value = score is not None
    value = max(0.0, min(1.0, score)) if has_value else 0.0
    color = score_color(value) if has_value else COLOR_NEUTRAL

    track_width = 8
    offset = _dash_offset(value, sweep=0.75)
    visible_length = _ARC_CIRCUMFERENCE * 0.75

    svg = f"""
    <svg viewBox="0 0 100 100" style="width:{size}px;height:{size}px;transform:rotate(135deg);">
        <circle
            cx="50" cy="50" r="{_ARC_RADIUS}"
            fill="none"
            stroke="var(--shr-surface-alt)"
            stroke-width="{track_width}"
            stroke-linecap="round"
            stroke-dasharray="{visible_length} {_ARC_CIRCUMFERENCE}"
        />
        <circle
            cx="50" cy="50" r="{_ARC_RADIUS}"
            fill="none"
            stroke="{color}"
            stroke-width="{track_width}"
            stroke-linecap="round"
            stroke-dasharray="{visible_length} {_ARC_CIRCUMFERENCE}"
            stroke-dashoffset="{offset}"
            style="transition: stroke-dashoffset 600ms cubic-bezier(0.4,0,0.2,1);"
        />
    </svg>
    """

    with ui.column().classes("items-center gap-1 no-wrap") as container:
        with ui.element("div").classes("relative flex items-center justify-center").style(
            f"width:{size}px;height:{size}px;"
        ):
            ui.html(svg)

            with ui.column().classes(
                "absolute inset-0 items-center justify-center gap-0 no-wrap"
            ):
                ui.label(format_percent(score) if has_value else "—").classes(
                    "font-semibold leading-none"
                ).style(f"color: {color}; font-size: {max(16, size // 5)}px;")

                if has_value:
                    ui.label(score_label(value)).classes("leading-none mt-1").style(
                        f"color: {color}; font-size: {max(9, size // 11)}px; "
                        "font-weight: 600; opacity: 0.85;"
                    )

        if show_label:
            ui.label(label).classes("text-xs shr-muted text-center leading-tight")

        if caption:
            ui.label(caption).classes("text-xs shr-muted text-center leading-tight").style(
                "opacity: 0.75;"
            )

    return container


def mini_gauge(score: Optional[float], *, size: int = 44) -> ui.element:
    has_value = score is not None
    value = max(0.0, min(1.0, score)) if has_value else 0.0
    color = score_color(value) if has_value else COLOR_NEUTRAL

    offset = _dash_offset(value)

    svg = f"""
    <svg viewBox="0 0 100 100" style="width:{size}px;height:{size}px;transform:rotate(-90deg);">
        <circle cx="50" cy="50" r="{_ARC_RADIUS}"
            fill="none" stroke="var(--shr-surface-alt)" stroke-width="10" />
        <circle cx="50" cy="50" r="{_ARC_RADIUS}"
            fill="none" stroke="{color}" stroke-width="10" stroke-linecap="round"
            stroke-dasharray="{_ARC_CIRCUMFERENCE}"
            stroke-dashoffset="{offset}"
            style="transition: stroke-dashoffset 500ms cubic-bezier(0.4,0,0.2,1);" />
    </svg>
    """

    with ui.element("div").classes("relative flex items-center justify-center").style(
        f"width:{size}px;height:{size}px;flex-shrink:0;"
    ) as container:
        ui.html(svg)
        ui.label(f"{int(value * 100)}" if has_value else "—").classes(
            "absolute font-semibold leading-none"
        ).style(f"color: {color}; font-size: {max(10, size // 4)}px;")

    return container


def score_bar(
    score: Optional[float],
    *,
    label: str,
    caption: Optional[str] = None,
    show_value: bool = True,
    height: int = 6,
    color_override: Optional[str] = None,
) -> ui.element:
    has_value = score is not None
    value = max(0.0, min(1.0, score)) if has_value else 0.0
    color = color_override or (score_color(value) if has_value else COLOR_NEUTRAL)

    with ui.column().classes("w-full gap-1 no-wrap") as container:
        with ui.row().classes("w-full items-baseline justify-between gap-2 no-wrap"):
            ui.label(label).classes("text-xs shr-muted")
            if show_value:
                ui.label(format_score(score)).classes("shr-mono text-xs font-semibold").style(
                    f"color: {color}"
                )

        with ui.element("div").classes("w-full").style(
            f"height:{height}px;border-radius:{height}px;"
            "background: var(--shr-surface-alt);overflow:hidden;"
        ):
            ui.element("div").style(
                f"width:{value * 100:.1f}%;height:100%;background:{color};"
                f"border-radius:{height}px;"
                "transition: width 600ms cubic-bezier(0.4,0,0.2,1);"
            )

        if caption:
            ui.label(caption).classes("text-xs shr-muted leading-tight").style(
                "opacity: 0.75;"
            )

    return container


def confidence_breakdown(
    *,
    overall: float,
    retrieval: float,
    grounding: float,
    gauge_size: int = 116,
) -> ui.element:
    with ui.row().classes("w-full items-center gap-5 no-wrap") as container:
        gauge(overall, size=gauge_size, label="Overall confidence")

        with ui.column().classes("flex-grow gap-3 min-w-0"):
            score_bar(
                retrieval,
                label="Retrieval",
                caption="Average similarity of the evidence that was retrieved",
            )
            score_bar(
                grounding,
                label="Grounding",
                caption="Judge confidence that the answer is supported by that evidence",
            )

    return container


def stat_tile(
    value: str,
    label: str,
    *,
    icon: Optional[str] = None,
    color: Optional[str] = None,
    caption: Optional[str] = None,
) -> ui.element:
    tone = color or theme.PRIMARY

    with ui.column().classes("gap-1 p-3 flex-grow min-w-0 shr-surface-alt") as container:
        with ui.row().classes("items-center gap-2 no-wrap"):
            if icon:
                ui.icon(icon, size="15px").style(f"color: {tone}")
            ui.label(label).classes("text-xs shr-muted ellipsis")

        ui.label(value).classes("text-lg font-semibold leading-tight").style(
            f"color: {tone}"
        )

        if caption:
            ui.label(caption).classes("text-xs shr-muted leading-tight").style(
                "opacity: 0.75;"
            )

    return container