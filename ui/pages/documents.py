from __future__ import annotations

import logging
from typing import Optional

from nicegui import ui

from app.constants import Route
from app.state import IngestionRecord
from services import document_service
from services.document_service import IngestionOutcome
from ui import layout, theme
from ui.components.notify import (
    confirm,
    error,
    info,
    success,
    warning,
    warning_list,
)
from ui.components.skeleton import ProgressPanel
from ui.components.uploader import DocumentUploader
from ui.components.url_ingest import UrlIngestField, url_note
from utils.formatters import (
    format_duration_sec,
    format_relative,
    format_source_label,
)

logger = logging.getLogger(__name__)


class DocumentsPage:
    def __init__(self) -> None:
        self.uploader: Optional[DocumentUploader] = None
        self.url_field: Optional[UrlIngestField] = None
        self.progress_slot: Optional[ui.element] = None
        self.result_slot: Optional[ui.element] = None
        self.history_slot: Optional[ui.element] = None
        self.stats_slot: Optional[ui.element] = None
        self.progress: Optional[ProgressPanel] = None

    def build(self) -> None:
        with layout.page_shell(Route.DOCUMENTS):
            layout.section_header(
                "Documents",
                "Add sources to the knowledge base. Each one is parsed, chunked, "
                "embedded and stored in the vector database.",
                icon="library_books",
            )

            self.stats_slot = ui.column().classes("w-full gap-0 shr-fill")
            self._render_stats()

            self.progress_slot = ui.column().classes("w-full gap-0 shr-fill")
            self.result_slot = ui.column().classes("w-full gap-2 shr-fill")

            with layout.responsive_grid(columns=2):
                self._build_upload_card()
                self._build_url_card()

            self._build_history()

    def _build_upload_card(self) -> None:
        with ui.column().classes("w-full gap-3 p-4 shr-surface shr-fill"):
            with ui.row().classes("items-center gap-2 no-wrap shr-fill"):
                ui.icon("upload_file", size="18px").style(
                    f"color: {theme.PRIMARY}; flex-shrink: 0;"
                )
                ui.label("Upload a file").classes("text-sm font-semibold")

            self.uploader = DocumentUploader(on_upload=self._handle_upload)
            self.uploader.build()

    def _build_url_card(self) -> None:
        with ui.column().classes("w-full gap-3 p-4 shr-surface shr-fill"):
            with ui.row().classes("items-center gap-2 no-wrap shr-fill"):
                ui.icon("link", size="18px").style(
                    f"color: {theme.PRIMARY}; flex-shrink: 0;"
                )
                ui.label("Ingest from a URL").classes("text-sm font-semibold")

            self.url_field = UrlIngestField(on_submit=self._handle_url)
            self.url_field.build()

            url_note()

    def _build_history(self) -> None:
        with ui.column().classes("w-full gap-3 p-4 shr-surface shr-fill"):
            with ui.row().classes("w-full items-center gap-2 no-wrap shr-fill"):
                ui.icon("history", size="18px").style(
                    f"color: {theme.PRIMARY}; flex-shrink: 0;"
                )
                ui.label("Ingestion history").classes("text-sm font-semibold")
                ui.space()
                ui.button(icon="delete_sweep", on_click=self._handle_clear).props(
                    "flat dense round size=sm"
                ).classes("shr-muted").style("flex-shrink: 0;").tooltip(
                    "Clear history"
                )

            ui.label(
                "Recorded in this browser only. It reflects what you ingested here, "
                "not the full contents of the knowledge base."
            ).classes("text-xs shr-muted leading-snug")

            self.history_slot = ui.column().classes("w-full gap-2 shr-fill")
            self._render_history()

    def _render_stats(self) -> None:
        if self.stats_slot is None:
            return

        self.stats_slot.clear()
        totals = document_service.totals()

        if not totals["attempts"]:
            return

        entries: list[tuple[str, str, str, str]] = [
            ("description", f"{totals['documents']:,}", "Documents", theme.PRIMARY),
            ("dataset", f"{totals['chunks']:,}", "Chunks stored", theme.SECONDARY),
            ("check_circle", f"{totals['successful']:,}", "Successful", theme.POSITIVE),
            ("error_outline", f"{totals['failed']:,}", "Failed", theme.NEGATIVE),
        ]

        with self.stats_slot:
            with ui.element("div").classes(
                "w-full grid grid-cols-2 md:grid-cols-4 gap-2 shr-fill"
            ):
                for icon, value, label, color in entries:
                    with ui.column().classes(
                        "gap-0.5 p-3 shr-surface-alt shr-fill"
                    ):
                        with ui.row().classes("items-center gap-1.5 no-wrap shr-fill"):
                            ui.icon(icon, size="14px").style(
                                f"color: {color}; opacity: 0.85; flex-shrink: 0;"
                            )
                            ui.label(label).classes("text-xs shr-muted").style(
                                "white-space: nowrap;"
                            )
                        ui.label(value).classes(
                            "text-lg font-semibold leading-tight"
                        ).style(f"color: {color}")

    def _start_progress(self, title: str) -> None:
        if self.progress_slot is None:
            return

        self.progress_slot.clear()
        with self.progress_slot:
            self.progress = ProgressPanel(title, icon="hourglass_top")
            self.progress.build()
            self.progress.set_status(
                "Parsing, chunking and embedding — this can take a minute."
            )

    def _stop_progress(self) -> None:
        if self.progress is not None:
            self.progress.dismiss()
            self.progress = None
        if self.progress_slot is not None:
            self.progress_slot.clear()

    def _render_outcome(self, outcome: IngestionOutcome) -> None:
        if self.result_slot is None:
            return

        self.result_slot.clear()

        if outcome.succeeded:
            color, icon = theme.POSITIVE, "check_circle"
            headline = "Ingestion complete"
        elif outcome.completed_without_content:
            color, icon = theme.WARNING, "warning_amber"
            headline = "Nothing was stored"
        else:
            color, icon = theme.NEGATIVE, "error_outline"
            headline = "Ingestion failed"

        slot = self.result_slot

        with slot:
            with ui.column().classes("w-full gap-2 p-4 shr-fade-in shr-fill").style(
                f"background: {color}0f; border: 1px solid {color}2b; "
                "border-radius: 12px;"
            ):
                with ui.row().classes("w-full items-start gap-3 no-wrap shr-fill"):
                    ui.icon(icon, size="20px").style(
                        f"color: {color}; flex-shrink: 0;"
                    )

                    with ui.column().classes("gap-0.5 shr-flex-min").style(
                        "flex: 1 1 auto; min-width: 0;"
                    ):
                        ui.label(headline).classes("text-sm font-semibold").style(
                            f"color: {color}"
                        )
                        ui.label(outcome.label).classes(
                            "text-sm font-medium"
                        ).style(
                            "overflow: hidden; text-overflow: ellipsis; "
                            "white-space: nowrap;"
                        ).tooltip(outcome.source)
                        ui.label(outcome.message).classes(
                            "text-xs shr-muted leading-snug"
                        )

                    ui.button(icon="close", on_click=slot.clear).props(
                        "flat dense round size=sm"
                    ).classes("shr-muted").style("flex-shrink: 0;")

                if outcome.succeeded:
                    with ui.row().classes(
                        "items-center gap-4 no-wrap flex-wrap pl-8 shr-fill"
                    ):
                        self._stat_chip("description", f"{outcome.documents} docs")
                        self._stat_chip("dataset", f"{outcome.chunks:,} chunks")
                        self._stat_chip(
                            "schedule", format_duration_sec(outcome.elapsed_sec)
                        )

                if outcome.warnings:
                    warning_list(outcome.warnings)

    def _stat_chip(self, icon: str, text: str) -> None:
        with ui.row().classes("items-center gap-1 no-wrap"):
            ui.icon(icon, size="13px").classes("shr-muted").style("flex-shrink: 0;")
            ui.label(text).classes("shr-mono text-xs shr-muted").style(
                "white-space: nowrap;"
            )

    def _render_history(self) -> None:
        if self.history_slot is None:
            return

        self.history_slot.clear()
        records = document_service.history()

        with self.history_slot:
            if not records:
                layout.empty_state(
                    "inbox",
                    "No ingestions yet",
                    "Upload a file or paste a URL above to add sources.",
                )
                return

            for record in records:
                self._history_row(record)

    def _history_row(self, record: IngestionRecord) -> None:
        color = theme.POSITIVE if record.succeeded else theme.NEGATIVE
        icon = "link" if record.is_url else "description"

        with ui.row().classes(
            "w-full items-center gap-3 no-wrap px-3 py-2 shr-surface-alt shr-fill"
        ).style(f"border-left: 3px solid {color};"):
            ui.icon(icon, size="16px").style(f"color: {color}; flex-shrink: 0;")

            with ui.column().classes("gap-0 shr-flex-min").style(
                "flex: 1 1 auto; min-width: 0;"
            ):
                label_style = (
                    "overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"
                )

                if record.is_url:
                    ui.link(
                        format_source_label(record.source),
                        record.source,
                        new_tab=True,
                    ).classes("text-sm no-underline").style(
                        f"color: var(--shr-text); {label_style}"
                    ).tooltip(record.source)
                else:
                    ui.label(format_source_label(record.source)).classes(
                        "text-sm"
                    ).style(label_style).tooltip(record.source)

                detail = (
                    f"{record.chunks_persisted:,} chunks · "
                    f"{format_duration_sec(record.elapsed_time_sec)}"
                    if record.succeeded
                    else (record.error or "Failed")
                )
                ui.label(detail).classes("text-xs shr-muted").style(
                    label_style
                ).tooltip(detail)

            ui.label(format_relative(record.ingested_dt)).classes(
                "text-xs shr-muted hidden sm:block"
            ).style("flex-shrink: 0; opacity: 0.75; white-space: nowrap;")

    async def _handle_upload(
        self,
        filename: str,
        content: bytes,
        content_type: Optional[str],
    ) -> None:
        self._start_progress(f"Ingesting {format_source_label(filename)}")

        try:
            outcome = await document_service.ingest_file(
                filename, content, content_type
            )
        finally:
            self._stop_progress()

        self._announce(outcome)
        self._render_outcome(outcome)
        self._render_history()
        self._render_stats()

    async def _handle_url(self, url: str) -> None:
        self._start_progress(f"Fetching {format_source_label(url)}")

        try:
            outcome = await document_service.ingest_url(url)
        finally:
            self._stop_progress()

        self._announce(outcome)
        self._render_outcome(outcome)
        self._render_history()
        self._render_stats()

    def _announce(self, outcome: IngestionOutcome) -> None:
        if outcome.succeeded:
            success(
                f"{outcome.chunks:,} chunks stored",
                caption=outcome.label,
            )
        elif outcome.completed_without_content:
            warning("No usable text was extracted", caption=outcome.label)
        else:
            error("Ingestion failed", caption=outcome.label)

    async def _handle_clear(self) -> None:
        records = document_service.history()
        if not records:
            return

        approved = await confirm(
            f"Clear all {len(records)} history entries from this browser? "
            "Ingested documents remain in the knowledge base.",
            title="Clear history",
            confirm_label="Clear",
            danger=True,
        )
        if not approved:
            return

        document_service.clear_history()
        self._render_history()
        self._render_stats()
        info("History cleared")


@ui.page(Route.DOCUMENTS)
def documents_page() -> None:
    page = DocumentsPage()
    page.build()