from datetime import date

import pytest

from advocacy_intel.indexing.schema import (
    EMBEDDING_DIMENSIONS,
    VECTOR_FIELD,
    document_id_of,
    exclude_documents_filter,
    index_definition,
    to_document,
)
from advocacy_intel.models import Recommendation

REC = Recommendation(
    recommendation_id="202409_lebanon_x-u007",
    recommendation_text="Halt expulsions.",
    source_context="To the Government",
    target_actor_raw="To the Government",
    topic=["expulsion"],
    publication_date=date(2024, 9, 4),
    document_title="A Report",
    document_type="report",
    source_url="https://www.hrw.org/x",
    source_page=96,
    source_end_page=96,
)


def fields_by_name():
    return {f["name"]: f for f in index_definition()["fields"]}


def test_exactly_one_key_and_one_vector_field_wired_to_a_profile():
    fields = fields_by_name()
    assert [n for n, f in fields.items() if f.get("key")] == ["id"]
    vec = fields[VECTOR_FIELD]
    assert vec["dimensions"] == EMBEDDING_DIMENSIONS
    profiles = {p["name"] for p in index_definition()["vectorSearch"]["profiles"]}
    assert vec["vectorSearchProfile"] in profiles
    assert sum("dimensions" in f for f in fields.values()) == 1


def test_document_id_is_filterable_for_held_out_evaluation():
    assert fields_by_name()["document_id"]["filterable"]


def test_every_document_key_is_a_defined_field():
    doc = to_document(REC, [0.0] * EMBEDDING_DIMENSIONS)
    assert set(doc) == set(fields_by_name())


def test_document_keeps_the_verbatim_text_and_converts_the_date():
    doc = to_document(REC, [0.0] * EMBEDDING_DIMENSIONS)
    assert doc["recommendation_text"] == "Halt expulsions."
    assert doc["publication_date"] == "2024-09-04T00:00:00Z"
    assert doc["document_id"] == "202409_lebanon_x"


def test_wrong_vector_size_is_rejected_not_silently_indexed():
    with pytest.raises(ValueError, match="3072"):
        to_document(REC, [0.0] * 10)


def test_unlabelled_record_maps_to_nulls_not_invented_values():
    bare = REC.model_copy(update={"action_requested": None, "topic": []})
    doc = to_document(bare, [0.0] * EMBEDDING_DIMENSIONS)
    assert doc["action_requested"] is None and doc["topic"] == []


def test_document_id_parsing():
    assert document_id_of("201804_lebanon_evictions-u029") == "201804_lebanon_evictions"


def test_exclude_filter():
    assert exclude_documents_filter([]) is None
    assert exclude_documents_filter(["a", "b"]) == "document_id ne 'a' and document_id ne 'b'"
    with pytest.raises(ValueError):
        exclude_documents_filter(["a' or true or 'b"])
