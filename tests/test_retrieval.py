import pytest
from fastapi.testclient import TestClient

from advocacy_intel.api.main import app, get_retriever
from advocacy_intel.indexing.embedding_text import TEXT_VERSION, draft_text, record_text
from advocacy_intel.indexing.schema import EMBEDDING_DIMENSIONS
from advocacy_intel.indexing.vectors import build_store
from advocacy_intel.models import Recommendation
from advocacy_intel.retrieval.precedents import PrecedentRetriever, StoreMismatch, from_environment


def rec(rid, text, actor="To the Government", action=None, topic=None):
    return Recommendation(
        recommendation_id=rid,
        recommendation_text=text,
        source_context=actor,
        target_actor_raw=actor,
        action_requested=action,
        topic=topic or [],
        document_title="A Report",
        document_type="report",
    )


def axis(i):
    v = [0.0] * EMBEDDING_DIMENSIONS
    v[i] = 1.0
    return v


RECORDS = [rec("docA-u001", "Halt expulsions."), rec("docB-u001", "Allow UNHCR access.")]


def fake_embed_texts(texts):
    # direction depends on a keyword, so retrieval is predictable without Azure
    return [axis(0 if "expuls" in t.lower() else 1) for t in texts]


def make(records=RECORDS):
    store = build_store(records, fake_embed_texts)
    return PrecedentRetriever(records, store, lambda t: fake_embed_texts([t])[0])


def test_embedding_text_includes_actor_quote_and_labels_and_omits_missing_ones():
    full = rec("d-u001", "Halt it.", "To X", "Halt the thing", ["detention", "expulsion"])
    assert record_text(full) == (
        "Target actor: To X\nRecommendation: Halt it.\n"
        "Requested action: Halt the thing\nTopics: detention, expulsion"
    )
    assert record_text(rec("d-u002", "Halt it.", "To X")) == (
        "Target actor: To X\nRecommendation: Halt it."
    )


def test_draft_text_has_no_labels_and_actor_only_when_given():
    assert draft_text("  Do X. ") == "Recommendation: Do X."
    assert draft_text("Do X.", "Parliament") == "Target actor: Parliament\nRecommendation: Do X."


def test_retriever_returns_real_records_unmodified_with_no_differences():
    [top, *_] = make().find("They must stop expulsions", k=2)
    assert top.recommendation.recommendation_id == "docA-u001"
    assert top.recommendation.recommendation_text == "Halt expulsions."
    assert top.differences == []
    assert 0.0 <= top.relevance <= 1.0


def test_held_out_document_can_be_excluded():
    got = make().find("expulsions", k=5, exclude_documents=["docA"])
    assert [p.recommendation.recommendation_id for p in got] == ["docB-u001"]


def test_stale_vector_file_is_rejected():
    store = build_store(RECORDS, fake_embed_texts)
    with pytest.raises(StoreMismatch, match="different recommendation ids"):
        PrecedentRetriever(RECORDS[:1], store, lambda t: axis(0))
    store["text_version"] = "old"
    with pytest.raises(StoreMismatch, match=TEXT_VERSION):
        PrecedentRetriever(RECORDS, store, lambda t: axis(0))


def test_real_retrieval_is_off_unless_switched_on(monkeypatch):
    monkeypatch.delenv("ADVOCACY_RETRIEVAL", raising=False)
    assert from_environment() is None


# ---- API ----


@pytest.fixture
def client():
    app.dependency_overrides[get_retriever] = lambda: make()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_api_real_mode_returns_real_precedents_and_says_no_comparison_was_run(client):
    body = client.post("/api/check", json={"draft_text": "Stop expulsions."}).json()
    assert body["is_mock"] is False
    assert body["comparison_performed"] is False
    assert body["precedents"][0]["recommendation"]["recommendation_text"] == "Halt expulsions."
    assert all(p["differences"] == [] for p in body["precedents"])
    # nothing from the fixture may appear beside real results (D37)
    app.dependency_overrides[get_retriever] = lambda: None
    fixture = TestClient(app).post("/api/check", json={"draft_text": "x"}).json()
    app.dependency_overrides[get_retriever] = lambda: make()
    fixture_texts = {p["recommendation"]["recommendation_text"] for p in fixture["precedents"]}
    assert fixture["is_mock"] is True and fixture_texts
    assert not fixture_texts & {
        p["recommendation"]["recommendation_text"] for p in body["precedents"]
    }


def test_api_real_mode_echoes_only_what_the_user_typed(client):
    body = client.post(
        "/api/check", json={"draft_text": "x", "target_actor": "Parliament", "topic": ["Detention"]}
    ).json()
    assert body["draft"]["target_actor"] == "Parliament"
    assert body["draft"]["topic"] == ["Detention"]
    plain = client.post("/api/check", json={"draft_text": "x"}).json()
    assert plain["draft"]["target_actor"] is None and plain["draft"]["topic"] == []


def test_api_real_mode_failure_is_a_503_not_a_silent_mock():
    def broken(_):
        raise RuntimeError("token expired")

    bad = PrecedentRetriever(RECORDS, build_store(RECORDS, fake_embed_texts), broken)
    app.dependency_overrides[get_retriever] = lambda: bad
    try:
        r = TestClient(app).post("/api/check", json={"draft_text": "x"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 503 and "token expired" in r.json()["detail"]
