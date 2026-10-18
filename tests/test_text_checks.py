from advocacy_intel.ingestion.text_checks import (
    PageText,
    glued_footnotes,
    hyphen_breaks,
    low_text_pages,
    recommendation_headings,
    repeated_edge_lines,
)


def pages(*texts):
    return [PageText(i, t) for i, t in enumerate(texts, 1)]


def test_repeated_edge_lines_finds_running_header_with_changing_page_number():
    ps = pages(*[f"HUMAN RIGHTS WATCH\nbody {i}\nmore body\n{i}" for i in range(1, 9)])
    found = dict(repeated_edge_lines(ps))
    assert found["HUMAN RIGHTS WATCH"] == 8
    assert found["#"] == 8  # page numbers normalised to one pattern


def test_repeated_edge_lines_ignores_unique_lines():
    ps = pages("a\nb\nc\nd\ne\nf\ng", "h\ni\nj\nk\nl\nm\nn")
    assert repeated_edge_lines(ps) == []


def test_glued_footnotes_detects_fused_number():
    assert glued_footnotes("guarantee the independence.23 Parliament")
    assert not glued_footnotes("It cost 3.5 million in 2018.")


def test_hyphen_breaks_counts_split_words_only():
    assert hyphen_breaks("the investi-\ngation was") == 1
    assert hyphen_breaks("a well-\nKnown case") == 0  # next line is capitalised


def test_low_text_pages_flags_sparse_pages():
    ps = pages("x" * 500, "scan", "y" * 300)
    assert low_text_pages(ps) == [2]


def test_recommendation_heading_allows_roman_numeral_prefix_but_not_toc_lines():
    ps = pages(
        "XII. Recommendations\nTo the Government", "XII. Recommendations " + "." * 80 + " 119"
    )
    assert recommendation_headings(ps)["recommendations"] == [1]  # dotted TOC line is too long


def test_recommendation_headings_finds_section_and_actor_headings():
    ps = pages("intro text", "Recommendations\nTo the Lebanese Government\nAdopt a law.")
    found = recommendation_headings(ps)
    assert found["recommendations"] == [2]
    assert found["actor_headings"] == [2]
