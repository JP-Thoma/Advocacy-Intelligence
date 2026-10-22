# Delivery plan: first release (minimum credible version)

Principle: real where it claims to be real, labelled where it is not. Nothing is described as evaluated beyond the small sample actually measured.

## Scope

The first release delivers capability 1, **find precedent**, for real: a draft goes in, real prior recommendations from real HRW reports come out as verbatim quotes with a link to the source. Comparison (capabilities 2 and 3) is deferred (D37), not faked.

| Kept (works) | Cut or simplified (stated openly) |
|---|---|
| Refugee trio only: 202409, 201804, 202110 | The other 6 reports stay in the manifest, not ingested |
| Minimal cleaner with the delete/join-only test (D26) | No Document Intelligence; scanned annex excluded (D27) |
| Extractor on the `chat` deployment with structured output, plus verbatim verifier | No controlled vocabularies: actor/topic are model-generated and labelled so; raw actor string kept |
| Records written to Blob (system of record) | No Cosmos DB, no near-duplicate grouping, no feedback buttons |
| Small gold check: ONE report labelled in full | Precedent-pair gold set replaced by synthetic edited drafts plus manual inspection |
| Retrieval by cosine similarity over embeddings, with a relevance threshold for clearly unrelated text (D42, D43) | AI Search written (Bicep, schema, service) but not deployed; no semantic ranker, no embedding A/B |
| `/api/check` wired to real retrieval; results show deterministic facts (date, document, actor as written) | **No LLM comparison.** The mock "differences" must not appear next to real results |
| Cached example and recording as a fallback | No hosting; local run (D32, D44) |

## Work packages

1. Ingestion on the trio: cleaner, extractor, verifier, records locally and in Blob; one report labelled as the gold check. **Done** (D38 to D41).
2. Retrieval: embeddings, retriever, `/api/check` wired, UI wording honest ("Wording not compared yet"). **Done** (D42).
3. Relevance threshold, so clearly off-topic text returns no results. **Done** (D43).
4. AI Search: deploy, build the index, hybrid query. **Not done.** Decision gate: if it does not return results within about 2.5 hours, keep the cosine retriever and present Search as the designed component.
5. Hosting behind a link for reviewers. **Not done** (D44).
6. Cached example from the real pipeline, marked as cached, plus a recorded run. **Not done.**

## Cost decision

AI Search Basic has a fixed monthly cost while it exists, billed in small increments; check the price shown when creating it. Raise the monthly budget deliberately before creating it, create it only when it is going to be used, and delete the resource group afterwards.

## Open items

- No labelled precedent pairs, so retrieval is looked at, not scored (no hit rate), and the threshold is calibrated on 44 texts only (D43).
- Extraction was gold-checked on one report (202409); the other two only by a bullet-glyph count.
- The Azure login must be redone each day (tokens last about a day; device code is blocked, see `docs/runbook.md` section 0).

## Cleanup

`az group delete --name rg-advocacy-poc`, and delete the demo user in the personal directory.
