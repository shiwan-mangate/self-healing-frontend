from __future__ import annotations

import logging
from typing import Optional

from nicegui import ui

from api.client import api_client
from api.errors import ApiError, ErrorCode
from api.models import EvaluationResponse
from app.constants import Route
from ui import layout, theme
from ui.components.confidence_gauge import confidence_breakdown, score_bar
from ui.components.metrics_row import grounding_pill, risk_pill
from ui.components.notify import copy_to_clipboard, error_card
from ui.components.ragas_card import ragas_card
from ui.components.skeleton import card_skeleton, metric_skeleton

logger = logging.getLogger(__name__)


class EvaluationPage:
    def __init__(self, query_id: str = "") -> None:
        self.query_id = query_id.strip()
        self.input: Optional[ui.input] = None
        self.results_slot: Optional[ui.element] = None
        self.loading = False

    def build(self) -> None:
        with layout.page_shell(Route.EVALUATION):
            layout.section_header(
                "Evaluation",
                "Look up the recorded quality metrics for any answer using its "
                "trace identifier.",
                icon="fact_check",
            )

            self._build_lookup()

            self.results_slot = ui.column().classes("w-full gap-4 shr-fill")

            if self.query_id:
                ui.timer(0.1, self._load, once=True)
            else:
                self._render_placeholder()

    def _build_lookup(self) -> None:
        with ui.column().classes("w-full gap-2 p-4 shr-surface shr-fill"):
            with ui.row().classes("w-full items-start gap-2 no-wrap shr-fill"):
                self.input = (
                    ui.input(
                        placeholder="Query ID, e.g. req-trace-5542",
                        value=self.query_id,
                    )
                    .props("dense outlined clearable input-class=font-mono")
                    .classes("shr-flex-min")
                    .style("flex: 1 1 auto; min-width: 0;")
                )
                self.input.on("keydown.enter", self._handle_lookup)

                ui.button("Look up", icon="search", on_click=self._handle_lookup).props(
                    "unelevated no-caps dense"
                ).style(
                    f"background: {theme.PRIMARY}; color: white; "
                    "border-radius: 8px; height: 40px; flex-shrink: 0;"
                )

            ui.label(
                "Every answer in the chat carries a query ID. Open the evaluation "
                "icon under an answer to jump straight here."
            ).classes("text-xs shr-muted leading-snug")

    def _render_placeholder(self) -> None:
        if self.results_slot is None:
            return

        self.results_slot.clear()
        with self.results_slot:
            with ui.column().classes("w-full shr-surface shr-fill"):
                layout.empty_state(
                    "fact_check",
                    "No evaluation loaded",
                    "Enter a query ID above, or open an answer's evaluation from "
                    "the chat page.",
                )

    def _render_loading(self) -> None:
        if self.results_slot is None:
            return

        self.results_slot.clear()
        with self.results_slot:
            metric_skeleton(3)
            card_skeleton(lines=4)

    async def _handle_lookup(self) -> None:
        if self.input is None or self.loading:
            return

        candidate = (self.input.value or "").strip()
        if not candidate:
            self.query_id = ""
            self._render_placeholder()
            return

        self.query_id = candidate
        await self._load()

    async def _load(self) -> None:
        if not self.query_id or self.results_slot is None:
            return

        self.loading = True
        self._render_loading()

        try:
            evaluation = await api_client.get_evaluation(self.query_id)
        except ApiError as exc:
            self._render_error(exc)
            return
        except Exception:
            logger.exception("Unexpected evaluation lookup failure")
            self._render_error(ApiError.client_side(ErrorCode.UNEXPECTED))
            return
        finally:
            self.loading = False

        self._render_evaluation(evaluation)

    def _render_error(self, exc: ApiError) -> None:
        if self.results_slot is None:
            return

        self.results_slot.clear()
        with self.results_slot:
            error_card(exc, on_retry=self._load)

            if exc.is_not_found:
                with ui.column().classes(
                    "w-full gap-1.5 p-4 shr-surface-alt shr-fill"
                ):
                    ui.label("Why might this be missing?").classes(
                        "text-sm font-semibold"
                    )
                    for reason in (
                        "The query ID may be mistyped — they are case-sensitive.",
                        "The workflow may have failed before metrics were recorded.",
                        "The evaluation judge may have been unreachable at the time.",
                    ):
                        with ui.row().classes("items-start gap-2 no-wrap shr-fill"):
                            ui.label("•").classes("text-xs shr-muted").style(
                                "flex-shrink: 0;"
                            )
                            ui.label(reason).classes(
                                "text-xs shr-muted leading-snug shr-flex-min"
                            ).style("flex: 1 1 auto; min-width: 0;")

    def _render_evaluation(self, evaluation: EvaluationResponse) -> None:
        if self.results_slot is None:
            return

        self.results_slot.clear()

        with self.results_slot:
            self._render_verdict(evaluation)
            self._render_confidence(evaluation)
            ragas_card(evaluation.ragas)
            self._render_trace()

    def _render_verdict(self, evaluation: EvaluationResponse) -> None:
        passed = evaluation.passed
        color = theme.POSITIVE if passed else theme.NEGATIVE
        icon = "verified" if passed else "gpp_bad"

        headline = (
            "This answer passed verification"
            if passed
            else "This answer failed verification"
        )

        detail = (
            "Every factual claim was supported by the retrieved evidence, and no "
            "fabricated content was detected."
            if passed
            else _failure_detail(evaluation)
        )

        with ui.column().classes("w-full gap-3 p-4 shr-fill").style(
            f"background: {color}0d; border: 1px solid {color}2b; border-radius: 12px;"
        ):
            with ui.row().classes("w-full items-start gap-3 no-wrap shr-fill"):
                ui.icon(icon, size="24px").style(f"color: {color}; flex-shrink: 0;")

                with ui.column().classes("gap-0.5 shr-flex-min").style(
                    "flex: 1 1 auto; min-width: 0;"
                ):
                    ui.label(headline).classes("text-base font-semibold").style(
                        f"color: {color}"
                    )
                    ui.label(detail).classes("text-sm shr-muted leading-snug")

            with ui.row().classes("items-center gap-2 flex-wrap shr-fill"):
                grounding_pill(evaluation.grounding.is_grounded)
                risk_pill(
                    evaluation.hallucination.risk,
                    detected=evaluation.hallucination.detected,
                )

                if evaluation.retry_recommended:
                    with ui.row().classes(
                        "items-center gap-1 no-wrap px-2 py-1"
                    ).style(
                        f"background: {theme.WARNING}1a; "
                        f"border: 1px solid {theme.WARNING}38; border-radius: 999px;"
                    ).tooltip(
                        "The evaluator recommended a corrective action for this answer."
                    ):
                        ui.icon("replay", size="13px").style(
                            f"color: {theme.WARNING}"
                        )
                        ui.label("Retry recommended").classes(
                            "text-xs font-semibold"
                        ).style(f"color: {theme.WARNING}; white-space: nowrap;")

    def _render_confidence(self, evaluation: EvaluationResponse) -> None:
        confidence = evaluation.confidence

        with ui.column().classes("w-full gap-4 p-4 shr-surface shr-fill"):
            with ui.row().classes("w-full items-center gap-2 no-wrap shr-fill"):
                ui.icon("speed", size="18px").style(
                    f"color: {theme.PRIMARY}; flex-shrink: 0;"
                )
                ui.label("Confidence breakdown").classes("text-sm font-semibold")
                ui.space()
                ui.icon("help_outline", size="15px").classes("shr-muted").style(
                    "flex-shrink: 0;"
                ).tooltip(
                    "Overall confidence is a weighted blend of retrieval and "
                    "grounding scores, penalised when hallucination risk is elevated."
                )

            confidence_breakdown(
                overall=confidence.score,
                retrieval=confidence.retrieval_confidence,
                grounding=confidence.grounding_confidence,
            )

            ui.element("div").classes("w-full").style(
                "height: 1px; background: var(--shr-border);"
            )

            with ui.element("div").classes(
                "w-full grid grid-cols-1 md:grid-cols-2 gap-4 items-start shr-fill"
            ):
                with ui.column().classes("gap-1 shr-fill"):
                    ui.label("Grounding judge").classes("text-xs shr-muted")
                    score_bar(
                        evaluation.grounding.confidence,
                        label="Judge confidence in its verdict",
                        show_value=True,
                    )

                with ui.column().classes("gap-1 shr-fill"):
                    ui.label("Hallucination risk").classes("text-xs shr-muted")
                    with ui.row().classes("items-center gap-2 flex-wrap pt-1"):
                        risk_pill(
                            confidence.hallucination_risk,
                            detected=evaluation.hallucination.detected,
                        )

    def _render_trace(self) -> None:
        with ui.row().classes(
            "w-full items-center gap-2 flex-wrap px-1 shr-fill"
        ):
            ui.icon("tag", size="13px").classes("shr-muted").style(
                "opacity: 0.7; flex-shrink: 0;"
            )
            ui.label(self.query_id).classes("shr-mono text-xs shr-muted").style(
                "opacity: 0.75;"
            )
            ui.button(
                icon="content_copy",
                on_click=lambda: copy_to_clipboard(
                    self.query_id, label="Query ID copied"
                ),
            ).props("flat dense round size=sm").classes("shr-muted").style(
                "flex-shrink: 0;"
            )
            ui.space()
            ui.button(
                "Back to chat",
                icon="arrow_back",
                on_click=lambda: ui.navigate.to(Route.CHAT),
            ).props("flat dense no-caps size=sm").classes("shr-muted").style(
                "flex-shrink: 0;"
            )


def _failure_detail(evaluation: EvaluationResponse) -> str:
    if evaluation.hallucination.detected:
        return (
            "The judge found claims in the answer that were not supported by, or "
            "contradicted, the retrieved evidence."
        )

    if not evaluation.grounding.is_grounded:
        return (
            "At least one factual claim in the answer could not be traced back to "
            "the retrieved evidence."
        )

    return (
        "Confidence fell below the acceptance threshold despite the answer being "
        "grounded."
    )


@ui.page(Route.EVALUATION)
def evaluation_page(query_id: str = "") -> None:
    page = EvaluationPage(query_id)
    page.build()