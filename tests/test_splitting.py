from fastapi.testclient import TestClient

from advocacy_intel.api.main import app
from advocacy_intel.api.splitting import MAX_RECOMMENDATIONS, split_recommendations

A = "The Lebanese authorities should strengthen judicial independence."
B = "Parliament should adopt legislation protecting judges from political interference."
C = "The government must ensure the investigation is completed without interference."


def test_single_recommendation_is_unchanged():
    assert split_recommendations(A) == ([A], False)


def test_numbered_list_on_separate_lines():
    assert split_recommendations(f"1. {A}\n2. {B}\n3. {C}")[0] == [A, B, C]


def test_numbered_list_glued_on_one_line():
    # the exact shape from the user's example: no space after the full stop
    assert split_recommendations(f"1. {A}2. {B} 3. {C}")[0] == [A, B, C]


def test_parenthesis_numbering_and_intro_line():
    text = f"Recommendations:\n1) {A}\n2) {B}"
    assert split_recommendations(text)[0] == [A, B]


def test_numbers_inside_a_sentence_do_not_split():
    text = "Authorities should publish Article 2.1 of the law and fund 1.5 million places."
    assert split_recommendations(text)[0] == [text]


def test_numbering_must_start_at_one_and_count_up():
    text = f"5. {A} 7. {B}"
    assert split_recommendations(text)[0] == [text]


def test_bullets_and_blank_lines():
    assert split_recommendations(f"- {A}\n- {B}")[0] == [A, B]
    assert split_recommendations(f"{A}\n\n{B}")[0] == [A, B]


def test_wrapped_lines_are_joined():
    wrapped = "The Lebanese authorities should strengthen\njudicial independence."
    assert split_recommendations(wrapped)[0] == [A]


def test_empty_input():
    assert split_recommendations("  \n ") == ([], False)


def test_cap_is_reported():
    text = "\n".join(f"{i}. {A}" for i in range(1, MAX_RECOMMENDATIONS + 4))
    items, truncated = split_recommendations(text)
    assert len(items) == MAX_RECOMMENDATIONS and truncated


def test_split_endpoint():
    client = TestClient(app)
    resp = client.post("/api/split", json={"text": f"1. {A}\n2. {B}"})
    assert resp.status_code == 200
    assert resp.json() == {"recommendations": [A, B], "truncated": False}
    assert client.post("/api/split", json={"text": "   "}).status_code == 422
