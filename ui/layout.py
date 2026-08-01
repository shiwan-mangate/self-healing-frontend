from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator, Optional

from nicegui import ui

from api.client import api_client
from api.errors import ApiError
from app import state
from app.config import settings
from app.constants import (
    APP_NAME,
    APP_TAGLINE,
    APP_VERSION,
    COLD_START_MESSAGE,
    Endpoint,
    NAV_ITEMS,
    Route,
)
from ui import theme

logger = logging.getLogger(__name__)


class BackendStatus:
    def __init__(self) -> None:
        self._dot: Optional[ui.element] = None
        self._label: Optional[ui.label] = None
        self._state = "unknown"

    def build(self) -> None:
        with ui.row().classes("items-center gap-2 no-wrap").style("flex-shrink: 0;"):
            self._dot = (
                ui.element("div")
                .classes("shr-pulse")
                .style(
                    "width: 8px; height: 8px; border-radius: 50%; "
                    "background: #8a93a6; flex-shrink: 0;"
                )
            )
            self._label = ui.label("Checking…").classes(
                "text-xs shr-muted hidden sm:block"
            )

    def _render(self, color: str, text: str, pulse: bool) -> None:
        if self._dot is None or self._label is None:
            return
        self._dot.style(
            f"width: 8px; height: 8px; border-radius: 50%; "
            f"background: {color}; flex-shrink: 0;"
        )
        if pulse:
            self._dot.classes(add="shr-pulse")
        else:
            self._dot.classes(remove="shr-pulse")
        self._label.set_text(text)

    def set_checking(self) -> None:
        self._state = "checking"
        self._render("#8a93a6", "Checking…", pulse=True)

    def set_online(self) -> None:
        self._state = "online"
        self._render(theme.POSITIVE, "Backend online", pulse=False)

    def set_waking(self) -> None:
        self._state = "waking"
        self._render(theme.WARNING, "Waking up…", pulse=True)

    def set_offline(self) -> None:
        self._state = "offline"
        self._render(theme.NEGATIVE, "Backend offline", pulse=False)

    @property
    def is_online(self) -> bool:
        return self._state == "online"

    async def probe(self) -> bool:
        self.set_checking()
        try:
            report = await api_client.check_liveness()
        except ApiError as exc:
            if exc.is_cold_start_suspect:
                self.set_waking()
            else:
                self.set_offline()
            return False

        if report.alive:
            self.set_online()
            return True

        self.set_offline()
        return False


def cold_start_banner() -> Optional[ui.element]:
    if not settings.should_warm_up:
        return None

    with ui.row().classes(
        "w-full items-center gap-3 px-4 py-2 no-wrap shr-fill"
    ).style(
        f"background: {theme.WARNING}18; "
        f"border-bottom: 1px solid {theme.WARNING}38; flex-shrink: 0;"
    ) as banner:
        ui.icon("bedtime", size="18px").style(f"color: {theme.WARNING}")
        ui.label(
            COLD_START_MESSAGE.format(seconds=settings.cold_start_estimate)
        ).classes("text-xs").style(f"color: {theme.WARNING}")
        ui.space()
        ui.button(icon="close", on_click=banner.delete).props(
            "flat dense round size=sm"
        ).style(f"color: {theme.WARNING}")

    return banner


def _nav_button(label: str, route: str, icon: str, active: bool) -> None:
    classes = (
        "w-full justify-start items-center gap-3 px-3 py-2 no-wrap "
        "shr-clickable shr-fill"
    )
    style = (
        f"border-radius: 8px; background: {theme.PRIMARY}1f; "
        f"border-left: 3px solid {theme.PRIMARY};"
        if active
        else "border-radius: 8px; border-left: 3px solid transparent;"
    )

    with ui.row().classes(classes).style(style).on(
        "click", lambda r=route: ui.navigate.to(r)
    ):
        ui.icon(icon, size="20px").style(
            f"color: {theme.PRIMARY}" if active else "color: var(--shr-text-muted)"
        )
        ui.label(label).classes("text-sm").style(
            f"color: {theme.PRIMARY}; font-weight: 600;"
            if active
            else "color: var(--shr-text); font-weight: 500;"
        )


def _build_drawer(current_route: str) -> ui.left_drawer:
    drawer = (
        ui.left_drawer(top_corner=False, bottom_corner=True)
        .props("width=248 bordered")
        .classes("p-3 gap-1")
        .style("overflow-x: hidden;")
    )

    with drawer:
        with ui.column().classes("w-full gap-1 shr-fill"):
            for item in NAV_ITEMS:
                _nav_button(
                    item.label,
                    item.route,
                    item.icon,
                    active=current_route == item.route,
                )

        ui.space()

        with ui.column().classes("w-full gap-2 mt-auto pt-3 shr-fill").style(
            "border-top: 1px solid var(--shr-border);"
        ):
            with ui.row().classes("items-center gap-2 no-wrap w-full shr-fill"):
                ui.icon("dns", size="16px").classes("shr-muted").style(
                    "flex-shrink: 0;"
                )
                ui.label(settings.api_host).classes(
                    "shr-mono text-xs shr-muted ellipsis"
                ).style("min-width: 0; overflow: hidden; text-overflow: ellipsis;").tooltip(
                    settings.api_base_url
                )

            with ui.row().classes("items-center gap-2 no-wrap w-full shr-fill"):
                ui.icon("api", size="16px").classes("shr-muted").style(
                    "flex-shrink: 0;"
                )
                ui.link(
                    "API reference",
                    f"{settings.api_base_url}{Endpoint.DOCS}",
                    new_tab=True,
                ).classes("text-xs no-underline").style(f"color: {theme.PRIMARY}")

    return drawer


