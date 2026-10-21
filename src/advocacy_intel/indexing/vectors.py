"""Local vector store built from the records (derived data, rebuildable, gitignored with data/).

Usage (repo root, after `az login`; PowerShell):
    $env:AZURE_OPENAI_ENDPOINT = "<openAiEndpoint>"
    .venv\\Scripts\\python -m advocacy_intel.indexing.vectors

Reads data/records/<id>.json, embeds record_text() with the `embedding` deployment, writes
data/index/vectors.json. The same file feeds the cosine fallback and, later, the AI Search upload.
"""

import json
import os
import sys
from pathlib import Path

from advocacy_intel.models import Recommendation

from .embedding_text import TEXT_VERSION, record_text
from .schema import EMBEDDING_DIMENSIONS
from .service import embed_texts

RECORDS = Path("data/records")
VECTORS = Path("data/index/vectors.json")
EMBEDDING_MODEL = "text-embedding-3-large"
API_VERSION = "2024-10-21"


def load_records(directory: Path = RECORDS) -> list[Recommendation]:
    records: list[Recommendation] = []
    for path in sorted(directory.glob("2*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        records.extend(Recommendation.model_validate(r) for r in payload["records"])
    return records


def build_store(records: list[Recommendation], embed) -> dict:
    """`embed` maps a list of texts to a list of vectors (injected so tests need no Azure)."""
    vectors = embed([record_text(r) for r in records])
    for v in vectors:
        if len(v) != EMBEDDING_DIMENSIONS:
            raise ValueError(f"expected {EMBEDDING_DIMENSIONS} dimensions, got {len(v)}")
    return {
        "embedding_model": EMBEDDING_MODEL,
        "text_version": TEXT_VERSION,
        "dimensions": EMBEDDING_DIMENSIONS,
        "entries": [
            {"id": r.recommendation_id, "vector": v} for r, v in zip(records, vectors, strict=True)
        ],
    }


def save_store(store: dict, path: Path = VECTORS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store), encoding="utf-8")


def load_store(path: Path = VECTORS) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def azure_client():
    """Keyless Azure OpenAI client using the developer identity (az login)."""
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from openai import AzureOpenAI

    return AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_ad_token_provider=get_bearer_token_provider(
            DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
        ),
        api_version=API_VERSION,
    )


def main() -> int:
    records = load_records()
    if not records:
        print("no records found in data/records; run the ingestion first")
        return 1
    client = azure_client()
    store = build_store(records, lambda texts: embed_texts(client, texts))
    save_store(store)
    print(f"embedded {len(records)} records -> {VECTORS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
