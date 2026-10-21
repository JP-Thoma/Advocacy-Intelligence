"""Cosine-similarity retrieval over stored vectors: the Session 2 decision-gate fallback (D40).

Used only if Azure AI Search is not returning results in time. It needs no Search service, and
it is presented honestly as a fallback, with AI Search as the designed component. Vector only (no
keyword side), so it is expected to rank differently from hybrid search. At ~100 records an exact
scan in plain Python takes milliseconds; it is not a design for 100k documents.
"""

import math
from dataclasses import dataclass

from .schema import document_id_of


@dataclass(frozen=True)
class Entry:
    recommendation_id: str
    vector: list[float]


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"vector sizes differ: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def top_k(
    query: list[float],
    entries: list[Entry],
    k: int = 5,
    exclude_documents: list[str] | None = None,
) -> list[tuple[str, float]]:
    """Best k (recommendation_id, similarity), highest first; ties broken by id for stability."""
    skip = set(exclude_documents or [])
    scored = [
        (e.recommendation_id, cosine(query, e.vector))
        for e in entries
        if document_id_of(e.recommendation_id) not in skip
    ]
    scored.sort(key=lambda t: (-t[1], t[0]))
    return scored[:k]
