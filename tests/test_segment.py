import re
from pathlib import Path

import pytest

from advocacy_intel.ingestion.clean import clean_pages
from advocacy_intel.ingestion.segment import segment
from advocacy_intel.ingestion.text_checks import PageText

EXTRACTED = Path(__file__).parent.parent / "data" / "extracted"


def run(*texts):
    pages = [PageText(i, t) for i, t in enumerate(texts, 1)]
    return segment("doc", clean_pages(pages))


def test_units_carry_actor_page_and_stable_ids():
    seg = run(
        "Recommendations\nTo the Government\n•(cid:3) Halt expulsions.\n•(cid:3) Allow UNHCR access.\n"
        "To the EU\n•(cid:3) Press for change.\nAcknowledgments\nThanks."
    )
    assert [u.unit_id for u in seg.units] == ["doc-u001", "doc-u002", "doc-u003"]
    assert [u.actor_raw for u in seg.units] == ["To the Government"] * 2 + ["To the EU"]
    assert seg.units[0].text == "Halt expulsions."
    assert seg.ended_by == "Acknowledgments"
    assert seg.warnings == ()


def test_bullet_cut_by_page_break_is_merged_and_spans_two_pages():
    seg = run(
        "Recommendations\nTo the Government\n•(cid:3) Ensure that people are given the",
        "chance to challenge the decision in court.\n•(cid:3) Halt expulsions.\nAnnex I: Letter",
    )
    assert (
        seg.units[0].text
        == "Ensure that people are given the chance to challenge the decision in court."
    )
    assert (seg.units[0].page, seg.units[0].end_page) == (1, 2)
    assert len(seg.units) == 2


def test_text_after_a_finished_bullet_ends_the_section_and_is_reported():
    seg = run(
        "Recommendations\nTo the Government\n•(cid:3) Halt expulsions.",
        "Some unrelated prose starts here and runs on.",
    )
    assert len(seg.units) == 1
    assert seg.ended_by.startswith("Some unrelated prose")


def test_table_of_contents_entry_is_not_a_section():
    seg = run("Recommendations ........ 12\nMethodology ........ 14")
    assert not seg.found
    assert seg.warnings == ("no recommendations section found",)


def test_second_candidate_section_is_flagged_not_silently_dropped():
    filler = [f"{w} filler page\n{w} text here\n{w} more\n{w} again" for w in "abcdefgh"]
    seg = run(
        "Recommendations\nTo the Government\n•(cid:3) Halt expulsions.\nMethodology\nx",
        *filler,
        "Recommendations\nTo the EU\n•(cid:3) Press.\nAcknowledgments",
    )
    assert any("2 candidate sections" in w for w in seg.warnings)
    assert len(seg.units) == 1


# Independent cross-check on real reports: unit count equals the number of bullet glyphs
# in the raw text of the recommendations pages (counted without the cleaner or segmenter).
REAL_COUNTS = {
    "201804_lebanon_evictionssyrianrefugees": 29,
    "202110_lebanon_syrianrefugeereturns": 43,
    "202409_lebanon_syrianrefugeepushbacks": 33,
}


@pytest.mark.parametrize(("doc_id", "expected"), REAL_COUNTS.items())
def test_real_report_unit_count_matches_raw_bullet_glyphs(doc_id, expected):
    path = EXTRACTED / f"{doc_id}.txt"
    if not path.exists():
        pytest.skip("local HRW text is gitignored; run the M1 probe to create it")
    parts = re.split(r"=== page (\d+) ===\n", path.read_text(encoding="utf-8"))
    pages = [PageText(int(n), b.rstrip("\n")) for n, b in zip(parts[1::2], parts[2::2])]
    seg = segment(doc_id, clean_pages(pages))
    raw = sum(
        p.text.count("•")
        for p in pages
        if seg.section_start_page <= p.number <= seg.section_end_page
    )
    assert seg.warnings == ()
    assert len(seg.units) == raw == expected
