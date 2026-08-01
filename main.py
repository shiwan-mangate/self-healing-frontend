from __future__ import annotations

import logging
import sys
from typing import Final

from nicegui import app, ui

from app.config import settings
from app.constants import APP_NAME, APP_TAGLINE, APP_VERSION, Route
from api.client import api_client


def _configure_logging() -> None:
    level = logging.DEBUG if settings.debug else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
        force=True,
    )

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


_configure_logging()
logger: Final[logging.Logger] = logging.getLogger("selfhealing.ui")


PAGES_READY: bool = False

try:
    from ui.pages import about, chat, documents, evaluation, health

    PAGES_READY = True
except ImportError as exc:
    logger.warning("Page modules not yet available (%s). Serving placeholder.", exc)


@app.get("/healthz")
def _healthz() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "selfhealing-rag-frontend",
        "version": APP_VERSION,
        "pages_loaded": str(PAGES_READY),
    }


if not PAGES_READY:

    @ui.page(Route.CHAT)
    def _placeholder() -> None:
        from ui import theme

        theme.apply()

        with ui.column().classes(
            "w-full h-screen items-center justify-center gap-4 p-8"
        ):
            ui.icon("construction", size="56px").style("color: #f0a848")
            ui.label(APP_NAME).classes("text-2xl font-semibold")
            ui.label(APP_TAGLINE).classes("shr-muted text-sm")

            with ui.card().classes("shr-surface p-5 mt-4").style("max-width: 32rem;"):
                ui.label("Scaffold verified").classes("font-semibold mb-2")
                ui.label(
                    "Configuration, models, HTTP client, storage and theme are all "
                    "loaded correctly. Page modules have not been added yet."
                ).classes("shr-muted text-sm")

                ui.separator().classes("my-3")
                ui.label(f"Backend: {settings.api_host}").classes(
                    "shr-mono text-xs shr-muted"
                )
                ui.label(f"Warm-up: {settings.should_warm_up}").classes(
                    "shr-mono text-xs shr-muted"
                )

            async def probe() -> None:
                spinner.visible = True
                try:
                    report = await api_client.check_liveness()
                    ui.notify(
                        f"Backend responded: {report.status}",
                        type="positive" if report.alive else "warning",
                    )
                except Exception as error:
                    ui.notify(f"Backend unreachable: {error}", type="negative")
                finally:
                    spinner.visible = False

            with ui.row().classes("items-center gap-3 mt-2"):
                ui.button(
                    "Test backend connection", icon="cable", on_click=probe
                ).props("unelevated")
                spinner = ui.spinner(size="sm")
                spinner.visible = False


@app.on_startup
async def _on_startup() -> None:
    logger.info("=" * 64)
    logger.info("%s — frontend starting", APP_NAME)
    logger.info(settings.describe())
    logger.info("Pages loaded: %s", PAGES_READY)
    logger.info("=" * 64)

    if settings.should_warm_up:
        try:
            awake = await api_client.warm_up()
            logger.info(
                "Warm-up ping: %s",
                "backend awake" if awake else "backend still waking",
            )
        except Exception as exc:
            logger.warning("Warm-up ping failed: %s", exc)


@app.on_shutdown
async def _on_shutdown() -> None:
    await api_client.aclose()
    logger.info("%s — frontend stopped", APP_NAME)


ui.run(
    host="0.0.0.0",
    port=settings.port,
    title=APP_NAME,
    favicon="🔁",
    storage_secret=settings.storage_secret,
    dark=True,
    reload=settings.debug,
    show=False,
    reconnect_timeout=10.0,
    uvicorn_logging_level="warning" if not settings.debug else "info",
)