from types import SimpleNamespace

import pytest

from advocacy_intel.indexing.schema import index_definition
from advocacy_intel.indexing.service import EMBED_BATCH, embed_texts, to_sdk_index


class FakeEmbeddings:
    def __init__(self):
        self.calls = []

    def create(self, model, input):
        self.calls.append((model, list(input)))
        # return out of order on purpose: the caller must restore input order by index
        items = [SimpleNamespace(index=i, embedding=[float(len(t))]) for i, t in enumerate(input)]
        return SimpleNamespace(data=list(reversed(items)))


def test_embed_texts_batches_and_keeps_input_order():
    texts = ["a" * (i + 1) for i in range(EMBED_BATCH + 3)]
    fake = SimpleNamespace(embeddings=FakeEmbeddings())
    vectors = embed_texts(fake, texts)
    assert vectors == [[float(len(t))] for t in texts]
    assert [len(inputs) for _, inputs in fake.embeddings.calls] == [EMBED_BATCH, 3]
    assert fake.embeddings.calls[0][0] == "embedding"


def test_sdk_conversion_keeps_every_field_and_the_vector_wiring():
    pytest.importorskip("azure.search.documents")
    definition = index_definition()
    index = to_sdk_index(definition)
    assert [f.name for f in index.fields] == [f["name"] for f in definition["fields"]]
    vec = next(f for f in index.fields if f.name == "content_vector")
    assert vec.vector_search_dimensions == 3072
    assert vec.vector_search_profile_name == index.vector_search.profiles[0].name
    assert index.vector_search.algorithms[0].parameters.metric == "cosine"
    key = next(f for f in index.fields if f.name == "id")
    assert key.key is True
    text = next(f for f in index.fields if f.name == "recommendation_text")
    assert text.analyzer_name == "en.microsoft"
