"""
app/config.py
==========================================================
The single source of truth for runtime configuration.

Architecture rules (mirroring the backend's config/settings.py):
1.  EXCLUSIVE OWNER OF os.environ. No other module in this
    project reads environment variables directly. If a value
    is needed elsewhere, it is exposed as an attribute here.
2.  FAIL FAST, FAIL LOUD. A malformed API_BASE_URL is a
    deployment error, not a runtime surprise. It raises at
    import time so Render marks the deploy unhealthy instead
    of serving a broken UI.
3.  TOLERANT OF JUNK, INTOLERANT OF NONSENSE. A typo'd
    integer falls back to its default with a warning; a
    missing backend URL is fatal.
4.  IMMUTABLE. The Settings object is frozen. Configuration
    cannot drift after boot.

Note on the backend contract: this project talks to a FastAPI
service with no authentication, so there are no secrets here
beyond STORAGE_SECRET, which signs this app's own session
cookie. Groq / Neon / HuggingFace / Tavily credentials live
exclusively on the backend and must never appear in this repo.
"""

from __future__ import annotations

import logging
import os
import secrets
from dataclasses import dataclass, field
from typing import Final, FrozenSet
from urllib.parse import urlparse

from dotenv import load_dotenv

# Load .env for local development. On Render the variables are
# already present in the process environment, and load_dotenv()
# is a harmless no-op because no .env file is deployed.
# override=False guarantees real environment variables always
# win over a stale local file.
load_dotenv(override=False)

logger = logging.getLogger(__name__)


# ==========================================================
# Primitive readers
# ==========================================================
# Each reader is total: it always returns a usable value of the
# right type. Bad input degrades to the default and is logged
# rather than crashing the process, because a mistyped timeout
# should never take down the whole frontend.

def _read_str(key: str, default: str = "") -> str:
    """Reads a string, treating whitespace-only values as absent."""
    raw = os.environ.get(key)
    if raw is None:
        return default
    cleaned = raw.strip()
    return cleaned if cleaned else default


def _read_bool(key: str, default: bool) -> bool:
    """
    Reads a boolean. Accepts the forms people actually type in
    dashboards: true/false, 1/0, yes/no, on/off. Case-insensitive.
    """
    raw = _read_str(key)
    if not raw:
        return default

    lowered = raw.lower()
    if lowered in {"true", "1", "yes", "y", "on"}:
        return True
    if lowered in {"false", "0", "no", "n", "off"}:
        return False

    logger.warning(
        "Config: %s=%r is not a recognised boolean. Falling back to %s.",
        key, raw, default,
    )
    return default


def _read_int(key: str, default: int, minimum: int, maximum: int) -> int:
    """
    Reads an integer and clamps it into [minimum, maximum].

    Clamping rather than rejecting is deliberate: a timeout of 0
    or 999999 is almost always a typo, and silently honouring it
    produces bugs that are very hard to trace back to config.
    """
    raw = _read_str(key)
    if not raw:
        return default

    try:
        value = int(raw)
    except ValueError:
        logger.warning(
            "Config: %s=%r is not an integer. Falling back to %d.",
            key, raw, default,
        )
        return default

    if value < minimum or value > maximum:
        clamped = max(minimum, min(value, maximum))
        logger.warning(
            "Config: %s=%d is outside the sane range [%d, %d]. Clamped to %d.",
            key, value, minimum, maximum, clamped,
        )
        return clamped

    return value


def _read_float(key: str, default: float, minimum: float, maximum: float) -> float:
    """Float equivalent of _read_int, with the same clamping policy."""
    raw = _read_str(key)
    if not raw:
        return default

    try:
        value = float(raw)
    except ValueError:
        logger.warning(
            "Config: %s=%r is not a number. Falling back to %s.",
            key, raw, default,
        )
        return default

    if value < minimum or value > maximum:
        clamped = max(minimum, min(value, maximum))
        logger.warning(
            "Config: %s=%s is outside the sane range [%s, %s]. Clamped to %s.",
            key, value, minimum, maximum, clamped,
        )
        return clamped

    return value


# ==========================================================
# Specialised readers
# ==========================================================

