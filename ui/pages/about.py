from __future__ import annotations

from typing import NamedTuple

from nicegui import ui

from app.config import settings
from app.constants import (
    APP_NAME,
    APP_TAGLINE,
    APP_VERSION,
    RECOVERY_ACTION_META,
    Endpoint,
    RecoveryAction,
    Route,
)
from ui import layout, theme


class Stage(NamedTuple):
    number: int
    title: str
    icon: str
    color: str
    summary: str
    detail: str


_PIPELINE: tuple[Stage, ...] = (
    Stage(
        1,
        "Memory",
        "history",
        "#4a9eff",
        "Loads the conversation so far",
        "Prior turns are retrieved and, once the history grows past its token "
        "budget, older messages are compressed into a rolling summary so context "
        "survives without exhausting the context window.",
    ),
    Stage(
        2,
        "Retrieval",
        "search",
        "#3fb9d4",
        "Finds relevant evidence",
        "The question is classified by intent, rewritten if it is vague or refers "
        "back to earlier turns, embedded, and matched against the vector store. "
        "Results are deduplicated, filtered by similarity, reranked and packed "
        "into a token budget.",
    ),
    Stage(
        3,
        "Generation",
        "auto_awesome",
        "#8b7cf6",
        "Writes a grounded answer",
        "A prompt is assembled from the retrieved evidence with strict grounding "
        "rules, the model answers using inline citation markers, and any marker "
        "that does not map to real evidence is stripped before the answer is "
        "returned.",
    ),
    Stage(
        4,
        "Evaluation",
        "fact_check",
        "#f0a848",
        "Verifies the answer",
        "An independent judge model checks whether every factual claim is "
        "supported by the evidence and whether anything was fabricated. RAGAS "
        "metrics are computed alongside, and the scores are combined into an "
        "overall confidence.",
    ),
    Stage(
        5,
        "Self-healing",
        "healing",
        "#22c9a8",
        "Repairs failures automatically",
        "When verification fails, a policy engine selects a corrective action "
        "based on the specific failure, the workflow loops, and the process "
        "repeats until the answer passes or the retry budget is exhausted.",
    ),
)


