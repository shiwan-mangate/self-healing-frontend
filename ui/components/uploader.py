from __future__ import annotations

from typing import Awaitable, Callable, Optional

from nicegui import events, ui

from app.config import settings
from app.constants import ALLOWED_UPLOAD_EXTENSIONS, UPLOAD_ACCEPT_ATTR
from ui import theme
from ui.components.notify import error, warning
from utils.formatters import file_extension, format_bytes, format_filename


UploadHandler = Callable[[str, bytes, Optional[str]], Awaitable[None]]


_EXTENSION_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("Documents", "description", (".pdf", ".docx", ".pptx")),
    ("Text", "article", (".txt", ".md", ".markdown", ".log")),
    ("Structured", "table_chart", (".csv", ".html", ".htm")),
)


def supported_types_row() -> ui.element:
    with ui.row().classes("items-center gap-2 no-wrap flex-wrap") as row:
        for label, icon, extensions in _EXTENSION_GROUPS:
            with ui.row().classes("items-center gap-1 no-wrap px-2 py-1").style(
                "background: var(--shr-surface-alt); border-radius: 999px;"
            ).tooltip(", ".join(extensions)):
                ui.icon(icon, size="12px").classes("shr-muted")
                ui.label(label).classes("text-xs shr-muted")

    return row


def validate_upload(filename: str, size: int) -> Optional[str]:
    name = filename.strip()
    if not name:
        return "The file has no name."

    extension = file_extension(name)
    if not extension:
        return f"“{format_filename(name)}” has no file extension."

    if extension not in ALLOWED_UPLOAD_EXTENSIONS:
        supported = ", ".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))
        return f"{extension} files are not supported. Supported types: {supported}"

    if size <= 0:
        return f"“{format_filename(name)}” is empty."

    if size > settings.max_upload_bytes:
        return (
            f"“{format_filename(name)}” is {format_bytes(size)}, "
            f"which exceeds the {settings.max_upload_mb} MB limit."
        )

    return None


class DocumentUploader:
    def __init__(
        self,
        *,
        on_upload: UploadHandler,
        multiple: bool = False,
    ) -> None:
        self._on_upload = on_upload
        self._multiple = multiple
        self._upload: Optional[ui.upload] = None
        self._busy = False

    def build(self) -> ui.element:
        with ui.column().classes("w-full gap-3") as container:
            self._build_drop_zone()

            with ui.row().classes("w-full items-center gap-2 no-wrap flex-wrap"):
                supported_types_row()
                ui.space()
                ui.label(f"Max {settings.max_upload_mb} MB").classes(
                    "text-xs shr-muted"
                )

        return container

    def _build_drop_zone(self) -> None:
        with ui.column().classes(
            "w-full items-center justify-center gap-2 py-6 px-4"
        ).style(
            f"border: 1.5px dashed {theme.PRIMARY}4d; border-radius: 12px; "
            f"background: {theme.PRIMARY}08;"
        ):
            ui.icon("cloud_upload", size="34px").style(
                f"color: {theme.PRIMARY}; opacity: 0.75;"
            )

            ui.label("Drop a document here, or browse").classes(
                "text-sm font-medium"
            )
            ui.label(
                "The file is parsed, chunked, embedded and stored in the vector database."
            ).classes("text-xs shr-muted text-center max-w-sm")

            self._upload = (
                ui.upload(
                    on_upload=self._handle_upload,
                    on_rejected=self._handle_rejected,
                    multiple=self._multiple,
                    auto_upload=True,
                    max_file_size=settings.max_upload_bytes,
                )
                .props(
                    f'accept="{UPLOAD_ACCEPT_ATTR}" flat bordered '
                    'color=primary label="Choose file"'
                )
                .classes("w-full max-w-sm")
            )

    def _handle_rejected(self) -> None:
        warning(
            f"File rejected before upload.",
            caption=(
                f"Check that it is a supported type and under "
                f"{settings.max_upload_mb} MB."
            ),
        )

    async def _handle_upload(self, event: events.UploadEventArguments) -> None:
        if self._busy:
            warning("An upload is already in progress.")
            return

        filename = (event.name or "").strip()

        try:
            content = event.content.read()
        except Exception:
            error("Could not read the uploaded file.")
            return

        problem = validate_upload(filename, len(content))
        if problem:
            error(problem)
            self.reset()
            return

        self._busy = True
        try:
            await self._on_upload(filename, content, event.type)
        finally:
            self._busy = False
            self.reset()

    def reset(self) -> None:
        if self._upload is not None:
            self._upload.reset()

    @property
    def is_busy(self) -> bool:
        return self._busy


def upload_result_row(
    filename: str,
    *,
    succeeded: bool,
    chunks: int = 0,
    elapsed_sec: float = 0.0,
    message: Optional[str] = None,
) -> ui.element:
    color = theme.POSITIVE if succeeded else theme.NEGATIVE
    icon = "check_circle" if succeeded else "error_outline"

    with ui.row().classes("w-full items-center gap-3 no-wrap px-3 py-2").style(
        f"background: {color}0f; border: 1px solid {color}2b; border-radius: 8px;"
    ) as row:
        ui.icon(icon, size="18px").style(f"color: {color}")

        with ui.column().classes("gap-0 flex-grow min-w-0"):
            ui.label(format_filename(filename)).classes(
                "text-sm font-medium ellipsis"
            ).tooltip(filename)

            detail = message or (
                f"{chunks:,} chunks stored in {elapsed_sec:.1f}s"
                if succeeded
                else "Ingestion failed"
            )
            ui.label(detail).classes("text-xs shr-muted")

    return row


def compact_uploader(
    *,
    on_upload: UploadHandler,
    label: str = "Upload document",
) -> ui.upload:
    async def handle(event: events.UploadEventArguments) -> None:
        filename = (event.name or "").strip()

        try:
            content = event.content.read()
        except Exception:
            error("Could not read the uploaded file.")
            return

        problem = validate_upload(filename, len(content))
        if problem:
            error(problem)
            return

        await on_upload(filename, content, event.type)

    return (
        ui.upload(
            on_upload=handle,
            multiple=False,
            auto_upload=True,
            max_file_size=settings.max_upload_bytes,
        )
        .props(
            f'accept="{UPLOAD_ACCEPT_ATTR}" flat dense bordered '
            f'color=primary label="{label}"'
        )
        .classes("w-full")
    )