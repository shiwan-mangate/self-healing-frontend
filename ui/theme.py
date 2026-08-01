from __future__ import annotations

from typing import Final

from nicegui import ui

from app import state
from utils.markdown import CITATION_CSS


PRIMARY: Final[str] = "#4a9eff"
SECONDARY: Final[str] = "#8b7cf6"
ACCENT: Final[str] = "#22c9a8"
POSITIVE: Final[str] = "#22c9a8"
WARNING: Final[str] = "#f0a848"
NEGATIVE: Final[str] = "#f0605f"
INFO: Final[str] = "#3fb9d4"
MUTED: Final[str] = "#8a93a6"

DARK_BG: Final[str] = "#0d1117"
DARK_SURFACE: Final[str] = "#151b24"
DARK_SURFACE_ALT: Final[str] = "#1c232e"
DARK_BORDER: Final[str] = "#252d3a"
DARK_TEXT: Final[str] = "#e4e8ef"
DARK_TEXT_MUTED: Final[str] = "#8a93a6"

LIGHT_BG: Final[str] = "#f6f8fb"
LIGHT_SURFACE: Final[str] = "#ffffff"
LIGHT_SURFACE_ALT: Final[str] = "#eef2f7"
LIGHT_BORDER: Final[str] = "#dde3ec"
LIGHT_TEXT: Final[str] = "#1a2029"
LIGHT_TEXT_MUTED: Final[str] = "#5b6675"

HEADER_HEIGHT: Final[int] = 52
FOOTER_HEIGHT: Final[int] = 30
SIDEBAR_WIDTH: Final[int] = 260
CONTENT_MAX_WIDTH: Final[int] = 1180
CHAT_MAX_WIDTH: Final[int] = 880


_FONT_LINK: Final[str] = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?'
    'family=Inter:wght@400;500;600;700&'
    'family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">'
)


