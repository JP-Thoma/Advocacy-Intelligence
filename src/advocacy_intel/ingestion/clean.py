"""Deterministic, versioned cleaning of extracted PDF page text (D26).

Design rule, enforced by tests: cleaning may only DELETE or JOIN characters. It never inserts,
reorders or substitutes words, so cleaned text is always traceable to the raw page text.
Whitespace is the one thing that may change (line breaks become spaces or paragraph breaks).

Bullet glyphs are deleted, so the fact that a paragraph was a bullet is kept as structure
(`Paragraph.kind`), not as text. The segmenter and verifier work on this structure.
"""

import re
from dataclasses import dataclass
from typing import Literal

from .text_checks import PageText, repeated_edge_lines

CLEANING_VERSION = "clean-v1"

Kind = Literal["bullet", "heading", "text"]

_DIGITS = re.compile(r"\d+")
_BULLET = re.compile(r"^\s*•\s*(?:\(cid:\d+\))?\s*")
_CID = re.compile(r"\(cid:\d+\)")
# footnote number fused to the preceding word: "planning.1" -> "planning."
_GLUED_FOOTNOTE = re.compile(r"(?<=[a-z][.,;:])\d{1,3}(?=\s|$)")
_HYPHEN_END = re.compile(r"[a-z]-$")
_ACTOR_HEADING = re.compile(r"^\s*To\s+(the\s+)?[A-Z]")
# a line that is only the section title: "Recommendations", "XII. Key Recommendations"
RECOMMENDATIONS_TITLE = re.compile(
    r"^\s*(?:[IVXLC]+\.|\d+\.)?\s*(key\s+)?recommendations?\s*$", re.IGNORECASE
)
# titles that normally follow the recommendations; kept as their own paragraph so the
# segmenter can see where the section ends instead of finding them glued to the last bullet
_SECTION_END_TITLE = re.compile(
    r"^\s*(?:acknowledg\w*|methodology|terminology|background|glossary|endnotes?"
    r"|(?:annex|appendix)\b.{0,70})\s*$",
    re.IGNORECASE,
)
_SENTENCE_END = re.compile(r"[.;:!?)\"”’]$")


def ends_sentence(text: str) -> bool:
    return bool(_SENTENCE_END.search(text.strip()))


@dataclass(frozen=True)
class Paragraph:
    text: str
    kind: Kind


@dataclass(frozen=True)
class CleanPage:
    number: int  # 1-based PDF page number, same as the raw page
    paragraphs: tuple[Paragraph, ...]

    @property
    def text(self) -> str:
        return "\n".join(p.text for p in self.paragraphs)


def _is_actor_heading(line: str, previous: Paragraph | None) -> bool:
    """'To the Ministry of X' on its own line, after a finished sentence or heading.

    The previous-paragraph test stops a wrapped line that happens to start with 'To Lebanon'
    from being read as a heading.
    """
    if not _ACTOR_HEADING.match(line) or len(line) >= 80:
        return False
    return previous is None or previous.kind == "heading" or ends_sentence(previous.text)


def _drop_running_lines(page: PageText, running: set[str], edge: int = 3) -> list[str]:
    """Raw lines of the page minus running headers/footers (edge lines only)."""
    lines = [ln for ln in page.text.splitlines() if ln.strip()]
    last = len(lines) - 1
    keep = []
    for i, ln in enumerate(lines):
        near_edge = i < edge or i > last - edge
        if near_edge and _DIGITS.sub("#", ln.strip()) in running:
            continue
        keep.append(ln)
    return keep


def clean_pages(pages: list[PageText]) -> list[CleanPage]:
    """Clean a whole document. Running headers are detected across all pages."""
    running = {ln for ln, _ in repeated_edge_lines(pages)}
    return [_clean_page(p, running) for p in pages]


def _clean_page(page: PageText, running: set[str]) -> CleanPage:
    paras: list[Paragraph] = []
    join_next = False  # previous line ended in a hyphenated word break

    for raw in _drop_running_lines(page, running):
        line = _GLUED_FOOTNOTE.sub("", raw).strip()
        bullet = _BULLET.match(line)
        if bullet:
            line = line[bullet.end() :]
        line = _CID.sub("", line).strip()  # stray glyphs outside the bullet position
        if not line:
            continue

        previous = paras[-1] if paras else None
        if join_next and previous is not None and line[:1].islower():
            # delete the hyphen, join without a space; the join keeps the paragraph kind
            paras[-1] = Paragraph(previous.text[:-1] + line, previous.kind)
        elif bullet:
            paras.append(Paragraph(line, "bullet"))
        elif (
            RECOMMENDATIONS_TITLE.match(line)
            or _SECTION_END_TITLE.match(line)
            or _is_actor_heading(line, previous)
        ):
            paras.append(Paragraph(line, "heading"))
        elif previous is not None and previous.kind != "heading":
            paras[-1] = Paragraph(previous.text + " " + line, previous.kind)
        else:
            paras.append(Paragraph(line, "text"))

        join_next = bool(_HYPHEN_END.search(paras[-1].text))

    return CleanPage(page.number, tuple(paras))
