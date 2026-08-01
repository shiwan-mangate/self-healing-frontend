from __future__ import annotations

import html
import re
from typing import Iterable, Optional

from api.models import Citation

_CITATION_PATTERN = re.compile(r"\[([0-9]+(?:\s*,\s*[0-9]+)*)\]")

_CODE_BLOCK_PATTERN = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_PATTERN = re.compile(r"`[^`\n]+`")

_APOLOGY_MARKERS: tuple[str, ...] = (
    "i apologize, but i do not have enough specific context",
    "i apologize, but i could not generate an answer",
    "i apologize, but i couldn't find any relevant information",
    "the retrieved evidence was too large to process",
    "i encountered an error while trying to synthesize",
)

_PLACEHOLDER_PREFIX = "\x00CIT"
_PLACEHOLDER_SUFFIX = "\x00"


def extract_citation_indices(text: str) -> list[int]:
    found: list[int] = []
    seen: set[int] = set()

    for match in _CITATION_PATTERN.finditer(text):
        for part in match.group(1).split(","):
            digits = part.strip()
            if not digits.isdigit():
                continue
            index = int(digits)
            if index not in seen:
                seen.add(index)
                found.append(index)

    return found


def build_citation_index(citations: Iterable[Citation]) -> dict[int, Citation]:
    index: dict[int, Citation] = {}
    for position, citation in enumerate(citations, start=1):
        key = citation.marker_index
        index[key if key is not None else position] = citation
    return index


def citation_tooltip(citation: Citation) -> str:
    parts: list[str] = [citation.display_name]
    location = citation.display_location
    if location:
        parts.append(location)
    parts.append(f"Relevance {citation.relevance_score:.2f}")
    return " · ".join(parts)


def _protected_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for pattern in (_CODE_BLOCK_PATTERN, _INLINE_CODE_PATTERN):
        spans.extend(match.span() for match in pattern.finditer(text))
    return spans


def _is_protected(position: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= position < end for start, end in spans)


def _citation_chip(index: int, citation: Optional[Citation]) -> str:
    tooltip = html.escape(citation_tooltip(citation), quote=True) if citation else "Source unavailable"
    known = "shr-cite" if citation else "shr-cite shr-cite-missing"
    return (
        f'<sup class="{known}" title="{tooltip}" data-citation="{index}">{index}</sup>'
    )


def annotate_citations(text: str, citations: Iterable[Citation]) -> str:
    index_map = build_citation_index(citations)
    spans = _protected_spans(text)

    def replace(match: re.Match[str]) -> str:
        if _is_protected(match.start(), spans):
            return match.group(0)

        chips: list[str] = []
        for part in match.group(1).split(","):
            digits = part.strip()
            if not digits.isdigit():
                return match.group(0)
            number = int(digits)
            chips.append(_citation_chip(number, index_map.get(number)))

        return "".join(chips)

    return _CITATION_PATTERN.sub(replace, text)


def strip_citations(text: str) -> str:
    spans = _protected_spans(text)

    def replace(match: re.Match[str]) -> str:
        if _is_protected(match.start(), spans):
            return match.group(0)
        return ""

    cleaned = _CITATION_PATTERN.sub(replace, text)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([.,;:!?])", r"\1", cleaned)
    return cleaned.strip()


def is_apology(text: str) -> bool:
    lowered = text.strip().lower()
    return any(lowered.startswith(marker) or marker in lowered for marker in _APOLOGY_MARKERS)


def normalize_answer(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def prepare_answer(text: str, citations: Iterable[Citation]) -> str:
    return annotate_citations(normalize_answer(text), citations)


def plain_text(text: str) -> str:
    stripped = strip_citations(normalize_answer(text))
    stripped = re.sub(r"```[a-zA-Z0-9_+-]*\n?", "", stripped)
    stripped = stripped.replace("```", "")
    stripped = re.sub(r"`([^`]+)`", r"\1", stripped)
    stripped = re.sub(r"^#{1,6}\s+", "", stripped, flags=re.MULTILINE)
    stripped = re.sub(r"\*\*([^*]+)\*\*", r"\1", stripped)
    stripped = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", stripped)
    stripped = re.sub(r"^\s*>\s?", "", stripped, flags=re.MULTILINE)
    stripped = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", stripped)
    return re.sub(r"\n{3,}", "\n\n", stripped).strip()


def preview(text: str, limit: int = 140) -> str:
    return " ".join(plain_text(text).split())[:limit].rstrip()


CITATION_CSS = """
.shr-cite {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 1.15em;
    height: 1.15em;
    margin: 0 0.12em;
    padding: 0 0.28em;
    border-radius: 0.35em;
    font-size: 0.68em;
    font-weight: 600;
    line-height: 1;
    vertical-align: super;
    cursor: help;
    background: var(--shr-cite-bg, rgba(74, 158, 255, 0.16));
    color: var(--shr-cite-fg, #4a9eff);
    border: 1px solid var(--shr-cite-border, rgba(74, 158, 255, 0.32));
    transition: background 120ms ease, transform 120ms ease;
}

.shr-cite:hover {
    background: var(--shr-cite-bg-hover, rgba(74, 158, 255, 0.28));
    transform: translateY(-1px);
}

.shr-cite-missing {
    background: rgba(138, 147, 166, 0.16);
    color: #8a93a6;
    border-color: rgba(138, 147, 166, 0.32);
}
"""