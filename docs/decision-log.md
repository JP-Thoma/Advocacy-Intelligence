# Decision log

Status: D = decided, O = open. Every entry: decision, rationale, what would change it.

## Product

- **D1 Product:** HRW Recommendation Consistency Assistant. AI retrieves precedent and highlights differences; humans decide. *Why:* concrete task, no policy judgement by AI. Rejected: impact tracking, generic chat.
- **D2 Interaction:** manual invocation, two inputs: pasted recommendation text (primary) and uploaded report PDF (secondary, reuses the extractor). *Assumption, unvalidated:* HRW staff draft recommendations in some place we cannot see.
- **D3 Never paraphrase:** prior recommendations are always shown verbatim from source. Derived fields (normalised actor, action summary) are labelled model-generated.
- **D4 MVP cuts:** multiple document-type handling, reviewer feedback buttons, near-duplicate handling are deferred. *Caveat:* design records so grouping near-duplicates can be added later (repeated recommendations across years are the core signal).
- **D5 Corpus:** public HRW documents from the HRW website filtered for Lebanon. This is corpus scoping, NOT a retrieval filter. Retrieval must not hard-filter on geography.
- **D6 Must work or the POC is pointless:** reliable extraction of recommendations (verbatim, correctly bounded) and a comparison that does not invent differences.
- **D7 Matching:** semantic matches are enough (draft need not equal prior wording). Matches are always displayed as verbatim quoted spans. Primary matching dimensions: actor and issue; geography secondary. Each result shows which dimension matched.
- **D8 Corpus growth:** uploaded drafts are compared against the corpus but never auto-added. Only published reports may be added later.
- **D9 POC success question:** "Does this work with a corpus of ~10 previous reports?"
- **D10 System of record:** Blob Storage holds authoritative recommendation records (JSON); AI Search is a derived, rebuildable index. Cosmos DB deferred to the scale discussion.
- **D11 Normalisation is in scope:** actor and topic normalisation, using small controlled vocabularies built bottom-up from the corpus (not designed upfront). Raw strings are kept alongside normalised values.
- **D12 Trust signals:** (1) deterministic verbatim check, (2) link to exact source passage, (3) offline precision/recall on a hand-labelled set. No LLM self-reported confidence.
- **D13 Embedding:** enrich corpus recommendations (actor, topic, text) before embedding (option 2). Keep the verbatim text in a separate field. Whether the draft side is bare, enriched or both is decided by experiment (see build plan M3).
- **D14 Strength of language:** LLM-judged, but it must quote the operative phrase from both sides and code verifies the quotes. User's decision, over the proposal of a code lexicon; revisit if evaluation shows instability.
- **D15 Evaluation design:** leave-one-out on the newest report plus synthetic edited drafts with known differences.

- **D16 Metrics (delegated to assistant by user):** five metrics: verbatim match 100%; extraction recall >=90%; extraction precision >=85%; retrieval hit rate@5 >=90% of drafts; comparison faithfulness >=95%. Stop signal: recall <75% after iteration or hit rate <70%. Thresholds are initial and revisited after the gold set exists (small sample, wide uncertainty).
- **D17 Hosting (delegated):** review app on Azure Container Apps (scale to zero, Managed Identity). Ingestion is a local Python script writing to Blob for the POC, packaged to run later as a Container Apps job. Event-driven (queue + Functions/jobs) is the scale-up story. App Service is an acceptable alternative; not chosen.
- **D18 Index (delegated):** one recommendation-level AI Search index. Source context is stored in each record; no chunk index until evaluation shows a need.
- **D19 Embedding (delegated):** two vector fields per record (bare text, enriched text); both queried; the draft is parsed into editable fields shown to the user before comparison. Final variant chosen by experiment in M3.
- **D20 Full reports are PDF-only** (user observation), so PDF text extraction quality is the first thing to measure (M1). News releases and World Report chapters are HTML.

- **D21 UI stack:** FastAPI backend plus a thin frontend (plain HTML/JS or htmx served as static files; no React build chain). *Why:* the API is the contract and the UI is replaceable; user wants to learn FastAPI. *Cost:* second codebase; mitigated by keeping the frontend minimal. Supersedes the Streamlit assumption in D17 (hosting stays Container Apps).
- **D22 Key Vault:** not deployed in the POC (Managed Identity + RBAC means no secrets). Documented as a production control and as the key store for customer-managed keys in the Phase 8 confidential redesign.
- **D23 Raw data:** raw PDFs/HTML and records live in gitignored `data/` locally; a committed `data/sources.csv` manifest holds URL, title, date, type, retrieval date, hash. Blob becomes authoritative once ingestion uploads. Redistribution rights to be checked with Legal.

## Open

- O1 Definition of "relevant precedent" in labelling guidelines (tiers by actor / issue / geography).
- O5 Text extraction path: HTML parsing vs plain PDF extraction vs Document Intelligence. Resolved by measurement in M1.
- O6 Hosting. Proposal in build plan, awaiting the user's defence.
- O7 Metrics: user chose verbatim match, extraction recall, stop signal. Challenged: retrieval hit rate and comparison faithfulness are missing; extraction precision needed to stop recall being gamed.
- O8 Is a separate document-chunk index needed, or is one recommendation-level index enough?
- O9 Azure OpenAI model choices (extraction vs comparison vs embeddings).
