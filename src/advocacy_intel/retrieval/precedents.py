"""Find prior recommendations for a draft: embed the draft, rank stored records by cosine.

This is the retrieval step only. It returns real records with their verbatim wording; it makes no
claim about differences (comparison is deferred, D37), so `Precedent.differences` stays empty.
The score is an ordering signal, not a measure of correctness (D31).

Relevance threshold (D43). The ranking text includes the actor line, which adds about 0.3 to every
score, so a cutoff on the ranking score would depend on what the user typed in the actor field.
The cutoff therefore uses a second score: the draft embedded WITHOUT the actor line, compared with
the same stored vectors. Both texts go out in one embedding call. The cutoff removes clearly
unrelated text; it does not decide whether a true precedent exists.
"""

import os
from collections.abc import Callable
from dataclasses import dataclass

from advocacy_intel.indexing.embedding_text import TEXT_VERSION, draft_text
from advocacy_intel.indexing.fallback import Entry, cosine, top_k
from advocacy_intel.models import Precedent, Recommendation

ENV_SWITCH = "ADVOCACY_RETRIEVAL"
ENV_VALUE = "azure-cosine"
ENV_THRESHOLD = "ADVOCACY_MIN_RELEVANCE"

# Between the highest off-topic score (0.34) and the lowest real held-out score (0.50) measured on
# 44 texts (D43). Re-run `python -m advocacy_intel.evaluation.threshold_check` after any change to
# the embedding model, the embedded text or the corpus.
DEFAULT_MIN_RELEVANCE = 0.42

# Embeds several texts in one call, returning vectors in the same order.
BatchEmbedder = Callable[[list[str]], list[list[float]]]


class StoreMismatch(RuntimeError):
    """The vector file does not describe the records on disk (stale or built differently)."""


@dataclass(frozen=True)
class RetrievalResult:
    precedents: list[Precedent]
    hidden_below_threshold: int  # top-k candidates dropped by the cutoff


class PrecedentRetriever:
    def __init__(
        self,
        records: list[Recommendation],
        store: dict,
        embed: BatchEmbedder,
        min_relevance: float = DEFAULT_MIN_RELEVANCE,
    ):
        if store.get("text_version") != TEXT_VERSION:
            raise StoreMismatch(
                f"vectors built with {store.get('text_version')!r}, code expects {TEXT_VERSION!r}"
            )
        if not 0.0 <= min_relevance <= 1.0:
            raise ValueError(f"min_relevance must be between 0 and 1, got {min_relevance}")
        self._records = {r.recommendation_id: r for r in records}
        self._entries = [Entry(e["id"], e["vector"]) for e in store["entries"]]
        if {e.recommendation_id for e in self._entries} != set(self._records):
            raise StoreMismatch("records and vectors cover different recommendation ids; rebuild")
        self._vectors = {e.recommendation_id: e.vector for e in self._entries}
        self._embed = embed
        self.min_relevance = min_relevance

    def find(
        self,
        draft: str,
        target_actor: str | None = None,
        k: int = 5,
        exclude_documents: list[str] | None = None,
    ) -> RetrievalResult:
        ranking_text = draft_text(draft, target_actor)
        bare_text = draft_text(draft)
        if ranking_text == bare_text:  # no actor given: one embedding serves both purposes
            [ranking_vec] = self._embed([ranking_text])
            bare_vec = ranking_vec
        else:
            ranking_vec, bare_vec = self._embed([ranking_text, bare_text])

        hits = top_k(ranking_vec, self._entries, k=k, exclude_documents=exclude_documents)
        kept: list[Precedent] = []
        for rec_id, score in hits:
            if cosine(bare_vec, self._vectors[rec_id]) < self.min_relevance:
                continue
            kept.append(
                Precedent(
                    recommendation=self._records[rec_id],
                    matched_dimensions=["semantic similarity"],
                    relevance=max(0.0, min(1.0, score)),
                    differences=[],
                )
            )
        return RetrievalResult(kept, len(hits) - len(kept))


def from_environment() -> PrecedentRetriever | None:
    """Real retrieval only when explicitly switched on; otherwise None (the API serves the mock)."""
    if os.environ.get(ENV_SWITCH) != ENV_VALUE:
        return None
    from advocacy_intel.indexing.service import embed_texts
    from advocacy_intel.indexing.vectors import azure_client, load_records, load_store

    client = azure_client()
    threshold = float(os.environ.get(ENV_THRESHOLD, DEFAULT_MIN_RELEVANCE))
    return PrecedentRetriever(
        load_records(),
        load_store(),
        lambda texts: embed_texts(client, texts),
        min_relevance=threshold,
    )
