"""Held-out retrieval check: use each recommendation of one report as a draft, hide that report.

Usage (repo root, after login; PowerShell):
    $env:AZURE_OPENAI_ENDPOINT = "<openAiEndpoint>"; $env:ADVOCACY_RETRIEVAL = "azure-cosine"
    .venv\\Scripts\\python -m advocacy_intel.evaluation.heldout 202409_lebanon_syrianrefugeepushbacks

Writes data/records/heldout_<id>.md. Without labelled precedent pairs this cannot be SCORED; it
lists what comes back so a human can judge, and reports only facts that need no judgement
(which reports were retrieved, how often the same actor words appear). Not a quality claim.
"""

import re
import sys
from collections import Counter
from pathlib import Path

from advocacy_intel.retrieval.precedents import from_environment

OUT = Path("data/records")


def _doc(rec_id: str) -> str:
    return rec_id.rsplit("-u", 1)[0]


def _short(text: str, n: int = 160) -> str:
    return text if len(text) <= n else text[:n] + "..."


def _actor_words(actor: str) -> set[str]:
    stop = {"to", "the", "and", "of", "related", "all", "its"}
    return {w for w in re.findall(r"[a-z]+", actor.casefold()) if w not in stop}


def run(doc_id: str, k: int = 3) -> str:
    retriever = from_environment()
    if retriever is None:
        raise SystemExit("set ADVOCACY_RETRIEVAL=azure-cosine and AZURE_OPENAI_ENDPOINT first")
    drafts = [r for r in retriever._records.values() if _doc(r.recommendation_id) == doc_id]
    drafts.sort(key=lambda r: r.recommendation_id)
    lines = [f"# Held-out retrieval check: {doc_id}", ""]
    retrieved_from: Counter[str] = Counter()
    same_actor_top1 = 0
    for d in drafts:
        hits = retriever.find(
            d.recommendation_text, d.target_actor_raw, k=k, exclude_documents=[doc_id]
        )
        for h in hits:
            retrieved_from[_doc(h.recommendation.recommendation_id)] += 1
        if hits and _actor_words(d.target_actor_raw) & _actor_words(
            hits[0].recommendation.target_actor_raw
        ):
            same_actor_top1 += 1
        lines.append(f"## {d.recommendation_id}  ({d.target_actor_raw})")
        lines.append(f"DRAFT: {_short(d.recommendation_text, 300)}")
        for i, h in enumerate(hits, 1):
            r = h.recommendation
            lines.append(
                f"- Match {i} [{_doc(r.recommendation_id)[:6]} p{r.source_page}, {r.target_actor_raw}, "
                f"cos {h.relevance:.2f}]: {_short(r.recommendation_text)}"
            )
        lines.append("")
    summary = [
        "## Facts that need no judgement",
        f"- drafts: {len(drafts)}; top-{k} results per draft; the held-out report is excluded",
        f"- results by report: {dict(retrieved_from)}",
        (
            "- top match shares at least one actor word with the draft's actor: "
            f"{same_actor_top1}/{len(drafts)} (the draft is embedded WITH its actor, so this is expected)"
        ),
        "",
    ]
    return "\n".join(lines[:2] + summary + lines[2:])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    doc = sys.argv[1]
    text = run(doc)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"heldout_{doc}.md").write_text(text, encoding="utf-8")
    print("\n".join(text.splitlines()[:12]))