class AboutPage:
    def build(self) -> None:
        with layout.page_shell(Route.ABOUT, max_width="960px"):
            self._build_hero()
            self._build_pipeline()
            self._build_actions()
            self._build_signals()
            self._build_notes()

    def _build_hero(self) -> None:
        with ui.column().classes("w-full gap-3 p-5 shr-surface"):
            with ui.row().classes("items-center gap-3 no-wrap"):
                ui.icon("autorenew", size="34px").style(f"color: {theme.PRIMARY}")
                with ui.column().classes("gap-0"):
                    ui.label(APP_NAME).classes("text-xl font-semibold leading-tight")
                    ui.label(APP_TAGLINE).classes("text-sm shr-muted leading-tight")

            ui.label(
                "Most retrieval systems answer a question and stop. This one keeps "
                "going: every answer is independently verified, and when that "
                "verification fails the system diagnoses why and repairs itself "
                "before responding. Everything it did to get there is visible in "
                "the interface."
            ).classes("text-sm leading-relaxed")

            with ui.row().classes("items-center gap-2 no-wrap flex-wrap pt-1"):
                ui.button(
                    "Start asking",
                    icon="forum",
                    on_click=lambda: ui.navigate.to(Route.CHAT),
                ).props("unelevated no-caps dense").style(
                    f"background: {theme.PRIMARY}; color: white; border-radius: 8px;"
                )
                ui.button(
                    "Add documents",
                    icon="library_books",
                    on_click=lambda: ui.navigate.to(Route.DOCUMENTS),
                ).props("flat no-caps dense").style(f"color: {theme.PRIMARY}")

    def _build_pipeline(self) -> None:
        with ui.column().classes("w-full gap-3 p-5 shr-surface"):
            ui.label("How a question is answered").classes("text-base font-semibold")
            ui.label(
                "Five stages run in order. Stage five only engages when stage four "
                "is not satisfied."
            ).classes("text-sm shr-muted")

            with ui.column().classes("w-full gap-0 pt-2"):
                for stage in _PIPELINE:
                    self._stage_row(stage, is_last=stage.number == len(_PIPELINE))

    def _stage_row(self, stage: Stage, *, is_last: bool) -> None:
        with ui.row().classes("w-full items-start gap-3 no-wrap"):
            with ui.column().classes("items-center gap-0 no-wrap").style(
                "flex-shrink: 0;"
            ):
                with ui.element("div").classes(
                    "flex items-center justify-center"
                ).style(
                    f"width: 34px; height: 34px; border-radius: 10px; "
                    f"background: {stage.color}1f; border: 1px solid {stage.color}44;"
                ):
                    ui.icon(stage.icon, size="18px").style(f"color: {stage.color}")

                if not is_last:
                    ui.element("div").style(
                        f"width: 2px; height: 34px; margin-top: 4px; "
                        f"background: linear-gradient(to bottom, {stage.color}55, "
                        f"{stage.color}18); border-radius: 1px;"
                    )

            with ui.column().classes("gap-0.5 flex-grow min-w-0 pb-4"):
                with ui.row().classes("items-baseline gap-2 no-wrap"):
                    ui.label(stage.title).classes("text-sm font-semibold").style(
                        f"color: {stage.color}"
                    )
                    ui.label(stage.summary).classes("text-xs shr-muted")

                ui.label(stage.detail).classes("text-sm leading-relaxed shr-muted")

    def _build_actions(self) -> None:
        with ui.column().classes("w-full gap-3 p-5 shr-surface"):
            ui.label("Recovery actions").classes("text-base font-semibold")
            ui.label(
                "When verification fails, one or more of these steps run. Any that "
                "were used appear in the self-healing trace under the answer."
            ).classes("text-sm shr-muted")

            order = (
                RecoveryAction.REWRITE_QUERY,
                RecoveryAction.RETRY_RETRIEVAL,
                RecoveryAction.WEB_SEARCH,
                RecoveryAction.MERGE_CONTEXT,
                RecoveryAction.STRICT_GROUNDING,
                RecoveryAction.LOG_KNOWLEDGE_GAP,
                RecoveryAction.ASK_CLARIFICATION,
                RecoveryAction.STOP,
            )

            with ui.grid(columns=2).classes("w-full gap-2 pt-1"):
                for action in order:
                    meta = RECOVERY_ACTION_META[action.value]

                    with ui.row().classes(
                        "items-start gap-2.5 no-wrap p-3 shr-surface-alt"
                    ).style(f"border-left: 3px solid {meta.color};"):
                        ui.icon(meta.icon, size="17px").style(
                            f"color: {meta.color}; flex-shrink: 0; margin-top: 1px;"
                        )
                        with ui.column().classes("gap-0 min-w-0"):
                            ui.label(meta.label).classes(
                                "text-sm font-medium"
                            ).style(f"color: {meta.color}")
                            ui.label(meta.description).classes(
                                "text-xs shr-muted leading-snug"
                            )

    def _build_signals(self) -> None:
        signals: tuple[tuple[str, str, str, str], ...] = (
            (
                "verified",
                theme.POSITIVE,
                "Grounded",
                "Every factual claim in the answer traces back to retrieved "
                "evidence. If even one does not, the answer is marked ungrounded.",
            ),
            (
                "dangerous",
                theme.NEGATIVE,
                "Hallucination risk",
                "Whether the model invented facts or contradicted its evidence. "
                "Rated low, medium or high by an independent judge.",
            ),
            (
                "speed",
                theme.PRIMARY,
                "Confidence",
                "A weighted blend of how well the evidence matched the question "
                "and how firmly the answer is grounded, penalised when "
                "hallucination risk is elevated.",
            ),
            (
                "insights",
                theme.SECONDARY,
                "RAGAS",
                "Standard retrieval-augmented generation metrics. Faithfulness and "
                "answer relevancy run on every query; context precision and recall "
                "require a labelled dataset and stay empty in normal use.",
            ),
        )

        with ui.column().classes("w-full gap-3 p-5 shr-surface"):
            ui.label("Reading the signals").classes("text-base font-semibold")
            ui.label(
                "Each answer carries these measurements. They are shown as chips "
                "under the answer and in full on the evaluation page."
            ).classes("text-sm shr-muted")

            with ui.column().classes("w-full gap-2 pt-1"):
                for icon, color, title, description in signals:
                    with ui.row().classes(
                        "items-start gap-3 no-wrap p-3 shr-surface-alt"
                    ):
                        ui.icon(icon, size="18px").style(
                            f"color: {color}; flex-shrink: 0; margin-top: 1px;"
                        )
                        with ui.column().classes("gap-0 min-w-0"):
                            ui.label(title).classes("text-sm font-medium").style(
                                f"color: {color}"
                            )
                            ui.label(description).classes(
                                "text-sm shr-muted leading-snug"
                            )

    def _build_notes(self) -> None:
        with ui.column().classes("w-full gap-3 p-5 shr-surface"):
            ui.label("Good to know").classes("text-base font-semibold")

            notes: tuple[tuple[str, str], ...] = (
                (
                    "bedtime",
                    "The backend sleeps when idle. The first question after a "
                    "quiet period can take up to a minute and a half while it "
                    "wakes up and reconnects to its services.",
                ),
                (
                    "devices",
                    "Conversations are listed per browser. The messages themselves "
                    "live on the server, but the list of which conversations are "
                    "yours is stored locally and will not follow you to another "
                    "device.",
                ),
                (
                    "search_off",
                    "If the knowledge base has nothing relevant, the system says so "
                    "rather than guessing. That refusal is the grounding rules "
                    "working as intended, not a failure.",
                ),
                (
                    "travel_explore",
                    "When internal evidence falls short, the recovery loop may "
                    "consult the live web. Those sources are labelled separately "
                    "in the citation list.",
                ),
            )

            for icon, text in notes:
                with ui.row().classes("items-start gap-3 no-wrap"):
                    ui.icon(icon, size="17px").classes("shr-muted").style(
                        "flex-shrink: 0; margin-top: 2px;"
                    )
                    ui.label(text).classes("text-sm shr-muted leading-relaxed")

            ui.element("div").classes("w-full my-1").style(
                "height: 1px; background: var(--shr-border);"
            )

            with ui.row().classes("w-full items-center gap-3 no-wrap flex-wrap"):
                ui.label(f"Version {APP_VERSION}").classes("text-xs shr-muted")
                ui.label("·").classes("text-xs shr-muted").style("opacity: 0.5;")
                ui.label(settings.api_host).classes("shr-mono text-xs shr-muted")
                ui.space()
                ui.link(
                    "API reference",
                    f"{settings.api_base_url}{Endpoint.DOCS}",
                    new_tab=True,
                ).classes("text-xs no-underline").style(f"color: {theme.PRIMARY}")


@ui.page(Route.ABOUT)
def about_page() -> None:
    page = AboutPage()
    page.build()