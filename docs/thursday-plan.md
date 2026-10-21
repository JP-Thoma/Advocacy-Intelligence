# Thursday plan v2 (minimum credible demo)

Time: three sessions of about 4, 4 and 5 hours, plus some time on Thursday. Reserve about 3 hours of the total for interview preparation (diagram, responsible-AI and evaluation story, confidential-data redesign, scale, mock review).

Principle: real where it claims to be real, labelled where it is not. Nothing is described as evaluated beyond the small sample actually measured.

## Scope

The demo delivers capability 1, **find precedent**, for real: a draft goes in, real prior recommendations from real HRW reports come out as verbatim quotes with a link to the source. Comparison (capabilities 2 and 3) is deferred (D37), not faked.

| Keep (must work) | Cut or simplify (say so in the interview) |
|---|---|
| Refugee trio only: 202409, 201804, 202110 | The other 6 reports stay in the manifest, not ingested |
| Minimal cleaner with the delete/join-only test (D26) | No Document Intelligence; scanned annex excluded (D27) |
| Extractor on the `chat` deployment with structured output, plus verbatim verifier | No controlled vocabularies: actor/topic are model-generated and labelled so; raw actor string kept |
| Records written to Blob (system of record) | No Cosmos DB, no near-duplicate grouping, no feedback buttons |
| Small gold check: ONE report labelled in full | Precedent-pair gold set replaced by synthetic edited drafts plus manual inspection |
| One AI Search index, one enriched vector field, hybrid (vector + keyword) | No semantic ranker, no embedding A/B, no second vector field |
| `/api/check` wired to real retrieval; results show matched dimensions and deterministic facts (date, document, actor as written) side by side with the draft | **No LLM comparison.** The mock "differences" must not appear next to real results |
| Cached example and recording | No hosting; local demo (D32) |

## Sessions

Session 1 (4h): ingestion on the trio. Cleaner, extractor, verifier, records locally and in Blob. Label one report as the gold check (about 1 hour, yours). Measure recall and precision on it.

Session 2 (4h): AI Search (keyless, Bicep, budget raised), embeddings, index, hybrid query, held-out check using 202409 recommendations as drafts, `/api/check` wired. **Decision gate after about 2.5 hours:** if AI Search is not returning results, fall back to cosine similarity over the stored embeddings and present AI Search as the designed component, honestly.

Session 3 (5h): make the UI honest (remove or gate mock comparison output; show real facts), save the cached example, record a run. Then at least 2.5 hours of interview preparation, ending with a mock architecture review.

Thursday: rehearsal only. No new features.

## Cost decision

AI Search Basic has a fixed monthly cost while it exists, billed in small increments; check the price shown when creating it. Raise the monthly budget deliberately before creating it (user agreed; suggested 100), create it in Session 2, delete the resource group after the demo.

## Status at the end of 2026-10-21 (about 03:00; interview is Thursday 2026-10-22)

Done and tested (100 tests, ruff clean): Session 1 in full (cleaner, segmenter, verifier, per-unit labeller, records in Blob, gold check 33/33 on 202409) and the guaranteed part of Session 2: embeddings, cosine retrieval, `/api/check` real mode, UI wording "Wording not compared yet". See `docs/runbook.md` for how to run it and `docs/decision-log.md` D38-D42 for the reasons.

Not done:
- AI Search is written (Bicep behind `deploySearch=false`, index schema, service functions) but **not deployed and never run live**. Decision gate unchanged: only if at least 2 hours remain, the budget has been raised, and it does not cost the interview preparation. Otherwise present it as the designed component.
- The real UI was seen working by the user at night; a careful review is planned for the morning. The standing check list: no mock banner, "Wording not compared yet" on cards, quote with source, page and link, nothing from the fixture beside real results.
- Session 3 items: save a cached example from the real pipeline (marked as cached) and record a run; interview preparation of at least 2.5 hours (architecture diagram, responsible-AI story, confidential-data redesign, scale to 100k documents and 500 daily users, mock architecture review).
- No labelled precedent pairs, so retrieval is looked at, not scored; no relevance cutoff (D31, D42).
- The Azure login must be redone on the day (tokens last about a day, device code is blocked: runbook section 0). Do this well before the interview and test `/api/check` once.

Suggested order for the remaining time: (1) review the UI and run one end-to-end check, (2) commit and merge, (3) cached example plus recording, (4) interview preparation, (5) AI Search only if time is left over. Thursday: rehearsal only, no new features.

Cleanup after the demo: `az group delete --name rg-advocacy-poc` and delete the demo user in the personal directory.
