# Build plan v0 (draft, pending decisions O5–O9)

Principle: small → working → measurable → defensible. Each milestone has an exit criterion; do not start the next until it is met.

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
| M0 | Corpus pick: skim recommendation sections, choose 10 reports (+1 held out) with repeated/evolving recommendations | Written list; at least 5 known recommendation pairs |
| M1 | Text extraction experiment on 2 PDFs and 2 HTML pages (reading order, headers/footers, footnotes, hyphenation, lists) | Decision on O5 with evidence |
| M2 | Hand-label gold set: all recommendations in 3 reports | Labelled file + labelling guideline (O1) |
| M3 | Extraction + verifier, measured against gold set; embedding variants A/B/C compared on retrieval | Recall/precision numbers; embedding choice by data |
| M4 | AI Search index, hybrid retrieval | Hit rate@5 on leave-one-out drafts |
| M5 | Comparison step with quote verification | Faithfulness on synthetic drafts |
| M6 | Minimal UI + deployment | End-to-end demo |
| M7 | Evaluation report; security redesign exercise; scale discussion | Interview artefacts |
