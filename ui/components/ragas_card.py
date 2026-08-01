from __future__ import annotations

from typing import Optional

from nicegui import ui

from api.models import RagasResult
from app.constants import (
    BENCHMARK_ONLY_NOTE,
    COLOR_NEUTRAL,
    RAGAS_METRICS,
    RagasMetricMeta,
    score_color,
)
from ui import theme
from ui.components.confidence_gauge import score_bar
from utils.formatters import format_percent, format_score


_LIVE_BADGE_COLOR = theme.POSITIVE
_BENCHMARK_BADGE_COLOR = COLOR_NEUTRAL


def _badge(text: str, color: str, *, tooltip: Optional[str] = None) -> ui.element:
    element = (
        ui.row()
        .classes("items-center gap-1 no-wrap px-1.5 py-0.5")
        .style(
            f"background: {color}1a; border: 1px solid {color}30; border-radius: 4px;"
        )
    )
    with element:
        ui.label(text).classes("font-semibold").style(
            f"color: {color}; font-size: 9px; letter-spacing: 0.03em;"
        )

    if tooltip:
        element.tooltip(tooltip)

    return element


def metric_row(
    meta: RagasMetricMeta,
    value: Optional[float],
    *,
    show_badge: bool = True,
) -> ui.element:
    available = value is not None
    tone = score_color(value) if available else COLOR_NEUTRAL

    with ui.column().classes("w-full gap-1.5 p-3 shr-surface-alt") as container:
        with ui.row().classes("w-full items-center gap-2 no-wrap"):
            ui.icon(meta.icon, size="16px").style(
                f"color: {tone}; opacity: {'1' if available else '0.5'};"
            )

            ui.label(meta.label).classes("text-sm font-medium").style(
                "" if available else "opacity: 0.7;"
            )

            if show_badge:
                if meta.live:
                    _badge("LIVE", _LIVE_BADGE_COLOR, tooltip="Computed on every query")
                else:
                    _badge(
                        "BENCHMARK",
                        _BENCHMARK_BADGE_COLOR,
                        tooltip="Requires a ground-truth dataset",
                    )

            ui.space()

            ui.label(format_score(value)).classes(
                "shr-mono text-sm font-semibold"
            ).style(f"color: {tone}")

        with ui.element("div").classes("w-full").style(
            "height: 5px; border-radius: 3px; background: var(--shr-surface); "
            "overflow: hidden;"
        ):
            width = (max(0.0, min(1.0, value)) * 100) if available else 0.0
            ui.element("div").style(
                f"width: {width:.1f}%; height: 100%; background: {tone}; "
                "border-radius: 3px; "
                "transition: width 600ms cubic-bezier(0.4,0,0.2,1);"
            )

        ui.label(meta.description if available else BENCHMARK_ONLY_NOTE).classes(
            "text-xs shr-muted leading-snug"
        ).style("opacity: 0.8;" if available else "opacity: 0.65; font-style: italic;")

    return container


def ragas_grid(ragas: RagasResult, *, include_benchmark: bool = True) -> ui.element:
    metrics = [
        meta for meta in RAGAS_METRICS if include_benchmark or meta.live
    ]

    with ui.grid(columns=2).classes("w-full gap-3") as grid:
        for meta in metrics:
            metric_row(meta, ragas.get(meta.key))

    return grid


def ragas_card(
    ragas: Optional[RagasResult],
    *,
    title: str = "RAGAS quality metrics",
    include_benchmark: bool = True,
) -> ui.element:
    with ui.column().classes("w-full gap-3 p-4 shr-surface") as card:
        with ui.row().classes("w-full items-center gap-2 no-wrap"):
            ui.icon("insights", size="18px").style(f"color: {theme.PRIMARY}")
            ui.label(title).classes("text-sm font-semibold")
            ui.space()
            ui.icon("help_outline", size="15px").classes("shr-muted").tooltip(
                "RAGAS is a standard framework for evaluating retrieval-augmented "
                "generation. Live metrics run on every query; benchmark metrics "
                "require a labelled ground-truth dataset."
            )

        if ragas is None or not ragas.has_any:
            with ui.column().classes("w-full items-center gap-2 py-6"):
                ui.icon("query_stats", size="32px").classes("shr-muted").style(
                    "opacity: 0.45;"
                )
                ui.label("No RAGAS metrics were recorded for this query.").classes(
                    "text-sm shr-muted text-center"
                )
        else:
            ragas_grid(ragas, include_benchmark=include_benchmark)

            if include_benchmark and not any(
                ragas.get(meta.key) is not None
                for meta in RAGAS_METRICS
                if not meta.live
            ):
                with ui.row().classes("items-start gap-2 no-wrap px-3 py-2").style(
                    "background: var(--shr-surface-alt); border-radius: 8px;"
                ):
                    ui.icon("science", size="14px").classes("shr-muted").style(
                        "margin-top: 2px;"
                    )
                    ui.label(
                        "Context precision and recall are only computed in benchmark "
                        "mode, where each question has a known correct answer to "
                        "compare against."
                    ).classes("text-xs shr-muted leading-snug")

    return card


def ragas_compact(ragas: Optional[RagasResult]) -> Optional[ui.element]:
    if ragas is None or not ragas.has_any:
        return None

    with ui.column().classes("w-full gap-2") as container:
        for meta in RAGAS_METRICS:
            value = ragas.get(meta.key)
            if value is None:
                continue
            score_bar(
                value,
                label=meta.label,
                show_value=True,
                height=5,
            )

    return container


def ragas_chips(ragas: Optional[RagasResult]) -> Optional[ui.element]:
    if ragas is None or not ragas.has_any:
        return None

    with ui.row().classes("items-center gap-1.5 no-wrap flex-wrap") as container:
        for meta in RAGAS_METRICS:
            value = ragas.get(meta.key)
            if value is None:
                continue

            tone = score_color(value)
            short = meta.label.replace("Answer ", "").replace("Context ", "")

            with ui.row().classes("items-center gap-1 no-wrap px-2 py-1").style(
                f"background: {tone}1a; border: 1px solid {tone}30; border-radius: 999px;"
            ).tooltip(f"{meta.label}: {meta.description}"):
                ui.icon(meta.icon, size="12px").style(f"color: {tone}")
                ui.label(short).classes("text-xs").style(f"color: {tone}")
                ui.label(format_percent(value)).classes(
                    "shr-mono text-xs font-semibold"
                ).style(f"color: {tone}")

    return container


def ragas_expander(
    ragas: Optional[RagasResult],
    *,
    default_open: bool = False,
) -> Optional[ui.element]:
    if ragas is None or not ragas.has_any:
        return None

    live_count = sum(
        1 for meta in RAGAS_METRICS if meta.live and ragas.get(meta.key) is not None
    )

    with ui.expansion(
        f"RAGAS metrics · {live_count} computed",
        icon="insights",
        value=default_open,
    ).classes("w-full shr-surface-alt").props("dense expand-separator") as expander:
        with ui.column().classes("w-full gap-3 pt-2 pb-1"):
            ragas_grid(ragas, include_benchmark=True)

    return expander