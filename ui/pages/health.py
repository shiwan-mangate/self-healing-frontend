from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from nicegui import ui

from api.client import api_client
from api.errors import ApiError
from api.models import LivenessReport, ReadinessReport
from app.config import settings
from app.constants import Endpoint, Route
from ui import layout, theme
from ui.components.notify import copy_to_clipboard, error_card
from ui.components.skeleton import card_skeleton
from utils.formatters import format_latency, format_time_only, humanize_key

logger = logging.getLogger(__name__)


_CHECK_LABELS: dict[str, tuple[str, str]] = {
    "database": (
        "PostgreSQL (Neon)",
        "Vector store, conversation memory and evaluation records.",
    ),
}


class HealthPage:
    def __init__(self) -> None:
        self.liveness: Optional[LivenessReport] = None
        self.readiness: Optional[ReadinessReport] = None
        self.last_error: Optional[ApiError] = None
        self.last_checked: Optional[datetime] = None
        self.checking = False
        self.auto_refresh = True

        self.status_slot: Optional[ui.element] = None
        self.detail_slot: Optional[ui.element] = None
        self.meta_label: Optional[ui.label] = None
        self.timer: Optional[ui.timer] = None

    def build(self) -> None:
        with layout.page_shell(Route.HEALTH, probe_backend=False):
            layout.section_header(
                "Health",
                "Live status of the backend service and the infrastructure it "
                "depends on.",
                icon="monitor_heart",
            )

            self._build_toolbar()

            self.status_slot = ui.column().classes("w-full gap-4 shr-fill")
            self.detail_slot = ui.column().classes("w-full gap-4 shr-fill")

            self._render_loading()
            self._build_endpoint_card()

        ui.timer(0.1, self._check, once=True)
        self.timer = ui.timer(settings.health_poll_interval, self._auto_check)

    def _build_toolbar(self) -> None:
        with ui.row().classes("w-full items-center gap-3 flex-wrap shr-fill"):
            self.meta_label = ui.label("Checking…").classes("text-xs shr-muted").style(
                "white-space: nowrap;"
            )

            ui.space()

            auto = ui.switch("Auto-refresh", value=True).props("dense")
            auto.on_value_change(self._handle_auto_toggle)
            auto.tooltip(
                f"Re-checks every {settings.health_poll_interval}s while this page "
                "is open."
            )

            ui.button("Check now", icon="refresh", on_click=self._check).props(
                "flat dense no-caps size=sm"
            ).style(f"color: {theme.PRIMARY}; flex-shrink: 0;")

    def _handle_auto_toggle(self, event) -> None:
        self.auto_refresh = bool(event.value)
        if self.timer is None:
            return
        if self.auto_refresh:
            self.timer.activate()
        else:
            self.timer.deactivate()

    async def _auto_check(self) -> None:
        if self.auto_refresh and not self.checking:
            await self._check()

    async def _check(self) -> None:
        if self.checking:
            return

        self.checking = True
        self.last_error = None

        try:
            self.liveness = await api_client.check_liveness()
        except ApiError as exc:
            self.liveness = None
            self.readiness = None
            self.last_error = exc
            self.last_checked = datetime.now(timezone.utc)
            self.checking = False
            self._render()
            return
        except Exception:
            logger.exception("Unexpected liveness failure")
            self.liveness = None
            self.readiness = None
            self.last_checked = datetime.now(timezone.utc)
            self.checking = False
            self._render()
            return

        try:
            self.readiness = await api_client.check_readiness()
        except ApiError as exc:
            self.readiness = None
            self.last_error = exc
            logger.info("Readiness check failed: %s", exc.code)
        except Exception:
            self.readiness = None
            logger.exception("Unexpected readiness failure")
        finally:
            self.checking = False

        self.last_checked = datetime.now(timezone.utc)
        self._render()

    def _render_loading(self) -> None:
        if self.status_slot is None:
            return
        self.status_slot.clear()
        with self.status_slot:
            card_skeleton(lines=2)

    def _render(self) -> None:
        self._render_status()
        self._render_detail()
        self._render_meta()

    def _render_meta(self) -> None:
        if self.meta_label is None:
            return
        if self.last_checked is None:
            self.meta_label.set_text("Not checked yet")
            return
        self.meta_label.set_text(
            f"Last checked at {format_time_only(self.last_checked)}"
        )

    def _overall(self) -> tuple[str, str, str, str]:
        if self.liveness is None:
            return (
                theme.NEGATIVE,
                "cloud_off",
                "Backend unreachable",
                "The service did not respond. On a free tier this often means it is "
                "asleep and waking up.",
            )

        if self.readiness is None:
            return (
                theme.WARNING,
                "warning_amber",
                "Process alive, readiness unknown",
                "The service is running but its readiness could not be determined.",
            )

        if self.readiness.ready:
            return (
                theme.POSITIVE,
                "check_circle",
                "All systems operational",
                "The service is running and connected to every dependency it needs.",
            )

        failed = ", ".join(humanize_key(c) for c in self.readiness.failed_checks)
        return (
            theme.NEGATIVE,
            "gpp_bad",
            "Degraded — not accepting traffic",
            f"The process is alive but these dependencies failed: "
            f"{failed or 'unknown'}.",
        )

    def _render_status(self) -> None:
        if self.status_slot is None:
            return

        self.status_slot.clear()
        color, icon, headline, detail = self._overall()

        with self.status_slot:
            with ui.column().classes("w-full gap-3 p-5 shr-fill").style(
                f"background: {color}0d; border: 1px solid {color}2b; "
                "border-radius: 12px;"
            ):
                with ui.row().classes("w-full items-start gap-3 no-wrap shr-fill"):
                    ui.icon(icon, size="28px").style(
                        f"color: {color}; flex-shrink: 0;"
                    )

                    with ui.column().classes("gap-0.5 shr-flex-min").style(
                        "flex: 1 1 auto; min-width: 0;"
                    ):
                        ui.label(headline).classes("text-base font-semibold").style(
                            f"color: {color}"
                        )
                        ui.label(detail).classes("text-sm shr-muted leading-snug")

                    if self.checking:
                        ui.spinner(size="sm").style(
                            f"color: {color}; flex-shrink: 0;"
                        )

                with ui.row().classes("items-center gap-2 flex-wrap shr-fill"):
                    self._probe_pill(
                        "Liveness",
                        self.liveness is not None and self.liveness.alive,
                        "The process is running and answering HTTP.",
                    )
                    self._probe_pill(
                        "Readiness",
                        self.readiness is not None and self.readiness.ready,
                        "Every dependency check passed.",
                    )

                    if self.readiness is not None:
                        with ui.row().classes("items-center gap-1 no-wrap"):
                            ui.icon("timer", size="13px").classes("shr-muted").style(
                                "flex-shrink: 0;"
                            )
                            ui.label(
                                format_latency(self.readiness.latency_ms)
                            ).classes("shr-mono text-xs shr-muted").style(
                                "white-space: nowrap;"
                            ).tooltip(
                                "Time the backend took to run its dependency checks."
                            )

    def _probe_pill(self, label: str, ok: bool, tooltip: str) -> None:
        color = theme.POSITIVE if ok else theme.NEGATIVE
        icon = "check_circle" if ok else "cancel"

        with ui.row().classes("items-center gap-1 no-wrap px-2 py-1").style(
            f"background: {color}1a; border: 1px solid {color}38; "
            "border-radius: 999px; flex-shrink: 0;"
        ).tooltip(tooltip):
            ui.icon(icon, size="13px").style(f"color: {color}")
            ui.label(label).classes("text-xs font-semibold").style(
                f"color: {color}; white-space: nowrap;"
            )

    def _render_detail(self) -> None:
        if self.detail_slot is None:
            return

        self.detail_slot.clear()

        with self.detail_slot:
            if self.last_error is not None and self.liveness is None:
                error_card(self.last_error, on_retry=self._check)
                return

            if self.readiness is not None:
                self._render_dependencies()

    def _render_dependencies(self) -> None:
        if self.readiness is None:
            return

        checks = self.readiness.checks

        with ui.column().classes("w-full gap-3 p-4 shr-surface shr-fill"):
            with ui.row().classes("w-full items-center gap-2 no-wrap shr-fill"):
                ui.icon("lan", size="18px").style(
                    f"color: {theme.PRIMARY}; flex-shrink: 0;"
                )
                ui.label("Dependencies").classes("text-sm font-semibold")
                ui.space()
                ui.label(
                    f"{sum(1 for ok in checks.values() if ok)}/{len(checks)} passing"
                ).classes("text-xs shr-muted").style(
                    "white-space: nowrap; flex-shrink: 0;"
                )

            if not checks:
                ui.label("The backend reported no individual checks.").classes(
                    "text-xs shr-muted"
                )
                return

            for name, ok in checks.items():
                self._dependency_row(name, ok)

    def _dependency_row(self, name: str, ok: bool) -> None:
        label, description = _CHECK_LABELS.get(
            name, (humanize_key(name), "Backend dependency.")
        )
        color = theme.POSITIVE if ok else theme.NEGATIVE

        with ui.row().classes(
            "w-full items-center gap-3 no-wrap px-3 py-2 shr-surface-alt shr-fill"
        ).style(f"border-left: 3px solid {color};"):
            ui.icon("check_circle" if ok else "cancel", size="17px").style(
                f"color: {color}; flex-shrink: 0;"
            )

            with ui.column().classes("gap-0 shr-flex-min").style(
                "flex: 1 1 auto; min-width: 0;"
            ):
                ui.label(label).classes("text-sm font-medium")
                ui.label(description).classes("text-xs shr-muted leading-snug")

            ui.label("Connected" if ok else "Unreachable").classes(
                "text-xs font-semibold"
            ).style(f"color: {color}; flex-shrink: 0; white-space: nowrap;")

    def _build_endpoint_card(self) -> None:
        with ui.column().classes("w-full gap-3 p-4 shr-surface shr-fill"):
            with ui.row().classes("w-full items-center gap-2 no-wrap shr-fill"):
                ui.icon("dns", size="18px").style(
                    f"color: {theme.PRIMARY}; flex-shrink: 0;"
                )
                ui.label("Backend").classes("text-sm font-semibold")
                ui.space()
                ui.link(
                    "Open API docs",
                    f"{settings.api_base_url}{Endpoint.DOCS}",
                    new_tab=True,
                ).classes("text-xs no-underline").style(
                    f"color: {theme.PRIMARY}; flex-shrink: 0; white-space: nowrap;"
                )

            with ui.row().classes("w-full items-center gap-2 no-wrap shr-fill"):
                ui.label(settings.api_base_url).classes(
                    "shr-mono text-xs shr-muted shr-flex-min"
                ).style(
                    "flex: 1 1 auto; min-width: 0; overflow: hidden; "
                    "text-overflow: ellipsis; white-space: nowrap;"
                ).tooltip(settings.api_base_url)

                ui.button(
                    icon="content_copy",
                    on_click=lambda: copy_to_clipboard(
                        settings.api_base_url, label="Backend URL copied"
                    ),
                ).props("flat dense round size=sm").classes("shr-muted").style(
                    "flex-shrink: 0;"
                )

            ui.element("div").classes("w-full").style(
                "height: 1px; background: var(--shr-border);"
            )

            with ui.element("div").classes(
                "w-full grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-2 shr-fill"
            ):
                self._config_row("Chat timeout", f"{settings.timeout_chat}s")
                self._config_row("Ingest timeout", f"{settings.timeout_ingest}s")
                self._config_row("Read timeout", f"{settings.timeout_read}s")
                self._config_row(
                    "Poll interval", f"{settings.health_poll_interval}s"
                )

    def _config_row(self, label: str, value: str) -> None:
        with ui.row().classes("w-full items-center gap-2 no-wrap shr-fill"):
            ui.label(label).classes("text-xs shr-muted shr-flex-min").style(
                "flex: 1 1 auto; min-width: 0; white-space: nowrap;"
            )
            ui.label(value).classes("shr-mono text-xs").style(
                "flex-shrink: 0; white-space: nowrap;"
            )


@ui.page(Route.HEALTH)
def health_page() -> None:
    page = HealthPage()
    page.build()