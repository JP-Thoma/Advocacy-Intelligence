import pytest

from advocacy_intel.indexing.fallback import Entry, cosine, top_k

ENTRIES = [
    Entry("docA-u001", [1.0, 0.0]),
    Entry("docA-u002", [0.0, 1.0]),
    Entry("docB-u001", [0.9, 0.1]),
]


def test_cosine_basics():
    assert cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert cosine([2, 0], [5, 0]) == pytest.approx(1.0)  # length does not matter, direction does
    assert cosine([0, 0], [1, 1]) == 0.0


def test_mismatched_sizes_raise():
    with pytest.raises(ValueError):
        cosine([1, 0], [1, 0, 0])


def test_top_k_orders_by_similarity():
    assert [i for i, _ in top_k([1.0, 0.0], ENTRIES, k=2)] == ["docA-u001", "docB-u001"]


def test_held_out_document_is_excluded():
    got = [i for i, _ in top_k([1.0, 0.0], ENTRIES, k=5, exclude_documents=["docA"])]
    assert got == ["docB-u001"]


def test_ties_are_broken_by_id():
    tied = [Entry("b-u001", [1.0, 0.0]), Entry("a-u001", [1.0, 0.0])]
    assert [i for i, _ in top_k([1.0, 0.0], tied)] == ["a-u001", "b-u001"]
