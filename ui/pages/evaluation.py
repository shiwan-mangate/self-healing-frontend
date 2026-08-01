from __future__ import annotations

import logging
from typing import Optional

from nicegui import ui

from api.client import api_client
from api.errors import ApiError, ErrorCode
from api.models import EvaluationResponse
from app.constants import Route, score_color, status_meta
from app.state import QueryRecord
from services import chat_service
from ui import layout, theme
from ui.components.confidence_gauge import confidence_breakdown, score_bar
from ui.components.metrics_row import grounding_pill, risk_pill
from ui.components.notify import confirm, copy_to_clipboard, error_card, info
from ui.components.ragas_card import ragas_card
from ui.components.skeleton import card_skeleton, metric_skeleton
from utils.formatters import format_percent, format_relative, truncate

logger = logging.getLogger(__name__)


class EvaluationPage:
    def __init__(self, query_id: str = "") -> None:
        self.query_id = query_id.strip()
        self.input: Optional[ui.input] = None
        self.results_slot: Optional[ui.element] = None
        self.recent_slot: Optional[ui.element] = None
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

            self.recent_slot = ui.column().classes("w-full gap-0 shr-fill")
            self._render_recent()

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

    def _render_recent(self) -> None:
        if self.recent_slot is None:
            return

        self.recent_slot.clear()
        records = chat_service.recent_queries()

        if not records:
            return

        with self.recent_slot:
            with ui.column().classes("w-full gap-2 p-4 shr-surface shr-fill"):
                with ui.row().classes("w-full items-center gap-2 no-wrap shr-fill"):
                    ui.icon("history", size="18px").style(
                        f"color: {theme.PRIMARY}; flex-shrink: 0;"
                    )
                    ui.label("Recent questions").classes("text-sm font-semibold")
                    ui.space()
                    ui.label(f"{len(records)} recorded").classes(
                        "text-xs shr-muted"
                    ).style("white-space: nowrap; flex-shrink: 0;")
                    ui.button(
                        icon="delete_sweep", on_click=self._handle_clear_recent
                    ).props("flat dense round size=sm").classes("shr-muted").style(
                        "flex-shrink: 0;"
                    ).tooltip("Clear this list")

                ui.label(
                    "Questions asked from this browser. Click one to load its metrics."
                ).classes("text-xs shr-muted")

                with ui.column().classes("w-full gap-1.5 pt-1 shr-fill"):
                    for record in records:
                        self._recent_row(record)

    def _recent_row(self, record: QueryRecord) -> None:
        meta = status_meta(record.status)
        active = record.query_id == self.query_id
        tone = score_color(record.confidence)

        background = f"{theme.PRIMARY}14" if active else "transparent"
        border = (
            f"1px solid {theme.PRIMARY}44"
            if active
            else "1px solid var(--shr-border)"
        )

        row = (
            ui.row()
            .classes(
                "w-full items-center gap-3 no-wrap px-3 py-2 shr-clickable shr-fill"
            )
            .style(
                f"background: {background}; border: {border}; border-radius: 8px;"
            )
        )

        with row:
            ui.icon(meta.icon, size="16px").style(
                f"color: {meta.color}; flex-shrink: 0;"
            ).tooltip(meta.label)

            with ui.column().classes("gap-0 shr-flex-min").style(
                "flex: 1 1 auto; min-width: 0;"
            ):
                ui.label(truncate(record.question, 72) or record.query_id).classes(
                    "text-sm"
                ).style(
                    "overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"
                ).tooltip(record.question or record.query_id)

                with ui.row().classes("items-center gap-2 no-wrap"):
                    ui.label(record.query_id).classes(
                        "shr-mono text-xs shr-muted"
                    ).style("opacity: 0.65; white-space: nowrap;")
                    ui.label("·").classes("text-xs shr-muted").style("opacity: 0.4;")
                    ui.label(format_relative(record.asked_dt)).classes(
                        "text-xs shr-muted"
                    ).style("opacity: 0.7; white-space: nowrap;")

            if record.recovery_used or record.retry_count:
                ui.icon("healing", size="14px").style(
                    f"color: {theme.SECONDARY}; flex-shrink: 0;"
                ).tooltip("Self-healing was engaged for this answer")

            ui.label(format_percent(record.confidence)).classes(
                "shr-mono text-xs font-semibold"
            ).style(f"color: {tone}; flex-shrink: 0; white-space: nowrap;")

        row.on("click", lambda qid=record.query_id: self._select_recent(qid))

    async def _select_recent(self, query_id: str) -> None:
        if self.loading:
            return
        self.query_id = query_id
        if self.input is not None:
            self.input.set_value(query_id)
        self._render_recent()
        await self._load()

    async def _handle_clear_recent(self) -> None:
        records = chat_service.recent_queries()
        if not records:
            return

        approved = await confirm(
            f"Clear all {len(records)} recorded questions from this browser? "
            "The evaluations remain on the server.",
            title="Clear recent questions",
            confirm_label="Clear",
            danger=True,
        )
        if not approved:
            return

        chat_service.clear_query_log()
        self._render_recent()
        info("Recent questions cleared")

    def _render_placeholder(self) -> None:
        if self.results_slot is None:
            return

        self.results_slot.clear()
        has_recent = bool(chat_service.recent_queries())

        with self.results_slot:
            with ui.column().classes("w-full shr-surface shr-fill"):
                layout.empty_state(
                    "fact_check",
                    "No evaluation loaded",
                    (
                        "Pick a question above, or paste a query ID."
                        if has_recent
                        else "Ask a question in the chat first, then open its "
                        "evaluation from the icon under the answer."
                    ),
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
            self._render_recent()
            self._render_placeholder()
            return

        self.query_id = candidate
        self._render_recent()
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
            self._render_context()
            self._render_verdict(evaluation)
            self._render_confidence(evaluation)
            ragas_card(evaluation.ragas)
            self._render_trace()

    def _render_context(self) -> None:
        record = chat_service.find_query(self.query_id)
        if record is None or not record.question:
            return

        with ui.row().classes(
            "w-full items-start gap-2 no-wrap px-4 py-3 shr-surface-alt shr-fill"
        ):
            ui.icon("help_outline", size="16px").classes("shr-muted").style(
                "flex-shrink: 0; margin-top: 2px;"
            )
            with ui.column().classes("gap-0 shr-flex-min").style(
                "flex: 1 1 auto; min-width: 0;"
            ):
                ui.label("Question").classes("text-xs shr-muted")
                ui.label(record.question).classes("text-sm leading-snug")

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