"""Split pasted text into separate draft recommendations.

Deterministic heuristics only (numbering, bullets, blank lines, line breaks). A semantic,
model-assisted split is a later option; keep this function's contract (text in, list of
recommendation strings out) so it can be swapped without touching the UI.
"""

import re

MAX_RECOMMENDATIONS = 25
MIN_PREFACE_CHARS = 25

# "1." / "2)" at a line start, or glued after a sentence end ("independence.2. Parliament").
_NUMBER_MARK = re.compile(
    r"(?:(?<=^)|(?<=\n)|(?<=[.!?”\"')])\s*)(\d{1,2})[.)]\s*(?=[A-Z“\"'(\[])",
)
_BULLET = re.compile(r"^\s*[-–•*▪●○]\s+")
_TERMINAL = re.compile(r"[.!?:;”\"')]$")


def _clean(text: str) -> str:
    return " ".join(text.split())


def _split_numbered(text: str) -> list[str] | None:
    """Accept numbering only when it counts 1, 2, 3... in order; this avoids splitting on
    'Article 2.1', '1.5 million' or an unrelated number inside a sentence."""
    marks = []
    expected = 1
    for m in _NUMBER_MARK.finditer(text):
        if int(m.group(1)) == expected:
            marks.append(m)
            expected += 1
    if len(marks) < 2:
        return None
    parts = [text[marks[i].end() : marks[i + 1].start()] for i in range(len(marks) - 1)]
    parts.append(text[marks[-1].end() :])
    preface = _clean(text[: marks[0].start()])
    if len(preface) >= MIN_PREFACE_CHARS and not preface.endswith(":"):
        parts.insert(0, preface)
    return parts


def _split_lines(text: str) -> list[str]:
    """Blank lines separate recommendations; bullets start a new one; otherwise a line break
    starts a new one unless the previous line is clearly unfinished (wrapped text)."""
    out: list[str] = []
    current: list[str] = []

    def flush() -> None:
        if current:
            out.append(" ".join(current))
            current.clear()

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        bullet = _BULLET.match(line)
        if bullet:
            flush()
            line = line[bullet.end() :]
        elif current and not _TERMINAL.search(current[-1]) and line[:1].islower():
            pass  # wrapped continuation of the previous line
        else:
            flush()
        current.append(line)
    flush()
    return out


def split_recommendations(text: str) -> tuple[list[str], bool]:
    """Return (recommendations, truncated)."""
    text = text.strip()
    if not text:
        return [], False
    parts = _split_numbered(text)
    if parts is None:
        parts = _split_lines(text)
    cleaned = [c for c in (_clean(p) for p in parts) if c]
    return cleaned[:MAX_RECOMMENDATIONS], len(cleaned) > MAX_RECOMMENDATIONS
