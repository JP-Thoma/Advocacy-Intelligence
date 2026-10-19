import re
from pathlib import Path

import pytest

from advocacy_intel.ingestion.clean import clean_pages
from advocacy_intel.ingestion.text_checks import PageText

EXTRACTED = Path(__file__).parent.parent / "data" / "extracted"


BODY = [
    "alpha",
    "bravo",
    "charlie",
    "delta",
    "echo",
    "foxtrot",
    "golf",
    "hotel",
]  # unique, no digits


def pages(*texts):
    return [PageText(i, t) for i, t in enumerate(texts, 1)]


def squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


def is_subsequence(small: str, big: str) -> bool:
    it = iter(big)
    return all(ch in it for ch in small)


def assert_delete_only(raw_pages: list[PageText]) -> None:
    """D26: cleaned text is raw text with characters deleted, nothing inserted or reordered."""
    for raw, clean in zip(raw_pages, clean_pages(raw_pages), strict=True):
        assert raw.number == clean.number
        assert is_subsequence(squash(clean.text), squash(raw.text)), f"page {raw.number}"


def test_bullet_glyph_deleted_and_marked_as_structure():
    [page] = clean_pages(pages("•(cid:3) Cease evicting\nSyrian nationals."))
    assert page.paragraphs[0].text == "Cease evicting Syrian nationals."
    assert page.paragraphs[0].kind == "bullet"


def test_running_headers_removed_but_body_kept():
    ps = pages(
        *[f"{i} HUMAN RIGHTS WATCH | APRIL 2018\n{BODY[i]}\nmore {BODY[i]}" for i in range(8)]
    )
    cleaned = clean_pages(ps)
    assert all("HUMAN RIGHTS" not in c.text for c in cleaned)
    assert BODY[3] in cleaned[3].text


def test_footer_inside_a_list_is_removed_and_bullet_continues_across_pages():
    ps = pages(
        *[
            f"•(cid:3) Ensure that {BODY[i]} evictions do not\ntake place at {BODY[i]} night\n"
            f"and {BODY[i]} again\n{BODY[i]} one\n{BODY[i]} two\n{i} HUMAN RIGHTS WATCH"
            for i in range(8)
        ]
    )
    cleaned = clean_pages(ps)
    assert (
        cleaned[0]
        .paragraphs[0]
        .text.startswith("Ensure that alpha evictions do not take place at alpha night")
    )
    assert all("HUMAN RIGHTS" not in c.text for c in cleaned)


def test_glued_footnote_digits_deleted_decimals_kept():
    [page] = clean_pages(pages("•(cid:3) End the practice.12 Over 2.5 million people"))
    assert page.text == "End the practice. Over 2.5 million people"


def test_hyphenated_line_break_joined():
    [page] = clean_pages(pages("•(cid:3) Ensure that the investi-\ngation is prompt"))
    assert page.text == "Ensure that the investigation is prompt"


def test_hyphen_kept_when_next_line_not_lowercase():
    [page] = clean_pages(pages("•(cid:3) Follow the UN-\nHabitat guidance"))
    assert "UN- Habitat" in page.text


def test_actor_heading_detected_after_finished_sentence():
    [page] = clean_pages(
        pages(
            "To Lebanese Municipal Authorities\n•(cid:3) Cease evicting people.\nTo the Ministry of Defense"
        )
    )
    kinds = [p.kind for p in page.paragraphs]
    assert kinds == ["heading", "bullet", "heading"]


def test_section_title_is_its_own_heading_before_first_actor():
    [page] = clean_pages(
        pages("Recommendations\nTo Lebanese Authorities\n•(cid:3) Cease evicting.")
    )
    assert [(p.kind, p.text) for p in page.paragraphs][:2] == [
        ("heading", "Recommendations"),
        ("heading", "To Lebanese Authorities"),
    ]


def test_wrapped_line_starting_with_to_is_not_a_heading():
    [page] = clean_pages(pages("•(cid:3) Give access\nTo Syrian children in schools"))
    assert [p.kind for p in page.paragraphs] == ["bullet"]


def test_delete_only_invariant_on_synthetic_page():
    raw = pages(
        *[
            f"{i} HUMAN RIGHTS WATCH | APRIL 2018\nTo Lebanese Authorities\n"
            "•(cid:3) Cease evicting people.3 Give notice of evic-\ntion to everyone.\n"
            f"“TITLE” {i}"
            for i in range(8)
        ]
    )
    assert_delete_only(raw)


def _real_pages(path: Path) -> list[PageText]:
    parts = re.split(r"=== page (\d+) ===\n", path.read_text(encoding="utf-8"))
    return [PageText(int(n), body.rstrip("\n")) for n, body in zip(parts[1::2], parts[2::2])]


@pytest.mark.parametrize(
    "doc_id",
    [
        "201804_lebanon_evictionssyrianrefugees",
        "202110_lebanon_syrianrefugeereturns",
        "202409_lebanon_syrianrefugeepushbacks",
    ],
)
def test_delete_only_invariant_on_real_pages(doc_id):
    path = EXTRACTED / f"{doc_id}.txt"
    if not path.exists():
        pytest.skip("local HRW text is gitignored; run the M1 probe to create it")
    assert_delete_only(_real_pages(path))
