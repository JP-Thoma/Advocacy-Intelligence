from datetime import date

from pydantic import BaseModel, Field


class Recommendation(BaseModel):
    """One recommendation extracted from a published HRW document.

    `recommendation_text` and `source_context` are verbatim source text (D3).
    Fields marked model-generated are interpretations and must be shown as such.
    """

    recommendation_id: str
    recommendation_text: str = Field(description="Verbatim quote from the source document")
    source_context: str = Field(description="Verbatim surrounding text, e.g. section heading")
    source_chunk_id: str | None = None

    target_actor_raw: str = Field(description="Actor string exactly as written in the source")
    target_actor: str | None = Field(default=None, description="Normalised actor (model-generated)")
    action_requested: str | None = Field(default=None, description="Short summary (model-generated)")
    topic: list[str] = Field(default_factory=list, description="Normalised (model-generated)")
    geography: list[str] = Field(default_factory=list)

    publication_date: date | None = None
    document_title: str
    document_type: str
    source_url: str | None = Field(default=None, description="Link to the original publication")