_BASE_CSS: Final[str] = """
*, *::before, *::after {
    box-sizing: border-box;
}

html, body {
    max-width: 100%;
    overflow-x: hidden;
    margin: 0;
    padding: 0;
}

:root {
    --shr-radius: 12px;
    --shr-radius-sm: 8px;
    --shr-radius-lg: 16px;
    --shr-font: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    --shr-mono: 'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace;
    --shr-transition: 160ms cubic-bezier(0.4, 0, 0.2, 1);
    --shr-header-h: 52px;
    --shr-footer-h: 30px;
}

body {
    font-family: var(--shr-font);
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    letter-spacing: -0.006em;
}

.body--dark {
    --shr-bg: #0d1117;
    --shr-surface: #151b24;
    --shr-surface-alt: #1c232e;
    --shr-surface-hover: #212a36;
    --shr-border: #252d3a;
    --shr-border-strong: #333d4d;
    --shr-text: #e4e8ef;
    --shr-text-muted: #8a93a6;
    --shr-shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
    --shr-shadow-lg: 0 8px 28px rgba(0, 0, 0, 0.5);
    --shr-cite-bg: rgba(74, 158, 255, 0.16);
    --shr-cite-fg: #6cb2ff;
    --shr-cite-border: rgba(74, 158, 255, 0.34);
    --shr-cite-bg-hover: rgba(74, 158, 255, 0.28);
    --shr-user-bubble: #1e3a5f;
    --shr-user-bubble-text: #dceaff;
}

.body--light {
    --shr-bg: #f6f8fb;
    --shr-surface: #ffffff;
    --shr-surface-alt: #eef2f7;
    --shr-surface-hover: #e6ecf4;
    --shr-border: #dde3ec;
    --shr-border-strong: #c6d0de;
    --shr-text: #1a2029;
    --shr-text-muted: #5b6675;
    --shr-shadow: 0 1px 2px rgba(16, 24, 40, 0.06);
    --shr-shadow-lg: 0 8px 24px rgba(16, 24, 40, 0.10);
    --shr-cite-bg: rgba(37, 122, 219, 0.10);
    --shr-cite-fg: #1e6fc4;
    --shr-cite-border: rgba(37, 122, 219, 0.26);
    --shr-cite-bg-hover: rgba(37, 122, 219, 0.18);
    --shr-user-bubble: #e3edfb;
    --shr-user-bubble-text: #12385f;
}

.body--dark, .body--light { background: var(--shr-bg); color: var(--shr-text); }

.nicegui-content {
    padding: 0 !important;
    margin: 0 !important;
    gap: 0 !important;
    width: 100%;
    max-width: 100%;
    overflow-x: hidden;
}

.q-page-container {
    width: 100%;
    max-width: 100%;
    overflow-x: hidden;
    padding-left: 0 !important;
    padding-right: 0 !important;
}

.q-page {
    width: 100%;
    max-width: 100%;
    overflow-x: hidden;
}

.q-layout { overflow-x: hidden; }

.shr-fill {
    width: 100%;
    max-width: 100%;
    min-width: 0;
}

.shr-flex-min { min-width: 0; min-height: 0; }

.shr-surface {
    background: var(--shr-surface);
    border: 1px solid var(--shr-border);
    border-radius: var(--shr-radius);
    max-width: 100%;
    min-width: 0;
    overflow-wrap: anywhere;
}

.shr-surface-alt {
    background: var(--shr-surface-alt);
    border: 1px solid var(--shr-border);
    border-radius: var(--shr-radius);
    max-width: 100%;
    min-width: 0;
    overflow-wrap: anywhere;
}

.shr-muted { color: var(--shr-text-muted); }

.shr-mono {
    font-family: var(--shr-mono);
    font-size: 0.82em;
    letter-spacing: -0.01em;
    overflow-wrap: anywhere;
}

.shr-divider { height: 1px; background: var(--shr-border); border: none; }

.shr-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.32rem;
    padding: 0.16rem 0.52rem;
    border-radius: 999px;
    font-size: 0.72rem;
    font-weight: 600;
    line-height: 1.5;
    white-space: nowrap;
}

.shr-session-panel { display: flex !important; }

@media (max-width: 767px) {
    .shr-session-panel { display: none !important; }
}

.shr-bubble-user {
    background: var(--shr-user-bubble);
    color: var(--shr-user-bubble-text);
    border-radius: var(--shr-radius-lg) var(--shr-radius-sm) var(--shr-radius-lg) var(--shr-radius-lg);
    max-width: 100%;
    overflow-wrap: anywhere;
}

.shr-bubble-assistant {
    background: var(--shr-surface);
    border: 1px solid var(--shr-border);
    border-radius: var(--shr-radius-sm) var(--shr-radius-lg) var(--shr-radius-lg) var(--shr-radius-lg);
    max-width: 100%;
    min-width: 0;
    overflow-wrap: anywhere;
}

.shr-answer {
    line-height: 1.68;
    font-size: 0.94rem;
    max-width: 100%;
    overflow-wrap: anywhere;
}
.shr-answer p { margin: 0 0 0.85em 0; }
.shr-answer p:last-child { margin-bottom: 0; }
.shr-answer ul, .shr-answer ol { margin: 0.5em 0 0.85em 0; padding-left: 1.4em; }
.shr-answer li { margin-bottom: 0.32em; }
.shr-answer h1, .shr-answer h2, .shr-answer h3 {
    margin: 1.1em 0 0.5em 0;
    font-weight: 650;
    line-height: 1.3;
}
.shr-answer h1 { font-size: 1.22rem; }
.shr-answer h2 { font-size: 1.10rem; }
.shr-answer h3 { font-size: 1.00rem; }
.shr-answer code {
    font-family: var(--shr-mono);
    font-size: 0.86em;
    padding: 0.12em 0.36em;
    border-radius: 5px;
    background: var(--shr-surface-alt);
    border: 1px solid var(--shr-border);
    overflow-wrap: anywhere;
}
.shr-answer pre {
    background: var(--shr-surface-alt);
    border: 1px solid var(--shr-border);
    border-radius: var(--shr-radius-sm);
    padding: 0.85rem 1rem;
    overflow-x: auto;
    max-width: 100%;
    margin: 0.7em 0;
}
.shr-answer pre code {
    background: none;
    border: none;
    padding: 0;
    overflow-wrap: normal;
    white-space: pre;
}
.shr-answer blockquote {
    margin: 0.7em 0;
    padding: 0.4em 0 0.4em 0.9em;
    border-left: 3px solid var(--shr-border-strong);
    color: var(--shr-text-muted);
}
.shr-answer table {
    width: 100%;
    border-collapse: collapse;
    margin: 0.7em 0;
    font-size: 0.88em;
    display: block;
    overflow-x: auto;
}
.shr-answer th, .shr-answer td {
    border: 1px solid var(--shr-border);
    padding: 0.45em 0.7em;
    text-align: left;
}
.shr-answer th { background: var(--shr-surface-alt); font-weight: 600; }
.shr-answer a { color: var(--shr-cite-fg); text-decoration: none; overflow-wrap: anywhere; }
.shr-answer a:hover { text-decoration: underline; }

.shr-timeline-line {
    width: 2px;
    background: var(--shr-border-strong);
    border-radius: 1px;
}

.shr-hover-lift { transition: transform var(--shr-transition), box-shadow var(--shr-transition); }
.shr-hover-lift:hover { transform: translateY(-1px); box-shadow: var(--shr-shadow-lg); }

.shr-clickable { cursor: pointer; transition: background var(--shr-transition); }
.shr-clickable:hover { background: var(--shr-surface-hover); }

.shr-fade-in { animation: shrFadeIn 260ms ease-out; }
@keyframes shrFadeIn {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
}

.shr-pulse { animation: shrPulse 1.6s ease-in-out infinite; }
@keyframes shrPulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.45; }
}

.shr-scroll::-webkit-scrollbar { width: 9px; height: 9px; }
.shr-scroll::-webkit-scrollbar-track { background: transparent; }
.shr-scroll::-webkit-scrollbar-thumb {
    background: var(--shr-border-strong);
    border-radius: 5px;
}
.shr-scroll::-webkit-scrollbar-thumb:hover { background: var(--shr-text-muted); }

.q-drawer, .q-header, .q-footer { background: var(--shr-surface) !important; }
.q-drawer { border-right: 1px solid var(--shr-border) !important; }
.q-header { border-bottom: 1px solid var(--shr-border) !important; }
.q-footer { border-top: 1px solid var(--shr-border) !important; }

.q-expansion-item { max-width: 100%; }
.q-expansion-item__container > .q-item { border-radius: var(--shr-radius-sm); }
.q-expansion-item__content { max-width: 100%; overflow-x: hidden; }

.q-field--outlined .q-field__control { border-radius: var(--shr-radius-sm); }

.q-uploader {
    width: 100% !important;
    max-width: 100% !important;
    background: var(--shr-surface-alt) !important;
    border: 1px solid var(--shr-border) !important;
    border-radius: var(--shr-radius-sm) !important;
    box-shadow: none !important;
}
.q-uploader__header { background: transparent !important; }
.q-uploader__list { display: none !important; }
.q-uploader__header-content { padding: 6px 10px !important; }
.q-uploader__title { font-size: 0.82rem !important; font-weight: 500 !important; }
.q-uploader__subtitle { display: none !important; }

.q-scrollarea { max-width: 100%; }
.q-scrollarea__content { max-width: 100%; }

.ellipsis { min-width: 0; }
"""


