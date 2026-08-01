from __future__ import annotations

from typing import Optional, Sequence

from nicegui import ui

from api.models import Citation
from app.constants import score_color
from ui import theme
from ui.components.notify import copy_to_clipboard
from utils.formatters import (
    format_count,
    format_score,
    format_source_label,
    truncate_middle,
)


_SOURCE_ICONS: dict[str, str] = {
    "pdf": "picture_as_pdf",
    "docx": "description",
    "doc": "description",
    "pptx": "slideshow",
    "ppt": "slideshow",
    "txt": "article",
    "log": "receipt_long",
    "csv": "table_chart",
    "md": "article",
    "markdown": "article",
    "html": "html",
    "htm": "html",
    "url": "link",
    "web": "travel_explore",
}

_WEB_COLOR = "#22c9a8"


def _source_icon(source_type: Optional[str]) -> str:
    if not source_type:
        return "description"
    return _SOURCE_ICONS.get(source_type.strip().lower(), "description")


def _is_url(value: str) -> bool:
    lowered = value.strip().lower()
    return lowered.startswith("http://") or lowered.startswith("https://")


def citation_marker(citation: Citation, *, size: int = 22) -> ui.element:
    index = citation.marker_index
    text = str(index) if index is not None else "·"

    with ui.element("div").classes("flex items-center justify-center").style(
        f"min-width: {size}px; height: {size}px; padding: 0 6px; border-radius: 6px; "
        f"background: {theme.PRIMARY}1f; border: 1px solid {theme.PRIMARY}3d; "
        "flex-shrink: 0;"
    ) as marker:
        ui.label(text).classes("text-xs font-semibold leading-none").style(
            f"color: {theme.PRIMARY}"
        )

    return marker


def citation_row(citation: Citation, *, show_chunk_id: bool = True) -> ui.element:
    is_web = citation.is_web_source or _is_url(citation.document_id)
    accent = _WEB_COLOR if is_web else theme.PRIMARY
    icon = "travel_explore" if is_web else _source_icon(citation.source_type)
    score_tone = score_color(citation.relevance_score)

    with ui.row().classes(
        "w-full items-start gap-3 no-wrap p-3 shr-surface-alt shr-hover-lift"
    ).style(f"border-left: 3px solid {accent};") as row:
        citation_marker(citation)

        with ui.column().classes("gap-1 flex-grow min-w-0"):
            with ui.row().classes("items-center gap-2 no-wrap w-full"):
                ui.icon(icon, size="15px").style(f"color: {accent}; flex-shrink: 0;")

                name = citation.display_name
                if _is_url(name):
                    ui.link(
                        format_source_label(name),
                        name,
                        new_tab=True,
                    ).classes("text-sm font-medium no-underline ellipsis").style(
                        f"color: {accent}"
                    ).tooltip(name)
                else:
                    ui.label(truncate_middle(name, 64)).classes(
                        "text-sm font-medium ellipsis"
                    ).tooltip(name)

            with ui.row().classes("items-center gap-2 no-wrap flex-wrap"):
                location = citation.display_location
                if location:
                    ui.label(location).classes("text-xs shr-muted")

                if is_web:
                    with ui.row().classes("items-center gap-1 no-wrap px-1.5").style(
                        f"background: {_WEB_COLOR}1a; border-radius: 4px;"
                    ):
                        ui.label("WEB").classes("text-xs font-semibold").style(
                            f"color: {_WEB_COLOR}; font-size: 9px;"
                        )

                if show_chunk_id:
                    ui.label(truncate_middle(citation.chunk_id, 22)).classes(
                        "shr-mono text-xs shr-muted"
                    ).style("opacity: 0.65;").tooltip(f"Chunk ID: {citation.chunk_id}")

        with ui.column().classes("items-end gap-1 no-wrap").style("flex-shrink: 0;"):
            ui.label(format_score(citation.relevance_score)).classes(
                "shr-mono text-xs font-semibold"
            ).style(f"color: {score_tone}")

            with ui.element("div").style(
                "width: 44px; height: 4px; border-radius: 2px; "
                "background: var(--shr-surface); overflow: hidden;"
            ):
                width = max(0.0, min(1.0, citation.relevance_score)) * 100
                ui.element("div").style(
                    f"width: {width:.1f}%; height: 100%; background: {score_tone}; "
                    "border-radius: 2px;"
                )

            ui.label("relevance").classes("text-xs shr-muted").style(
                "font-size: 9px; opacity: 0.7;"
            )

    return row


def citation_list(
    citations: Sequence[Citation],
    *,
    show_chunk_id: bool = True,
) -> Optional[ui.element]:
    if not citations:
        return None

    with ui.column().classes("w-full gap-2") as container:
        for citation in citations:
            citation_row(citation, show_chunk_id=show_chunk_id)

    return container


