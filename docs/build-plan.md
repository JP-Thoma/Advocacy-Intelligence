# Build plan v1 (revised 2026-10-16)

Principle: small → working → measurable → defensible. Each milestone has an exit criterion; do not start the next until it is met.

Change from v0: M0 (corpus and pairs) and M2 (gold labels) merged into one human labelling pass (see docs/labelling-guide.md), because both answer keys come from one read of the source. Corpus fixed at the 9 downloaded Lebanon reports (D24).

## Logical architecture

```
INGEST (batch)
HRW HTML / PDF -> text extraction -> LLM proposes recommendation spans + metadata
  -> verbatim verifier (code) -> normalise actor/topic -> record JSON (Blob, system of record)
  -> embed (enriched text) -> AI Search index (derived)

REVIEW (online)
draft text / uploaded PDF -> same extractor + verifier -> editable "how I understood your draft"
  -> hybrid retrieval (vector + keyword + boosts) -> top precedents with matched dimensions
  -> comparison (code for facts, LLM for language, every claim quote-verified)
  -> UI: verbatim prior wording, differences, source link
```

## Milestones

| # | Milestone | Exit criterion |
|---|---|---|
| M0 | Corpus manifest (`data/sources.csv`, 9 reports) and fixture-driven scaffold | Merged to main; manifest IDs match files; tests pass |
| M1 | Text extraction experiment on the PDFs (reading order, headers/footers, footnotes, hyphenation, lists), run before any LLM | Decision on Document Intelligence (O5) with evidence |
| M2 | Gold labels: all recommendations in the refugee trio (202409 held out, 201804, 202110) plus precedent links | Three YAML files in `eval/gold/`; at least 3 genuine precedent links, else revisit D24 |
| M3 | Extraction + verifier, measured against the gold set; embedding variants compared on retrieval | Recall/precision numbers; embedding choice by data |
| M4 | AI Search index, hybrid retrieval | Hit rate@5 on leave-one-out drafts |
| M5 | Comparison step with quote verification | Faithfulness on synthetic drafts |
| M6 | Real fixtures replace placeholders; UI polish pass; deployment | End-to-end demo |
| M7 | Evaluation report; security redesign exercise; scale discussion | Interview artefacts |

M1 and M2 can run in parallel: M2 is your reading, M1 is code on a separate branch.