_dark_mode_element: ui.dark_mode | None = None


def install() -> None:
    ui.add_head_html(_FONT_LINK)
    ui.add_css(_BASE_CSS)
    ui.add_css(CITATION_CSS)

    ui.colors(
        primary=PRIMARY,
        secondary=SECONDARY,
        accent=ACCENT,
        positive=POSITIVE,
        negative=NEGATIVE,
        warning=WARNING,
        info=INFO,
        dark=DARK_BG,
        dark_page=DARK_BG,
    )


def apply() -> ui.dark_mode:
    global _dark_mode_element
    install()
    _dark_mode_element = ui.dark_mode(value=state.is_dark_mode())
    return _dark_mode_element


def set_dark(enabled: bool) -> None:
    state.set_dark_mode(enabled)
    if _dark_mode_element is not None:
        _dark_mode_element.value = enabled


def toggle_dark() -> bool:
    enabled = state.toggle_dark_mode()
    if _dark_mode_element is not None:
        _dark_mode_element.value = enabled
    return enabled


def surface_classes(alt: bool = False, hover: bool = False) -> str:
    base = "shr-surface-alt" if alt else "shr-surface"
    return f"{base} shr-hover-lift" if hover else base


def chip_style(color: str, subtle: bool = True) -> str:
    if subtle:
        return f"background: {color}22; color: {color}; border: 1px solid {color}44;"
    return f"background: {color}; color: #ffffff;"


def text_style(color: str, weight: int = 600) -> str:
    return f"color: {color}; font-weight: {weight};"


def accent_border(color: str, width: int = 3) -> str:
    return f"border-left: {width}px solid {color};"