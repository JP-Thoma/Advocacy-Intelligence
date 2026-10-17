from importlib import resources
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles

from advocacy_intel.api.document_text import MAX_UPLOAD_BYTES, DocumentError, extract_paragraphs
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


@app.post("/api/extract")
async def extract(request: Request, filename: str = "") -> dict[str, object]:
    """Return candidate paragraphs of an uploaded .docx/.pptx/.pdf/.txt (raw request body,
    type taken from `filename`). Nothing is stored."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "The file is larger than 5 MB.")
    data = await request.body()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "The file is larger than 5 MB.")
    try:
        paragraphs, truncated = extract_paragraphs(data, filename)
    except DocumentError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not paragraphs:
        raise HTTPException(
            422, "No readable text was found. Scanned PDFs (images of text) are not supported."
        )
    return {"paragraphs": paragraphs, "truncated": truncated}


if WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
