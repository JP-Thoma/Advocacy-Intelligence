"""Azure AI Search index definition and record -> document mapping (D10, D37).

Pure data, no SDK import, so it is unit-tested in CI. `service.py` turns it into SDK objects.
The index is DERIVED: records in Blob are the system of record, and this index can be dropped
and rebuilt from them without re-running extraction. The version in the name marks the shape.

Choices, each with a reason:
- One index, one vector field (thursday-plan): hybrid = vector similarity + keyword (BM25).
- Vectors are computed in our code, not by an index-side vectorizer: one visible embedding path
  that is also reused for the draft at query time, and the fallback needs no Search service.
- HNSW with cosine. At ~100 vectors an exact scan would be as fast; HNSW is kept because it is
  what the 100k-document answer needs, and efSearch is high enough to behave near-exactly.
- No semantic ranker (separate paid feature, cut from scope).
- `document_id` is filterable so a held-out report can be excluded from its own evaluation.
"""

from datetime import date
from typing import Any

from advocacy_intel.models import Recommendation

INDEX_NAME = "recommendations-v1"
VECTOR_FIELD = "content_vector"
VECTOR_PROFILE = "hnsw-cosine"
VECTOR_ALGORITHM = "hnsw-config"
EMBEDDING_DIMENSIONS = 3072  # text-embedding-3-large (D34); a different model changes this

_STRING = "Edm.String"
_STRINGS = "Collection(Edm.String)"


def _field(name: str, type_: str, **flags: Any) -> dict[str, Any]:
    return {"name": name, "type": type_, **flags}


def index_definition(dimensions: int = EMBEDDING_DIMENSIONS) -> dict[str, Any]:
    """The index in the shape of the Search REST API (also what the docs and portal show)."""
    return {
        "name": INDEX_NAME,
        "fields": [
            _field("id", _STRING, key=True, filterable=True),
            # keyword side of hybrid search: English stemming so "expelling" matches "expulsion"
            _field("recommendation_text", _STRING, searchable=True, analyzer="en.microsoft"),
            _field("target_actor_raw", _STRING, searchable=True, filterable=True),
            _field("action_requested", _STRING, searchable=True),  # model-generated; may be null
            _field("topic", _STRINGS, searchable=True, filterable=True, facetable=True),
            _field("document_id", _STRING, filterable=True),
            _field("document_title", _STRING),
            _field("publication_date", "Edm.DateTimeOffset", filterable=True, sortable=True),
            _field("source_url", _STRING),
            _field("source_page", "Edm.Int32", filterable=True),
            _field("source_end_page", "Edm.Int32"),
            _field(
                VECTOR_FIELD,
                "Collection(Edm.Single)",
                searchable=True,
                retrievable=False,  # large and never shown; saves response size
                dimensions=dimensions,
                vectorSearchProfile=VECTOR_PROFILE,
            ),
        ],
        "vectorSearch": {
            "algorithms": [
                {
                    "name": VECTOR_ALGORITHM,
                    "kind": "hnsw",
                    "hnswParameters": {
                        "metric": "cosine",
                        "m": 4,
                        "efConstruction": 400,
                        "efSearch": 500,
                    },
                }
            ],
            "profiles": [{"name": VECTOR_PROFILE, "algorithm": VECTOR_ALGORITHM}],
        },
    }


def document_id_of(recommendation_id: str) -> str:
    """'201804_..._refugees-u007' -> '201804_..._refugees' (ids are '<document_id>-uNNN')."""
    return recommendation_id.rsplit("-u", 1)[0]


def _search_date(d: date | None) -> str | None:
    # Edm.DateTimeOffset needs a full timestamp, not a bare date
    return f"{d.isoformat()}T00:00:00Z" if d else None


def to_document(rec: Recommendation, vector: list[float]) -> dict[str, Any]:
    """One record + its embedding as an index document. Nothing is added or rewritten."""
    if len(vector) != EMBEDDING_DIMENSIONS:
        raise ValueError(f"expected {EMBEDDING_DIMENSIONS} dimensions, got {len(vector)}")
    return {
        "id": rec.recommendation_id,
        "recommendation_text": rec.recommendation_text,
        "target_actor_raw": rec.target_actor_raw,
        "action_requested": rec.action_requested,
        "topic": rec.topic,
        "document_id": document_id_of(rec.recommendation_id),
        "document_title": rec.document_title,
        "publication_date": _search_date(rec.publication_date),
        "source_url": rec.source_url,
        "source_page": rec.source_page,
        "source_end_page": rec.source_end_page,
        VECTOR_FIELD: vector,
    }


def exclude_documents_filter(document_ids: list[str]) -> str | None:
    """OData filter that drops whole reports, e.g. the held-out report in a leave-one-out check."""
    if not document_ids:
        return None
    for d in document_ids:
        if "'" in d:
            raise ValueError(f"unexpected quote in document id {d!r}")
    return " and ".join(f"document_id ne '{d}'" for d in document_ids)
