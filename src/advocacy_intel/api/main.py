from functools import lru_cache
from importlib import resources
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from advocacy_intel.api.document_text import MAX_UPLOAD_BYTES, DocumentError, extract_paragraphs
from advocacy_intel.api.splitting import split_recommendations
from advocacy_intel.models import CheckRequest, CheckResponse, DraftParse, Provenance
from advocacy_intel.retrieval.precedents import PrecedentRetriever, from_environment

WEB_DIR = Path(__file__).resolve().parents[3] / "web"

app = FastAPI(title="HRW Recommendation Consistency Assistant (POC)")


def _load_mock() -> CheckResponse:
    raw = resources.files("advocacy_intel.fixtures").joinpath("mock_check.json").read_text("utf-8")
    return CheckResponse.model_validate_json(raw)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


REAL_NOTICE = (
    "This tool retrieves prior HRW wording. It does not compare wording yet and does not assess "
    "consistency with HRW policy. The author and reviewers decide."
)


@lru_cache
def _retriever() -> PrecedentRetriever | None:
    return from_environment()


def get_retriever() -> PrecedentRetriever | None:
    """None means 'serve the fixture'. A broken real setup is an error, never a silent mock."""
    try:
        return _retriever()
    except Exception as exc:
        raise HTTPException(503, f"Retrieval is switched on but not available: {exc}") from exc


@app.post("/api/check", response_model=CheckResponse)
def check(
    req: CheckRequest,
    retriever: PrecedentRetriever | None = Depends(get_retriever),  # noqa: B008
) -> CheckResponse:
    """Check a draft against prior recommendations.

    Real retrieval (no comparison) when ADVOCACY_RETRIEVAL=azure-cosine, else the fixture."""
    if retriever is not None:
        try:
            result = retriever.find(req.draft_text, req.target_actor)
        except Exception as exc:
            raise HTTPException(503, f"Retrieval failed: {exc}") from exc
        return CheckResponse(
            draft=DraftParse(
                text=req.draft_text,
                target_actor=req.target_actor,
                topic=req.topic or [],
                geography=req.geography or [],
                provenance=Provenance.FOR_HUMAN_REVIEW,  # only what the user typed; nothing inferred
            ),
            precedents=result.precedents,
            hidden_below_threshold=result.hidden_below_threshold,
            notice=REAL_NOTICE,
            is_mock=False,
            comparison_performed=False,
        )
    resp = _load_mock()
    resp.draft.text = req.draft_text
    if req.target_actor is not None:
        resp.draft.target_actor = req.target_actor
    if req.topic is not None:
        resp.draft.topic = req.topic
    if req.geography is not None:
        resp.draft.geography = req.geography
    return resp


class SplitRequest(BaseModel):
    text: str = Field(max_length=20000)


@app.post("/api/split")
def split(req: SplitRequest) -> dict[str, object]:
    """Split pasted text into separate recommendations (deterministic heuristics)."""
    recommendations, truncated = split_recommendations(req.text)
    if not recommendations:
        raise HTTPException(422, "Enter at least one recommendation.")
    return {"recommendations": recommendations, "truncated": truncated}


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


class RevalidatingStaticFiles(StaticFiles):
    """Static files that browsers must revalidate (ETag) so edits show up on reload."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


if WEB_DIR.is_dir():
    app.mount("/", RevalidatingStaticFiles(directory=WEB_DIR, html=True), name="web")
