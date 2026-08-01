from __future__ import annotations

from typing import Optional

from nicegui import ui

from api.models import ChatResponse, EvaluationResponse
from app.constants import (
    COLOR_NEUTRAL,
    risk_meta,
    score_color,
    status_meta,
)
from ui import theme
from ui.components.confidence_gauge import mini_gauge
from ui.components.healing_timeline import recovery_badge
from utils.formatters import format_latency, format_percent


def status_pill(status: str, *, dense: bool = False) -> ui.element:
    meta = status_meta(status)
    padding = "px-1.5 py-0.5" if dense else "px-2 py-1"

    with ui.row().classes(f"items-center gap-1 no-wrap {padding}").style(
        f"background: {meta.color}1a; border: 1px solid {meta.color}38; "
        "border-radius: 999px;"
    ) as pill:
        ui.icon(meta.icon, size="13px").style(f"color: {meta.color}")
        ui.label(meta.label).classes("text-xs font-semibold").style(
            f"color: {meta.color}"
        )

    return pill


def risk_pill(risk: str, *, detected: bool = False) -> ui.element:
    meta = risk_meta(risk)
    label = "Hallucination detected" if detected else meta.label

    with ui.row().classes("items-center gap-1 no-wrap px-2 py-1").style(
        f"background: {meta.color}1a; border: 1px solid {meta.color}38; "
        "border-radius: 999px;"
    ).tooltip(
        "The judge found fabricated claims not supported by the retrieved evidence."
        if detected
        else "Categorical hallucination risk assigned by the evaluation judge."
    ) as pill:
        ui.icon(meta.icon, size="13px").style(f"color: {meta.color}")
        ui.label(label).classes("text-xs font-semibold").style(f"color: {meta.color}")

    return pill


def grounding_pill(is_grounded: bool) -> ui.element:
    color = theme.POSITIVE if is_grounded else theme.NEGATIVE
    icon = "verified" if is_grounded else "gpp_bad"
    label = "Grounded" if is_grounded else "Not grounded"

    with ui.row().classes("items-center gap-1 no-wrap px-2 py-1").style(
        f"background: {color}1a; border: 1px solid {color}38; border-radius: 999px;"
    ).tooltip(
        "Every factual claim in the answer is supported by the retrieved evidence."
        if is_grounded
        else "At least one factual claim was not supported by the retrieved evidence."
    ) as pill:
        ui.icon(icon, size="13px").style(f"color: {color}")
        ui.label(label).classes("text-xs font-semibold").style(f"color: {color}")

    return pill


def metric_chip(
    icon: str,
    value: str,
    *,
    label: Optional[str] = None,
    color: Optional[str] = None,
    tooltip: Optional[str] = None,
) -> ui.element:
    tone = color or COLOR_NEUTRAL

    chip = ui.row().classes("items-center gap-1 no-wrap")
    with chip:
        ui.icon(icon, size="14px").style(f"color: {tone}; opacity: 0.85;")
        ui.label(value).classes("shr-mono text-xs font-semibold").style(f"color: {tone}")
        if label:
            ui.label(label).classes("text-xs shr-muted")

    if tooltip:
        chip.tooltip(tooltip)

    return chip


def _divider() -> None:
    ui.element("div").style(
        "width: 1px; height: 14px; background: var(--shr-border); flex-shrink: 0;"
    )


