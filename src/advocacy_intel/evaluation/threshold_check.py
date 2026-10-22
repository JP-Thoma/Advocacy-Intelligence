"""Calibration check for the relevance threshold (D43): is the cutoff still in the right place?

Usage (repo root, after login; PowerShell):
    $env:AZURE_OPENAI_ENDPOINT = "<openAiEndpoint>"; $env:ADVOCACY_RETRIEVAL = "azure-cosine"
    .venv\\Scripts\\python -m advocacy_intel.evaluation.threshold_check 202409_lebanon_syrianrefugeepushbacks

For every text, the score is the top-1 similarity of the draft WITHOUT an actor line against the
stored vectors, which is what the cutoff uses. Three groups:
- REAL: each recommendation of one report, with that report hidden (what a real draft looks like);
- OFF-TOPIC: synthetic sentences unrelated to rights (written here, clearly not HRW text);
- RIGHTS-RELATED, NOT IN CORPUS: synthetic sentences on other human-rights topics.
The cutoff is meant to separate OFF-TOPIC from REAL. It is not expected to separate
"has a real precedent" from "has none", and RIGHTS-RELATED texts may pass. Small sample: counts
are printed, not just percentages. Re-run after changing the embedding model, text or corpus.
"""

import sys
from pathlib import Path

from advocacy_intel.retrieval.precedents import from_environment

OUT = Path("data/records")

OFF_TOPIC = [
    "Always take an umbrella when it rains.",
    "Use a sharp knife and let the onions cook slowly for twenty minutes.",
    "Upgrade the database server to the latest version before the end of the quarter.",
    "The football team should train twice a week during the winter season.",
    "Invest in a diversified index fund and rebalance every year.",
    "Water the plants every morning and keep them away from direct sunlight.",
]
RIGHTS_RELATED = [
    "Abolish the death penalty and commute all existing sentences.",
    "Protect journalists from arbitrary arrest and allow independent media to operate freely.",
    "Reduce greenhouse gas emissions and phase out coal power plants by 2030.",
    "Ensure free school meals for all children in public schools.",
    "Guarantee access to clean drinking water for all residents.",
]


def _top1(retriever, text: str, exclude: list[str] | None = None) -> float:
    """Top-1 no-actor similarity, measured with the cutoff switched off."""
    saved = retriever.min_relevance
    retriever.min_relevance = 0.0
    try:
        found = retriever.find(text, None, k=1, exclude_documents=exclude).precedents
    finally:
        retriever.min_relevance = saved
    # with no actor line the ranking score IS the cutoff score
    return found[0].relevance


def run(doc_id: str) -> str:
    retriever = from_environment()
    if retriever is None:
        raise SystemExit("set ADVOCACY_RETRIEVAL=azure-cosine and AZURE_OPENAI_ENDPOINT first")
    tau = retriever.min_relevance
    real = sorted(
        r.recommendation_text
        for r in retriever._records.values()
        if r.recommendation_id.startswith(doc_id)
    )
    groups = {
        "REAL (held-out report)": [_top1(retriever, t, [doc_id]) for t in real],
        "OFF-TOPIC (synthetic)": [_top1(retriever, t) for t in OFF_TOPIC],
        "RIGHTS-RELATED, NOT IN CORPUS (synthetic)": [_top1(retriever, t) for t in RIGHTS_RELATED],
    }
    lines = [f"# Threshold check (cutoff = {tau:.2f}, report held out: {doc_id})", ""]
    lines += [
        "| group | n | min | median | max | passing the cutoff |",
        "|---|---|---|---|---|---|",
    ]
    for name, scores in groups.items():
        s = sorted(scores)
        passing = sum(x >= tau for x in s)
        lines.append(
            f"| {name} | {len(s)} | {s[0]:.2f} | {s[len(s) // 2]:.2f} | {s[-1]:.2f} | {passing}/{len(s)} |"
        )
    lines += [
        "",
        "Intended: all REAL pass, no OFF-TOPIC passes. RIGHTS-RELATED may pass; that is expected.",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    text = run(sys.argv[1])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "threshold_check.md").write_text(text, encoding="utf-8")
    print(text)
