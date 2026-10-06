from importlib import resources
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from advocacy_intel.models import CheckRequest, CheckResponse

WEB_DIR = Path(__file__).resolve().parents[3] / "web"

app = FastAPI(title="HRW Recommendation Consistency Assistant (POC)")


def _load_mock() -> CheckResponse:
    raw = resources.files("advocacy_intel.fixtures").joinpath("mock_check.json").read_text("utf-8")
    return CheckResponse.model_validate_json(raw)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/check", response_model=CheckResponse)
def check(req: CheckRequest) -> CheckResponse:
    """Check a draft against prior recommendations. Fixture-backed until M3-M5."""
    resp = _load_mock()
    resp.draft.text = req.draft_text
    if req.target_actor is not None:
        resp.draft.target_actor = req.target_actor
    if req.topic is not None:
        resp.draft.topic = req.topic
    return resp


if WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