def _build_header(drawer: ui.left_drawer, status: BackendStatus) -> None:
    with ui.header(elevated=False).classes(
        "items-center px-3 gap-3 no-wrap shr-fill"
    ).style(f"height: {theme.HEADER_HEIGHT}px; min-height: {theme.HEADER_HEIGHT}px;"):
        ui.button(icon="menu", on_click=drawer.toggle).props(
            "flat dense round"
        ).classes("lg:hidden").style("flex-shrink: 0;")

        with ui.row().classes(
            "items-center gap-2 no-wrap cursor-pointer"
        ).style("flex-shrink: 0;").on("click", lambda: ui.navigate.to(Route.CHAT)):
            ui.icon("autorenew", size="24px").style(f"color: {theme.PRIMARY}")
            with ui.column().classes("gap-0"):
                ui.label(APP_NAME).classes(
                    "text-sm font-semibold leading-tight"
                ).style("white-space: nowrap;")
                ui.label(APP_TAGLINE).classes(
                    "text-xs shr-muted leading-tight hidden md:block"
                ).style("white-space: nowrap;")

        ui.space()

        status.build()

        dark_icon = "light_mode" if state.is_dark_mode() else "dark_mode"

        def _toggle() -> None:
            enabled = theme.toggle_dark()
            toggle_button.props(f'icon={"light_mode" if enabled else "dark_mode"}')

        toggle_button = (
            ui.button(icon=dark_icon, on_click=_toggle)
            .props("flat dense round")
            .style("flex-shrink: 0;")
            .tooltip("Toggle theme")
        )


def _build_footer() -> None:
    with ui.footer(elevated=False).classes(
        "items-center px-4 gap-3 no-wrap shr-fill"
    ).style(f"height: {theme.FOOTER_HEIGHT}px; min-height: {theme.FOOTER_HEIGHT}px;"):
        ui.label(f"{APP_NAME} v{APP_VERSION}").classes("text-xs shr-muted").style(
            "white-space: nowrap;"
        )
        ui.space()
        ui.label("Grounding · Hallucination · RAGAS · Self-healing").classes(
            "text-xs shr-muted hidden md:block"
        ).style("white-space: nowrap;")


@contextmanager
def page_shell(
    current_route: str,
    *,
    max_width: Optional[str] = None,
    padded: bool = True,
    probe_backend: bool = True,
) -> Iterator[BackendStatus]:
    theme.apply()

    status = BackendStatus()
    drawer = _build_drawer(current_route)
    _build_header(drawer, status)
    _build_footer()

    resolved_width = max_width or f"{theme.CONTENT_MAX_WIDTH}px"

    with ui.column().classes("w-full items-center gap-0 shr-fill").style(
        "padding: 0; margin: 0;"
    ):
        container_classes = "w-full gap-4 shr-fade-in shr-fill"
        if padded:
            container_classes += " p-4 md:p-6"

        with ui.column().classes(container_classes).style(
            f"max-width: {resolved_width};"
        ):
            yield status

    if probe_backend:
        ui.timer(0.15, lambda: status.probe(), once=True)


@contextmanager
def full_height_shell(
    current_route: str,
    *,
    probe_backend: bool = True,
) -> Iterator[BackendStatus]:
    theme.apply()

    status = BackendStatus()
    drawer = _build_drawer(current_route)
    _build_header(drawer, status)

    with ui.column().classes("w-full gap-0 no-wrap shr-fill").style(
        f"height: calc(100vh - {theme.HEADER_HEIGHT}px); "
        "min-height: 0; overflow: hidden;"
    ):
        yield status

    if probe_backend:
        ui.timer(0.15, lambda: status.probe(), once=True)


def section_header(
    title: str,
    subtitle: Optional[str] = None,
    icon: Optional[str] = None,
) -> None:
    with ui.row().classes("w-full items-start gap-3 no-wrap shr-fill"):
        if icon:
            ui.icon(icon, size="26px").style(
                f"color: {theme.PRIMARY}; flex-shrink: 0;"
            )
        with ui.column().classes("gap-0 shr-flex-min").style("flex: 1 1 auto;"):
            ui.label(title).classes("text-lg font-semibold leading-tight")
            if subtitle:
                ui.label(subtitle).classes("text-sm shr-muted leading-snug")


def empty_state(
    icon: str,
    headline: str,
    body: Optional[str] = None,
    *,
    color: str = theme.MUTED,
) -> None:
    with ui.column().classes(
        "w-full items-center justify-center gap-2 py-12 px-6 text-center shr-fill"
    ):
        ui.icon(icon, size="44px").style(f"color: {color}; opacity: 0.55;")
        ui.label(headline).classes("text-base font-medium")
        if body:
            ui.label(body).classes("text-sm shr-muted").style("max-width: 28rem;")


def card(
    *,
    padded: bool = True,
    alt: bool = False,
    gap: str = "gap-3",
) -> ui.element:
    classes = f"w-full {gap} shr-fill "
    classes += "shr-surface-alt" if alt else "shr-surface"
    if padded:
        classes += " p-4"
    return ui.column().classes(classes)


def responsive_grid(columns: int = 2, gap: str = "gap-4") -> ui.element:
    return ui.element("div").classes(
        f"w-full grid grid-cols-1 md:grid-cols-{columns} {gap} items-start shr-fill"
    )