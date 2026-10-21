"""Calls to Azure AI Search and Azure OpenAI embeddings. SDK imports are lazy (CI has no Azure extra).

UNTESTED AGAINST A LIVE SERVICE until the Search resource exists (Session 2 decision gate).
What is tested offline: the definition converter keeps every field and flag, and embedding batching.
"""

from typing import Any

from .schema import INDEX_NAME, VECTOR_FIELD, index_definition

EMBED_BATCH = 64  # inputs per embeddings request; well under the API limit for short texts

_SELECT = [
    "id",
    "recommendation_text",
    "target_actor_raw",
    "action_requested",
    "topic",
    "document_id",
    "document_title",
    "publication_date",
    "source_url",
    "source_page",
    "source_end_page",
]


def embed_texts(client, texts: list[str], deployment: str = "embedding") -> list[list[float]]:
    """Embed in batches, in order. Raises on any failure: a partial index would be misleading."""
    vectors: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        response = client.embeddings.create(model=deployment, input=texts[i : i + EMBED_BATCH])
        data = sorted(response.data, key=lambda d: d.index)
        vectors.extend(d.embedding for d in data)
    if len(vectors) != len(texts):
        raise RuntimeError(f"embedded {len(vectors)} of {len(texts)} texts")
    return vectors


def to_sdk_index(definition: dict[str, Any] | None = None):
    """Turn the REST-shaped definition from schema.py into SDK objects."""
    from azure.search.documents.indexes.models import (
        HnswAlgorithmConfiguration,
        HnswParameters,
        SearchField,
        SearchIndex,
        VectorSearch,
        VectorSearchProfile,
    )

    d = definition or index_definition()
    rename = {
        "analyzer": "analyzer_name",
        "dimensions": "vector_search_dimensions",
        "vectorSearchProfile": "vector_search_profile_name",
    }
    fields = [SearchField(**{rename.get(k, k): v for k, v in f.items()}) for f in d["fields"]]
    vs = d["vectorSearch"]
    algorithms = [
        HnswAlgorithmConfiguration(
            name=a["name"],
            parameters=HnswParameters(
                metric=a["hnswParameters"]["metric"],
                m=a["hnswParameters"]["m"],
                ef_construction=a["hnswParameters"]["efConstruction"],
                ef_search=a["hnswParameters"]["efSearch"],
            ),
        )
        for a in vs["algorithms"]
    ]
    profiles = [
        VectorSearchProfile(name=p["name"], algorithm_configuration_name=p["algorithm"])
        for p in vs["profiles"]
    ]
    return SearchIndex(
        name=d["name"],
        fields=fields,
        vector_search=VectorSearch(algorithms=algorithms, profiles=profiles),
    )


def create_index(endpoint: str, credential) -> None:
    from azure.search.documents.indexes import SearchIndexClient

    SearchIndexClient(endpoint, credential).create_or_update_index(to_sdk_index())


def upload_documents(endpoint: str, credential, documents: list[dict[str, Any]]) -> int:
    """Upload and return how many were accepted; raises if any document failed."""
    from azure.search.documents import SearchClient

    results = SearchClient(endpoint, INDEX_NAME, credential).upload_documents(documents)
    failed = [r.key for r in results if not r.succeeded]
    if failed:
        raise RuntimeError(f"{len(failed)} documents failed to index: {failed[:5]}")
    return len(results)


def hybrid_search(
    endpoint: str,
    credential,
    query_text: str,
    query_vector: list[float],
    top: int = 5,
    odata_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Vector + keyword in one request; Search fuses the two rankings (RRF).

    The score is an ordering signal, not a relevance percentage (D31): show rank, not the number.
    """
    from azure.search.documents import SearchClient
    from azure.search.documents.models import VectorizedQuery

    client = SearchClient(endpoint, INDEX_NAME, credential)
    hits = client.search(
        search_text=query_text,
        vector_queries=[
            VectorizedQuery(vector=query_vector, k_nearest_neighbors=top * 3, fields=VECTOR_FIELD)
        ],
        filter=odata_filter,
        select=_SELECT,
        top=top,
    )
    return [dict(h) for h in hits]