def _read_base_url(key: str) -> str:
    """
    Reads and validates the backend base URL.

    This is the one genuinely fatal setting: with a bad value
    every single page in the app is broken, so we refuse to boot
    rather than serve a UI where nothing works.

    Normalises by stripping trailing slashes so that endpoint
    paths in app/constants.py can be joined without producing
    a double slash.
    """
    raw = _read_str(key)

    if not raw:
        raise RuntimeError(
            f"{key} is not set. Point it at the Self-Healing RAG API, e.g.\n"
            f"    {key}=https://self-healing-rag-api-v3.onrender.com\n"
            "Set it in .env locally, or in the Render dashboard when deployed."
        )

    parsed = urlparse(raw)

    if parsed.scheme not in {"http", "https"}:
        raise RuntimeError(
            f"{key}={raw!r} must start with http:// or https://. "
            "A bare hostname will not resolve."
        )

    if not parsed.netloc:
        raise RuntimeError(
            f"{key}={raw!r} has no host component. "
            "Expected something like https://example.onrender.com"
        )

    normalised = raw.rstrip("/")

    # A deployed backend reached over plain HTTP is a real problem
    # worth flagging, but localhost over HTTP is perfectly normal.
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "0.0.0.0"}:
        logger.warning(
            "Config: %s uses plain http:// for a remote host (%s). "
            "Traffic will be unencrypted.",
            key, parsed.hostname,
        )

    return normalised


def _read_storage_secret(key: str, debug: bool) -> str:
    """
    Reads the signing key for NiceGUI's app.storage.user cookie.

    That cookie holds this browser's session registry and theme
    choice. Render's filesystem is ephemeral, so the cookie is
    the store — there is deliberately no SQLite file.

    In production a missing or placeholder secret is fatal: an
    ephemeral key would silently invalidate every visitor's saved
    sessions on each restart. In debug we generate a throwaway
    key so a fresh clone runs without any setup.
    """
    raw = _read_str(key)

    placeholder = "replace-me-with-a-random-32-byte-urlsafe-string"
    is_unset = (not raw) or raw == placeholder
    is_too_short = bool(raw) and len(raw) < 32

    if is_unset or is_too_short:
        if debug:
            logger.warning(
                "Config: %s is unset or weak. Generating an ephemeral key for "
                "this debug run. Saved sessions will not survive a restart.",
                key,
            )
            return secrets.token_urlsafe(32)

        reason = "is not set" if is_unset else "is shorter than 32 characters"
        raise RuntimeError(
            f"{key} {reason}. Generate a strong value with:\n"
            '    python -c "import secrets; print(secrets.token_urlsafe(32))"\n'
            "then set it in the Render dashboard. Without a stable secret, "
            "every visitor loses their saved sessions on each restart."
        )

    return raw


# ==========================================================
# Settings
# ==========================================================

@dataclass(frozen=True)
class Settings:
    """
    Immutable, validated runtime configuration.

    Instantiated exactly once at import time as the module-level
    `settings` singleton. Every field maps to a key documented in
    .env.example.
    """

    # --- Backend API ------------------------------------------
    api_base_url: str

    # --- Timeouts (seconds) -----------------------------------
    timeout_chat: int
    timeout_ingest: int
    timeout_read: int
    timeout_health: int

    # --- Cold start (Render free tier) ------------------------
    cold_start_estimate: int
    warmup_on_load: bool

    # --- Evaluation fetch -------------------------------------
    eval_fetch_retries: int
    eval_retry_delay: float

    # --- Health page ------------------------------------------
    health_poll_interval: int

    # --- Uploads ----------------------------------------------
    max_upload_mb: int

    # --- Session storage --------------------------------------
    storage_secret: str = field(repr=False)  # never logged

    # --- Server -----------------------------------------------
    port: int
    debug: bool

    # ------------------------------------------------------
    # Derived helpers
    # ------------------------------------------------------

    @property
    def max_upload_bytes(self) -> int:
        """Upload ceiling in bytes, for direct comparison against file size."""
        return self.max_upload_mb * 1024 * 1024

    @property
    def api_host(self) -> str:
        """Hostname only. Used in the footer so users can see which backend they are hitting."""
        return urlparse(self.api_base_url).netloc

    @property
    def is_local_backend(self) -> bool:
        """
        True when the backend runs on this machine.

        Local backends do not sleep, so the cold-start banner and
        the warm-up ping are pointless noise and get suppressed.
        """
        host = urlparse(self.api_base_url).hostname or ""
        return host in {"localhost", "127.0.0.1", "0.0.0.0"}

    @property
    def should_warm_up(self) -> bool:
        """Warm-up only matters for a remote backend that can sleep."""
        return self.warmup_on_load and not self.is_local_backend

    def url(self, path: str) -> str:
        """
        Joins an endpoint path onto the base URL.

        Accepts paths with or without a leading slash so callers
        cannot accidentally produce a double slash.
        """
        return f"{self.api_base_url}/{path.lstrip('/')}"

    def describe(self) -> str:
        """A single-line, secret-free summary for the boot log."""
        return (
            f"api={self.api_base_url} | "
            f"timeouts(chat={self.timeout_chat}s, ingest={self.timeout_ingest}s, "
            f"read={self.timeout_read}s, health={self.timeout_health}s) | "
            f"warmup={self.should_warm_up} | "
            f"max_upload={self.max_upload_mb}MB | "
            f"port={self.port} | debug={self.debug}"
        )


