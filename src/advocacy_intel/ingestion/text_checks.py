"""Pure heuristics for spotting PDF text-extraction problems (M1).

No I/O and no PDF library here, so every check is unit-testable with plain strings.
All checks are heuristics that surface candidates for a human to inspect; none is proof.
"""

import re
from collections import Counter
from dataclasses import dataclass


@dataclass(frozen=True)
class PageText:
    number: int  # 1-based PDF page number
    text: str


_DIGITS = re.compile(r"\d+")
# punctuation followed directly by 1-3 digits then whitespace/end: "independence.23 "
_GLUED_FOOTNOTE = re.compile(r"(?<=[a-z])[.,;:]\d{1,3}(?=\s|$)")
_HYPHEN_BREAK = re.compile(r"[a-z]-$")
# optional section numbering such as "XII." or "7." before the heading text
_REC_HEADING = re.compile(r"^\s*(?:[IVXLC]+\.|\d+\.)?\s*(key\s+)?recommendations?\b", re.IGNORECASE)
_ACTOR_HEADING = re.compile(r"^\s*to\s+(the\s+)?[A-Z]", re.IGNORECASE)


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def repeated_edge_lines(
    pages: list[PageText], edge: int = 3, min_share: float = 0.3
) -> list[tuple[str, int]]:
    """Lines near the top/bottom of many pages: probable running headers and footers.

    Digits are normalised so 'Page 12' and 'Page 13' count as the same line.
    """
    counts: Counter[str] = Counter()
    for p in pages:
        ls = _lines(p.text)
        seen = {_DIGITS.sub("#", ln) for ln in ls[:edge] + ls[-edge:]}
        counts.update(seen)
    threshold = max(2, int(len(pages) * min_share))
    return [(ln, n) for ln, n in counts.most_common() if n >= threshold]


def glued_footnotes(text: str) -> list[str]:
    """Snippets where a footnote number appears fused to the preceding word."""
    return [text[max(0, m.start() - 25) : m.end() + 5].replace("\n", " ") for m in _GLUED_FOOTNOTE.finditer(text)]


def hyphen_breaks(text: str) -> int:
    """Count lines ending in 'letter-' followed by a lowercase-starting line."""
    ls = _lines(text)
    return sum(
        1 for a, b in zip(ls, ls[1:], strict=False) if _HYPHEN_BREAK.search(a) and b[:1].islower()
    )


def low_text_pages(pages: list[PageText], min_chars: int = 200) -> list[int]:
    """Pages with very little text: scans, full-page images or sparse layouts."""
    return [p.number for p in pages if len(p.text.strip()) < min_chars]


def recommendation_headings(pages: list[PageText]) -> dict[str, list[int]]:
    """Pages where a 'Recommendations' heading or 'To the ...' actor heading appears."""
    found: dict[str, list[int]] = {"recommendations": [], "actor_headings": []}
    for p in pages:
        for ln in _lines(p.text):
            if _REC_HEADING.match(ln) and len(ln) < 60:
                found["recommendations"].append(p.number)
            elif _ACTOR_HEADING.match(ln) and len(ln) < 80:
                found["actor_headings"].append(p.number)
    return {k: sorted(set(v)) for k, v in found.items()}