def source_summary(citations: Sequence[Citation]) -> Optional[ui.element]:
    if not citations:
        return None

    seen: set[str] = set()
    entries: list[tuple[str, bool, str]] = []

    for citation in citations:
        name = citation.display_name
        if name in seen:
            continue
        seen.add(name)
        is_web = citation.is_web_source or _is_url(citation.document_id)
        entries.append((name, is_web, citation.source_type or ""))

    with ui.row().classes("items-center gap-1.5 no-wrap flex-wrap") as container:
        for name, is_web, source_type in entries:
            accent = _WEB_COLOR if is_web else theme.MUTED
            icon = "travel_explore" if is_web else _source_icon(source_type)

            with ui.row().classes("items-center gap-1 no-wrap px-2 py-1").style(
                f"background: {accent}14; border: 1px solid {accent}2b; "
                "border-radius: 999px; max-width: 220px;"
            ).tooltip(name):
                ui.icon(icon, size="12px").style(f"color: {accent}; flex-shrink: 0;")
                ui.label(format_source_label(name, limit=28)).classes(
                    "text-xs ellipsis"
                ).style(f"color: {accent}")

    return container


def citation_panel(
    citations: Sequence[Citation],
    *,
    title: str = "Sources",
    show_summary: bool = True,
) -> Optional[ui.element]:
    if not citations:
        return None

    unique_count = len({c.display_name for c in citations})

    with ui.column().classes("w-full gap-3 p-4 shr-surface") as panel:
        with ui.row().classes("w-full items-center gap-2 no-wrap"):
            ui.icon("format_quote", size="18px").style(f"color: {theme.PRIMARY}")
            ui.label(title).classes("text-sm font-semibold")
            ui.space()
            ui.label(
                f"{format_count(len(citations), 'citation')} · "
                f"{format_count(unique_count, 'document')}"
            ).classes("text-xs shr-muted")

        if show_summary and unique_count > 1:
            source_summary(citations)
            ui.element("div").classes("w-full").style(
                "height: 1px; background: var(--shr-border);"
            )

        citation_list(citations)

    return panel


def citation_expander(
    citations: Sequence[Citation],
    *,
    default_open: bool = False,
) -> Optional[ui.element]:
    if not citations:
        return None

    unique_count = len({c.display_name for c in citations})
    label = (
        f"Sources · {format_count(len(citations), 'citation')} "
        f"from {format_count(unique_count, 'document')}"
    )

    with ui.expansion(label, icon="format_quote", value=default_open).classes(
        "w-full shr-surface-alt"
    ).props("dense expand-separator") as expander:
        with ui.column().classes("w-full gap-2 pt-2 pb-1"):
            citation_list(citations)

    return expander


def no_citations_note() -> ui.element:
    with ui.row().classes("items-center gap-2 no-wrap px-3 py-2").style(
        f"background: {theme.WARNING}12; border: 1px solid {theme.WARNING}2b; "
        "border-radius: 8px;"
    ) as note:
        ui.icon("info_outline", size="15px").style(f"color: {theme.WARNING}")
        ui.label(
            "This answer did not reference any specific source from the knowledge base."
        ).classes("text-xs").style(f"color: {theme.WARNING}")

    return note


def citation_detail_dialog(citation: Citation) -> None:
    is_web = citation.is_web_source or _is_url(citation.document_id)
    accent = _WEB_COLOR if is_web else theme.PRIMARY

    with ui.dialog() as dialog, ui.card().classes("shr-surface p-5 gap-3").style(
        "min-width: 380px; max-width: 560px;"
    ):
        with ui.row().classes("w-full items-center gap-2 no-wrap"):
            citation_marker(citation, size=26)
            ui.label("Citation detail").classes("text-base font-semibold")
            ui.space()
            ui.button(icon="close", on_click=dialog.close).props("flat dense round size=sm")

        ui.element("div").classes("w-full").style(
            "height: 1px; background: var(--shr-border);"
        )

        rows: list[tuple[str, str, bool]] = [
            ("Document", citation.display_name, _is_url(citation.display_name)),
            ("Document ID", citation.document_id, _is_url(citation.document_id)),
            ("Chunk ID", citation.chunk_id, False),
            ("Source type", (citation.source_type or "—").upper(), False),
            (
                "Page",
                str(citation.page_number) if citation.page_number is not None else "—",
                False,
            ),
            ("Relevance", format_score(citation.relevance_score, decimals=4), False),
            ("Inline marker", citation.inline_reference or "—", False),
        ]

        with ui.column().classes("w-full gap-2"):
            for label, value, linkable in rows:
                with ui.row().classes("w-full items-start gap-3 no-wrap"):
                    ui.label(label).classes("text-xs shr-muted").style(
                        "width: 104px; flex-shrink: 0;"
                    )
                    if linkable:
                        ui.link(value, value, new_tab=True).classes(
                            "shr-mono text-xs no-underline break-all"
                        ).style(f"color: {accent}")
                    else:
                        ui.label(value).classes("shr-mono text-xs break-all")

        with ui.row().classes("w-full justify-end gap-2 mt-1 no-wrap"):
            ui.button(
                "Copy chunk ID",
                icon="content_copy",
                on_click=lambda: copy_to_clipboard(citation.chunk_id, label="Chunk ID copied"),
            ).props("flat dense size=sm")

    dialog.open()


def citations_footer(citations: Sequence[Citation]) -> Optional[ui.element]:
    if not citations:
        return None

    with ui.row().classes("items-center gap-2 no-wrap flex-wrap") as container:
        ui.label("Cited:").classes("text-xs shr-muted")
        for citation in citations:
            marker = citation_marker(citation, size=20)
            marker.classes("shr-clickable")
            marker.on("click", lambda c=citation: citation_detail_dialog(c))
            marker.tooltip(citation.display_name)

    return container