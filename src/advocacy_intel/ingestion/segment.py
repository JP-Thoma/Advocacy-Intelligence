"""Split the recommendations section of a cleaned report into numbered units (D38).

Pure code, no model. A unit is one bullet under one actor heading, and its text is copied from
the cleaned page, so it is verbatim by construction. The model later receives the units and
returns only unit IDs plus metadata; it never writes the quote.

The segmenter fails loudly: when it cannot find the section or has to guess, it says so in
`warnings` and `ended_by` instead of returning a quietly shorter list.
"""

from dataclasses import dataclass, field

from .clean import RECOMMENDATIONS_TITLE, CleanPage, Paragraph, ends_sentence

SEGMENTER_VERSION = "segment-v1"


@dataclass(frozen=True)
class Unit:
    unit_id: str
    text: str
    actor_raw: str | None  # the "To ..." heading exactly as written, None before the first one
    page: int  # PDF page where the unit starts
    end_page: int  # PDF page where it ends (differs when a bullet crosses a page break)


@dataclass(frozen=True)
class Segmentation:
    units: tuple[Unit, ...]
    section_start_page: int | None
    section_end_page: int | None
    ended_by: str | None  # first words of whatever stopped the section, for a human to check
    warnings: tuple[str, ...] = field(default=())

    @property
    def found(self) -> bool:
        return self.section_start_page is not None


def _flatten(pages: list[CleanPage]) -> list[tuple[int, bool, Paragraph]]:
    """(page, first_on_page, paragraph) in reading order."""
    return [(pg.number, i == 0, p) for pg in pages for i, p in enumerate(pg.paragraphs)]


def _find_starts(flat: list[tuple[int, bool, Paragraph]]) -> list[int]:
    """Indexes of 'Recommendations' headings that are followed by an actor heading.

    The follow-up test skips the table of contents and prose mentions.
    """
    starts = []
    for i, (_, _, p) in enumerate(flat[:-1]):
        nxt = flat[i + 1][2]
        if (
            p.kind == "heading"
            and RECOMMENDATIONS_TITLE.match(p.text)
            and nxt.kind == "heading"
            and nxt.text.lstrip().startswith("To ")
        ):
            starts.append(i)
    return starts


def segment(doc_id: str, pages: list[CleanPage]) -> Segmentation:
    flat = _flatten(pages)
    starts = _find_starts(flat)
    if not starts:
        return Segmentation((), None, None, None, ("no recommendations section found",))

    warnings: list[str] = []
    if len(starts) > 1:
        where = [flat[i][0] for i in starts]
        warnings.append(
            f"{len(starts)} candidate sections on pages {where}; only the first is read"
        )

    units: list[Unit] = []
    actor: str | None = None
    ended_by: str | None = None
    last_page = flat[starts[0]][0]

    for page, first_on_page, p in flat[starts[0] + 1 :]:
        last_page = page
        if p.kind == "heading":
            if p.text.lstrip().startswith("To "):
                actor = p.text
                continue
            ended_by = p.text[:80]
            break
        if p.kind == "bullet":
            units.append(Unit(f"{doc_id}-u{len(units) + 1:03d}", p.text, actor, page, page))
            continue
        # a plain-text paragraph: either the tail of a bullet cut by a page break, or the end
        last = units[-1] if units else None
        continues = (
            first_on_page
            and last is not None
            and last.end_page == page - 1
            and (not ends_sentence(last.text) or p.text[:1].islower())
        )
        if continues:
            units[-1] = Unit(last.unit_id, f"{last.text} {p.text}", last.actor_raw, last.page, page)
        else:
            ended_by = p.text[:80]
            break

    if ended_by is None:
        warnings.append("section ran to the end of the document without a closing heading")
    if not units:
        warnings.append("section found but no bullet units")
    section_end = units[-1].end_page if units else last_page
    return Segmentation(tuple(units), flat[starts[0]][0], section_end, ended_by, tuple(warnings))
