from __future__ import annotations

from typing import Callable, Optional

from nicegui import ui

from app import state
from app.constants import MAX_SESSION_TITLE_LENGTH
from app.state import SessionRecord
from ui import theme
from ui.components.notify import confirm, copy_to_clipboard, info, success
from utils.formatters import format_relative, truncate


class SessionSidebar:
    def __init__(
        self,
        *,
        on_select: Callable[[str], None],
        on_create: Callable[[str], None],
        width: int = theme.SIDEBAR_WIDTH,
    ) -> None:
        self._on_select = on_select
        self._on_create = on_create
        self._width = width
        self._list_container: Optional[ui.element] = None
        self._count_label: Optional[ui.label] = None
        self._filter: str = ""

    def build(self) -> ui.element:
        with ui.column().classes("gap-0 no-wrap").style(
            f"width: {self._width}px; min-width: {self._width}px; "
            "flex-shrink: 0; height: 100%; min-height: 0; "
            "border-right: 1px solid var(--shr-border); "
            "background: var(--shr-surface); overflow: hidden;"
        ) as container:
            self._build_header()
            self._build_search()
            self._build_list()
            self._build_footer()

        self.refresh()
        return container

    def _build_header(self) -> None:
        with ui.column().classes("w-full gap-2 p-3 shr-fill").style(
            "border-bottom: 1px solid var(--shr-border); flex-shrink: 0;"
        ):
            ui.button(
                "New conversation",
                icon="add",
                on_click=self._handle_create,
            ).props("unelevated no-caps dense").classes("w-full").style(
                f"background: {theme.PRIMARY}; color: white; "
                "border-radius: 8px; height: 36px;"
            )

    def _build_search(self) -> None:
        with ui.row().classes("w-full px-3 pt-2 pb-1 shr-fill").style(
            "flex-shrink: 0;"
        ):
            search = (
                ui.input(placeholder="Search")
                .props("dense outlined clearable input-class=text-xs")
                .classes("w-full shr-flex-min")
            )
            search.on_value_change(self._handle_filter)

    def _build_list(self) -> None:
        with ui.scroll_area().classes("w-full shr-scroll").style(
            "flex: 1 1 auto; min-height: 0;"
        ):
            self._list_container = ui.column().classes(
                "w-full gap-1 px-2 py-1 shr-fill"
            )

    def _build_footer(self) -> None:
        with ui.row().classes(
            "w-full items-center gap-2 px-3 py-2 no-wrap shr-fill"
        ).style("border-top: 1px solid var(--shr-border); flex-shrink: 0;"):
            self._count_label = ui.label("").classes("text-xs shr-muted").style(
                "white-space: nowrap;"
            )
            ui.space()
            ui.button(icon="delete_sweep", on_click=self._handle_clear_all).props(
                "flat dense round size=sm"
            ).classes("shr-muted").style("flex-shrink: 0;").tooltip(
                "Delete all conversations"
            )

    def _handle_filter(self, event) -> None:
        self._filter = (event.value or "").strip().lower()
        self.refresh()

    def _handle_create(self) -> None:
        record = state.create_session()
        self.refresh()
        self._on_create(record.session_id)

    def _handle_select(self, session_id: str) -> None:
        if session_id == state.get_active_session_id():
            return
        state.set_active_session_id(session_id)
        self.refresh()
        self._on_select(session_id)

    async def _handle_delete(self, record: SessionRecord) -> None:
        approved = await confirm(
            f"Delete “{truncate(record.title, 48)}”? "
            "This removes it from this browser only — the conversation remains "
            "on the server.",
            title="Delete conversation",
            confirm_label="Delete",
            danger=True,
        )
        if not approved:
            return

        was_active = record.session_id == state.get_active_session_id()
        state.delete_session(record.session_id)

        if was_active:
            active = state.ensure_active_session()
            self.refresh()
            self._on_select(active.session_id)
        else:
            self.refresh()

        info("Conversation deleted")

    async def _handle_clear_all(self) -> None:
        records = state.load_sessions()
        if not records:
            return

        approved = await confirm(
            f"Delete all {len(records)} conversations from this browser? "
            "This cannot be undone.",
            title="Delete everything",
            confirm_label="Delete all",
            danger=True,
        )
        if not approved:
            return

        state.clear_sessions()
        active = state.ensure_active_session()
        self.refresh()
        self._on_select(active.session_id)
        info("All conversations deleted")

    def open_rename(self, record: SessionRecord) -> None:
        with ui.dialog() as dialog, ui.card().classes("shr-surface p-5 gap-3").style(
            "min-width: 320px; max-width: 90vw;"
        ):
            ui.label("Rename conversation").classes("text-base font-semibold")

            field = (
                ui.input(value=record.title)
                .props(f"dense outlined autofocus maxlength={MAX_SESSION_TITLE_LENGTH}")
                .classes("w-full")
            )

            def apply() -> None:
                title = (field.value or "").strip()
                if title:
                    state.rename_session(record.session_id, title)
                    self.refresh()
                    success("Conversation renamed")
                dialog.close()
                dialog.delete()

            def cancel() -> None:
                dialog.close()
                dialog.delete()

            field.on("keydown.enter", apply)

            with ui.row().classes("w-full justify-end gap-2 no-wrap"):
                ui.button("Cancel", on_click=cancel).props("flat dense no-caps")
                ui.button("Save", on_click=apply).props(
                    "unelevated dense no-caps"
                ).style(f"background: {theme.PRIMARY}; color: white;")

        dialog.open()

    def _session_item(self, record: SessionRecord, *, active: bool) -> None:
        background = f"{theme.PRIMARY}1a" if active else "transparent"
        border = f"3px solid {theme.PRIMARY}" if active else "3px solid transparent"

        with ui.row().classes(
            "w-full items-center gap-1 no-wrap px-2 py-2 shr-clickable shr-fill"
        ).style(
            f"background: {background}; border-left: {border}; border-radius: 8px;"
        ):
            with ui.column().classes("gap-0 shr-flex-min").style(
                "flex: 1 1 auto; min-width: 0; cursor: pointer;"
            ).on("click", lambda sid=record.session_id: self._handle_select(sid)):
                ui.label(truncate(record.title, 30)).classes(
                    "text-sm leading-tight"
                ).style(
                    (
                        f"color: {theme.PRIMARY}; font-weight: 600;"
                        if active
                        else "color: var(--shr-text); font-weight: 500;"
                    )
                    + " overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"
                ).tooltip(record.title)

                with ui.row().classes("items-center gap-1.5 no-wrap"):
                    ui.label(format_relative(record.last_used_dt)).classes(
                        "text-xs shr-muted"
                    ).style("opacity: 0.75; white-space: nowrap;")

                    if record.message_count:
                        ui.label("·").classes("text-xs shr-muted").style(
                            "opacity: 0.5;"
                        )
                        ui.label(str(record.message_count)).classes(
                            "text-xs shr-muted"
                        ).style("opacity: 0.75;")

            with ui.button(icon="more_vert").props(
                "flat dense round size=sm"
            ).classes("shr-muted").style("flex-shrink: 0;"):
                with ui.menu().props("auto-close"):
                    ui.menu_item(
                        "Rename",
                        on_click=lambda r=record: self.open_rename(r),
                    ).props("dense")
                    ui.menu_item(
                        "Copy session ID",
                        on_click=lambda r=record: copy_to_clipboard(
                            r.session_id, label="Session ID copied"
                        ),
                    ).props("dense")
                    ui.separator()
                    ui.menu_item(
                        "Delete",
                        on_click=lambda r=record: self._handle_delete(r),
                    ).props("dense").style(f"color: {theme.NEGATIVE}")

    def _empty_note(self) -> None:
        with ui.column().classes("w-full items-center gap-1 py-8 px-3 shr-fill"):
            ui.icon("forum", size="28px").classes("shr-muted").style("opacity: 0.4;")
            ui.label(
                "No conversations yet" if not self._filter else "No matches"
            ).classes("text-xs shr-muted text-center")

    def refresh(self) -> None:
        if self._list_container is None:
            return

        records = state.load_sessions()
        active_id = state.get_active_session_id()

        if self._filter:
            visible = [r for r in records if self._filter in r.title.lower()]
        else:
            visible = records

        self._list_container.clear()

        with self._list_container:
            if not visible:
                self._empty_note()
            else:
                for record in visible:
                    self._session_item(record, active=record.session_id == active_id)

        if self._count_label is not None:
            total = len(records)
            label = "1 conversation" if total == 1 else f"{total} conversations"
            self._count_label.set_text(label)


def session_header(record: SessionRecord, *, on_rename: Callable[[], None]) -> ui.element:
    with ui.row().classes(
        "w-full items-center gap-2 no-wrap px-4 py-2 shr-fill"
    ).style(
        "border-bottom: 1px solid var(--shr-border); "
        "background: var(--shr-surface); flex-shrink: 0;"
    ) as header:
        ui.icon("forum", size="17px").classes("shr-muted").style("flex-shrink: 0;")

        ui.label(truncate(record.title, 52)).classes(
            "text-sm font-medium shr-flex-min"
        ).style(
            "min-width: 0; overflow: hidden; text-overflow: ellipsis; "
            "white-space: nowrap;"
        ).tooltip(record.title)

        ui.button(icon="edit", on_click=on_rename).props(
            "flat dense round size=sm"
        ).classes("shr-muted").style("flex-shrink: 0;").tooltip("Rename")

        ui.space()

        ui.label(record.session_id).classes(
            "shr-mono text-xs shr-muted hidden lg:block"
        ).style("opacity: 0.6; white-space: nowrap; flex-shrink: 0;").tooltip(
            "Session ID sent to the backend"
        )

    return header