def _build_settings() -> Settings:
    """
    Factory that reads, validates, and freezes configuration.

    Debug is resolved first because it changes how strictly the
    storage secret is enforced.
    """
    debug = _read_bool("DEBUG", default=False)

    return Settings(
        # --- Backend API --------------------------------------
        api_base_url=_read_base_url("API_BASE_URL"),

        # --- Timeouts -----------------------------------------
        # The chat ceiling is high on purpose. A self-healed query
        # re-runs generation and the LLM judges once per retry, on
        # top of a possible cold start.
        timeout_chat=_read_int("API_TIMEOUT_CHAT", default=180, minimum=30, maximum=600),
        timeout_ingest=_read_int("API_TIMEOUT_INGEST", default=120, minimum=30, maximum=600),
        timeout_read=_read_int("API_TIMEOUT_READ", default=30, minimum=5, maximum=120),
        # Health must fail fast so a sleeping backend surfaces as a
        # cold-start banner rather than a hung request.
        timeout_health=_read_int("API_TIMEOUT_HEALTH", default=10, minimum=3, maximum=60),

        # --- Cold start ---------------------------------------
        cold_start_estimate=_read_int("COLD_START_ESTIMATE", default=90, minimum=10, maximum=300),
        warmup_on_load=_read_bool("WARMUP_ON_LOAD", default=True),

        # --- Evaluation fetch ---------------------------------
        # EvaluationLogger.log() runs synchronously inside the
        # pipeline, so the row is committed before /chat/query
        # returns. One retry covers a failed logger write; a
        # polling loop would be pure overhead.
        eval_fetch_retries=_read_int("EVAL_FETCH_RETRIES", default=1, minimum=0, maximum=5),
        eval_retry_delay=_read_float("EVAL_RETRY_DELAY", default=1.5, minimum=0.1, maximum=10.0),

        # --- Health page --------------------------------------
        # Readiness opens a real Neon connection on every call, so
        # the floor here is deliberately not lower.
        health_poll_interval=_read_int("HEALTH_POLL_INTERVAL", default=15, minimum=5, maximum=300),

        # --- Uploads ------------------------------------------
        # The backend reads uploads fully into memory via
        # UploadFile.read(), so a client-side ceiling protects a
        # 512 MB free instance from an OOM kill.
        max_upload_mb=_read_int("MAX_UPLOAD_MB", default=25, minimum=1, maximum=200),

        # --- Session storage ----------------------------------
        storage_secret=_read_storage_secret("STORAGE_SECRET", debug=debug),

        # --- Server -------------------------------------------
        # Render injects PORT at runtime and it must be honoured,
        # or the health check fails and the deploy is unhealthy.
        port=_read_int("PORT", default=8080, minimum=1, maximum=65535),
        debug=debug,
    )


# ==========================================================
# Module-level singleton
# ==========================================================
# Built at import time so configuration errors surface during
# startup rather than on a user's first click.
settings: Final[Settings] = _build_settings()


# ==========================================================
# Allowed upload extensions
# ==========================================================
# Mirrors ALLOWED_EXTENSIONS in the backend's api/routers/documents.py
# exactly. Kept here rather than in constants.py because the client-side
# guard and the server-side guard must be reviewed together: if the
# backend list changes, this is the line that has to change with it.
#
# The backend answers 415 for anything outside this set. Checking first
# turns a confusing error into an immediate, specific message.
ALLOWED_UPLOAD_EXTENSIONS: Final[FrozenSet[str]] = frozenset({
    ".pdf", ".docx", ".pptx", ".txt", ".log",
    ".csv", ".md", ".markdown", ".html", ".htm",
})