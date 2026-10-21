"""Find prior recommendations for a draft: embed the draft, rank stored records by cosine.

This is the retrieval step only. It returns real records with their verbatim wording; it makes no
claim about differences (comparison is deferred, D37), so `Precedent.differences` stays empty.
The score is an ordering signal, not a measure of correctness (D31).
"""

import os
from collections.abc import Callable

from advocacy_intel.indexing.embedding_text import TEXT_VERSION, draft_text
from advocacy_intel.indexing.fallback import Entry, top_k
from advocacy_intel.models import Precedent, Recommendation

ENV_SWITCH = "ADVOCACY_RETRIEVAL"
ENV_VALUE = "azure-cosine"

Embedder = Callable[[str], list[float]]


class StoreMismatch(RuntimeError):
    """The vector file does not describe the records on disk (stale or built differently)."""


class PrecedentRetriever:
    def __init__(self, records: list[Recommendation], store: dict, embed_query: Embedder):
        if store.get("text_version") != TEXT_VERSION:
            raise StoreMismatch(
                f"vectors built with {store.get('text_version')!r}, code expects {TEXT_VERSION!r}"
            )
        self._records = {r.recommendation_id: r for r in records}
        self._entries = [Entry(e["id"], e["vector"]) for e in store["entries"]]
        if {e.recommendation_id for e in self._entries} != set(self._records):
            raise StoreMismatch("records and vectors cover different recommendation ids; rebuild")
        self._embed_query = embed_query

    def find(
        self,
        draft: str,
        target_actor: str | None = None,
        k: int = 5,
        exclude_documents: list[str] | None = None,
    ) -> list[Precedent]:
        query = self._embed_query(draft_text(draft, target_actor))
        hits = top_k(query, self._entries, k=k, exclude_documents=exclude_documents)
        return [
            Precedent(
                recommendation=self._records[rec_id],
                matched_dimensions=["semantic similarity"],
                relevance=max(0.0, min(1.0, score)),
                differences=[],
            )
            for rec_id, score in hits
        ]


def from_environment() -> PrecedentRetriever | None:
    """Real retrieval only when explicitly switched on; otherwise None (the API serves the mock)."""
    if os.environ.get(ENV_SWITCH) != ENV_VALUE:
        return None
    from advocacy_intel.indexing.service import embed_texts
    from advocacy_intel.indexing.vectors import azure_client, load_records, load_store

    client = azure_client()
    return PrecedentRetriever(
        load_records(), load_store(), lambda text: embed_texts(client, [text])[0]
    )
