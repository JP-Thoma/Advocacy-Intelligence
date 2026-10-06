from fastapi.testclient import TestClient

from advocacy_intel.api.main import app

client = TestClient(app)


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_check_returns_precedents_and_flags_mock():
    r = client.post("/api/check", json={"draft_text": "Authorities should do X."})
    assert r.status_code == 200
    body = r.json()
    assert body["is_mock"] is True
    assert body["draft"]["text"] == "Authorities should do X."
    assert body["precedents"]


def test_user_corrections_override_parse():
    r = client.post(
        "/api/check",
        json={"draft_text": "x", "target_actor": "Parliament", "topic": ["Detention"]},
    )
    assert r.json()["draft"]["target_actor"] == "Parliament"
    assert r.json()["draft"]["topic"] == ["Detention"]


def test_empty_draft_rejected():
    assert client.post("/api/check", json={"draft_text": ""}).status_code == 422


def test_every_llm_difference_has_verified_quotes_in_fixture():
    # Guards the responsible-AI rule: no unverified LLM claim is displayed.
    body = client.post("/api/check", json={"draft_text": "x"}).json()
    for p in body["precedents"]:
        for d in p["differences"]:
            assert d["quotes_verified"] is True
