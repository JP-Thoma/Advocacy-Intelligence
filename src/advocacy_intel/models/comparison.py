from enum import Enum

from pydantic import BaseModel, Field

from .recommendation import Recommendation


class Provenance(str, Enum):
    """Knowledge vs inference. Every displayed statement carries one of these."""

    SOURCE_TEXT = "source_text"  # verbatim HRW wording
    MODEL_SYNTHESIS = "model_synthesis"  # LLM summary or comparison
    FOR_HUMAN_REVIEW = "for_human_review"  # inference the user must check


class Method(str, Enum):
    DETERMINISTIC = "deterministic"  # computed by code, reproducible
    LLM = "llm"  # judged by the model, quotes verified by code


class Dimension(str, Enum):
    TARGET_ACTOR = "target_actor"
    GEOGRAPHY = "geography"
    SCOPE = "scope"
    SPECIFICITY = "specificity"
    STRENGTH_OF_LANGUAGE = "strength_of_language"
    SAFEGUARDS = "safeguards"
    REQUESTED_ACTION = "requested_action"
    DATE = "date"


class Difference(BaseModel):
    dimension: Dimension
    observation: str = Field(description="Hedged wording, e.g. 'appears broader'; never a verdict")
    draft_quote: str | None = Field(default=None, description="Exact words from the draft")
    prior_quote: str | None = Field(default=None, description="Exact words from the prior text")
    method: Method
    provenance: Provenance = Provenance.MODEL_SYNTHESIS
    quotes_verified: bool = Field(description="True only if code confirmed both quotes exist")


class Precedent(BaseModel):
    recommendation: Recommendation
    matched_dimensions: list[str] = Field(description="Why this was retrieved, e.g. ['actor','issue']")
    relevance: float = Field(ge=0, le=1, description="Retrieval relevance, not a policy judgement")
    differences: list[Difference] = Field(default_factory=list)


class DraftParse(BaseModel):
    """How the system understood the draft. Shown to the user and editable."""

    text: str
    target_actor: str | None = None
    topic: list[str] = Field(default_factory=list)
    geography: list[str] = Field(default_factory=list)
    provenance: Provenance = Provenance.MODEL_SYNTHESIS


class CheckRequest(BaseModel):
    draft_text: str = Field(min_length=1)
    target_actor: str | None = None  # user-confirmed overrides
    topic: list[str] | None = None


class CheckResponse(BaseModel):
    draft: DraftParse
    precedents: list[Precedent]
    notice: str = Field(description="Standing statement that humans decide")
    is_mock: bool = Field(description="True while responses come from fixtures")
