"""Model-generated labels for one unit at a time (D38).

The model sees one unit and returns only `action_requested` and `topic`. It is never given a
unit ID to echo, and it never writes the quote, so neither can be wrong because of the model.
A failed call leaves the labels empty; the unit and its verbatim text are kept regardless.

The model call is injected (`Labeller`), so tests use a fake and the real run uses Azure.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from .segment import Unit

PROMPT_VERSION = "extract_unit_v1"
PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts" / f"{PROMPT_VERSION}.md"


class UnitLabels(BaseModel):
    """The structured-output schema the model must fill in."""

    action_requested: str = Field(description="One short imperative sentence")
    topic: list[str] = Field(description="One to four short lowercase noun phrases")


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass(frozen=True)
class LabelResult:
    unit_id: str
    labels: UnitLabels | None  # None when every attempt failed
    error: str | None
    usage: Usage


# (system prompt, user message) -> parsed labels and token usage; raises on API failure
Labeller = Callable[[str, str], tuple[UnitLabels, Usage]]


def load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def user_message(unit: Unit) -> str:
    heading = unit.actor_raw or "Recommendations"
    return f"Heading: {heading}\n\nRecommendation text:\n{unit.text}"


def _valid(labels: UnitLabels) -> str | None:
    if not labels.action_requested.strip():
        return "empty action_requested"
    if not 1 <= len(labels.topic) <= 4 or any(not t.strip() for t in labels.topic):
        return f"topic count {len(labels.topic)} outside 1-4 or blank topic"
    return None


def label_unit(labeller: Labeller, unit: Unit, system: str, attempts: int = 2) -> LabelResult:
    usage = Usage()
    error = None
    for _ in range(attempts):
        try:
            labels, used = labeller(system, user_message(unit))
        except Exception as exc:  # noqa: BLE001 - any API failure is recorded, never drops a unit
            if getattr(exc, "code", None) == "content_filter":
                # deterministic for this text: retrying cannot help, and it needs its own label
                return LabelResult(unit.unit_id, None, "content_filter (Azure policy)", usage)
            error = f"{type(exc).__name__}: {exc}"
            continue
        usage = Usage(
            usage.prompt_tokens + used.prompt_tokens,
            usage.completion_tokens + used.completion_tokens,
        )
        problem = _valid(labels)
        if problem is None:
            return LabelResult(unit.unit_id, labels, None, usage)
        error = problem
    return LabelResult(unit.unit_id, None, error, usage)


def azure_labeller(client, deployment: str = "chat") -> Labeller:
    """Real model call: structured output, temperature 0, via the Azure OpenAI client."""

    def call(system: str, user: str) -> tuple[UnitLabels, Usage]:
        response = client.beta.chat.completions.parse(
            model=deployment,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format=UnitLabels,
            temperature=0,
            max_tokens=200,
        )
        message = response.choices[0].message
        if message.parsed is None:
            raise ValueError(f"no parsed output (refusal: {message.refusal!r})")
        usage = Usage(response.usage.prompt_tokens, response.usage.completion_tokens)
        return message.parsed, usage

    return call