def metrics_row(
    response: ChatResponse,
    evaluation: Optional[EvaluationResponse] = None,
    *,
    show_gauge: bool = True,
) -> ui.element:
    confidence = (
        evaluation.confidence.score if evaluation is not None else response.confidence
    )
    has_confidence = evaluation is not None or response.confidence > 0.0

    with ui.row().classes(
        "w-full items-center gap-3 no-wrap flex-wrap px-3 py-2"
    ).style(
        "background: var(--shr-surface-alt); border-radius: 8px;"
    ) as row:
        if show_gauge and has_confidence:
            mini_gauge(confidence, size=38)

        status_pill(response.status)

        if evaluation is not None:
            grounding_pill(evaluation.grounding.is_grounded)

            if evaluation.hallucination.detected:
                risk_pill(evaluation.hallucination.risk, detected=True)
            elif evaluation.hallucination.risk in {"medium", "high"}:
                risk_pill(evaluation.hallucination.risk)

        healing = recovery_badge(
            recovery_used=response.recovery_used,
            retry_count=response.retry_count,
            step_count=len(response.correction_path),
        )

        ui.space()

        if not show_gauge and has_confidence:
            metric_chip(
                "speed",
                format_percent(confidence),
                label="confidence",
                color=score_color(confidence),
                tooltip="Aggregated confidence across retrieval, grounding and hallucination signals.",
            )
            _divider()

        metric_chip(
            "schedule",
            format_latency(response.latency_ms),
            color=COLOR_NEUTRAL,
            tooltip="Total workflow latency reported by the backend.",
        )

        if response.has_citations:
            _divider()
            metric_chip(
                "format_quote",
                str(len(response.citations)),
                label="cited",
                color=COLOR_NEUTRAL,
                tooltip=f"{len(response.citations)} evidence chunks referenced in this answer.",
            )

        if evaluation is not None and evaluation.retry_recommended:
            _divider()
            metric_chip(
                "replay",
                "retry advised",
                color=theme.WARNING,
                tooltip="The evaluator recommended a corrective action for this answer.",
            )

    return row


def evaluation_summary_row(evaluation: EvaluationResponse) -> ui.element:
    with ui.row().classes("w-full items-center gap-2 no-wrap flex-wrap") as row:
        grounding_pill(evaluation.grounding.is_grounded)
        risk_pill(
            evaluation.hallucination.risk,
            detected=evaluation.hallucination.detected,
        )

        metric_chip(
            "speed",
            format_percent(evaluation.confidence.score),
            label="overall",
            color=score_color(evaluation.confidence.score),
        )

        if evaluation.retry_recommended:
            metric_chip(
                "replay",
                "retry advised",
                color=theme.WARNING,
                tooltip="The evaluator recommended a corrective action.",
            )

    return row


def stat_grid(response: ChatResponse, evaluation: Optional[EvaluationResponse]) -> ui.element:
    confidence = (
        evaluation.confidence.score if evaluation is not None else response.confidence
    )

    entries: list[tuple[str, str, str, str, str]] = [
        (
            "speed",
            format_percent(confidence),
            "Confidence",
            score_color(confidence),
            "Aggregated system trust in this answer",
        ),
        (
            "schedule",
            format_latency(response.latency_ms),
            "Latency",
            COLOR_NEUTRAL,
            "End-to-end workflow duration",
        ),
        (
            "replay",
            str(response.retry_count),
            "Retries",
            theme.SECONDARY if response.retry_count else COLOR_NEUTRAL,
            "Recovery attempts executed",
        ),
        (
            "format_quote",
            str(len(response.citations)),
            "Citations",
            COLOR_NEUTRAL,
            "Evidence chunks referenced",
        ),
    ]

    with ui.grid(columns=4).classes("w-full gap-2") as grid:
        for icon, value, label, color, tooltip in entries:
            with ui.column().classes("gap-0.5 p-3 shr-surface-alt").tooltip(tooltip):
                with ui.row().classes("items-center gap-1.5 no-wrap"):
                    ui.icon(icon, size="14px").style(f"color: {color}; opacity: 0.8;")
                    ui.label(label).classes("text-xs shr-muted")
                ui.label(value).classes("text-base font-semibold leading-tight").style(
                    f"color: {color}"
                )

    return grid


def trace_row(query_id: str, session_id: Optional[str] = None) -> ui.element:
    with ui.row().classes("items-center gap-3 no-wrap flex-wrap") as row:
        with ui.row().classes("items-center gap-1 no-wrap").tooltip(
            "Trace identifier for this workflow execution"
        ):
            ui.icon("tag", size="12px").classes("shr-muted").style("opacity: 0.7;")
            ui.label(query_id).classes("shr-mono text-xs shr-muted").style(
                "opacity: 0.75;"
            )

        if session_id:
            with ui.row().classes("items-center gap-1 no-wrap").tooltip(
                "Conversation session identifier"
            ):
                ui.icon("forum", size="12px").classes("shr-muted").style("opacity: 0.7;")
                ui.label(session_id).classes("shr-mono text-xs shr-muted").style(
                    "opacity: 0.75;"
                )

    return row