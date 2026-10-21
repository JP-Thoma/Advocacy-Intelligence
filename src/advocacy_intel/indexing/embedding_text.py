"""What text is turned into a vector (D41): actor heading + quote + the model's labels.

One function per side, so the stored records and the user's draft are written in the same shape.
Lines for missing values are left out, never invented: a record whose labels were blocked by the
content filter (D39) simply has a shorter text. The draft carries no model labels.
"""

from advocacy_intel.models import Recommendation

TEXT_VERSION = "embed-text-v1"


def record_text(rec: Recommendation) -> str:
    lines = []
    if rec.target_actor_raw:
        lines.append(f"Target actor: {rec.target_actor_raw}")
    lines.append(f"Recommendation: {rec.recommendation_text}")
    if rec.action_requested:
        lines.append(f"Requested action: {rec.action_requested}")
    if rec.topic:
        lines.append(f"Topics: {', '.join(rec.topic)}")
    return "\n".join(lines)


def draft_text(text: str, target_actor: str | None = None) -> str:
    lines = []
    if target_actor and target_actor.strip():
        lines.append(f"Target actor: {target_actor.strip()}")
    lines.append(f"Recommendation: {text.strip()}")
    return "\n".join(lines)
