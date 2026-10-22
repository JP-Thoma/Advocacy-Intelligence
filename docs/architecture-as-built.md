# Architecture as built (state on 2026-10-22)

`docs/architecture.md` is the plan (a hypothesis). This file states what exists, what is only written, and what is missing. Say which is which.

Legend: `[x]` built and tested   `[~]` written but not deployed or never run live   `[ ]` missing or deliberately deferred

## 1. The five layers (one picture)

```
┌─ CHANNELS / APPLICATION ─ what the user touches ───────────────────────────────────────────────
│ [x] Web UI (web/: plain HTML + JS, text inserted with textContent only)
│ [x] Multi-recommendation review: paste text, or upload .docx/.pptx/.pdf/.txt, pick recommendations
│ [x] Result cards: verbatim prior quote, source, page, link, "Read as" correction form
│ [x] Honest wording: "Wording not compared yet"; mock banner only when the fixture is served
│ [ ] Hosting (runs locally)   [ ] User sign-in   [ ] Reviewer feedback buttons   [ ] Comparison view
└────────────────────────────────────────────────────────────────────────────────────────────────
                                              │  HTTP (JSON, contract = Pydantic models)
                                              ▼
┌─ ORCHESTRATION ─ who calls what, in which order, and what happens on failure ──────────────────
│ ONLINE   [x] FastAPI: /api/check  /api/split  /api/extract  /api/health
│          [x] /api/check: embed draft -> rank by cosine -> drop weak matches -> Precedent objects
│          [x] switch: ADVOCACY_RETRIEVAL=azure-cosine, else mock fixture; any failure = 503
│ BATCH    [x] ingest.py: clean -> segment -> verify -> label -> records -> coverage report
│          [x] vectors.py: records -> embedding text -> vectors file
│ CHECKS   [x] gold_check.py (extraction vs hand labels)   [x] heldout.py (retrieval, eyeball)
│ [ ] Comparison step (differences)   [ ] Draft parsing   [ ] Feedback capture   [ ] Monitoring
└────────────────────────────────────────────────────────────────────────────────────────────────
                         │ calls models                                   │ reads / writes
                         ▼                                                ▼
┌─ AI SERVICES ─ models, and the code that guards them ──┐  ┌─ DATA LAYER ─ what is stored, where ─
│ Azure OpenAI (Sweden Central, keyless)                  │  │ SYSTEM OF RECORD
│ [x] chat = gpt-4o: one call per unit -> action + topic  │  │ [x] 105 records as JSON, Blob
│     structured output, temperature 0, content filter ON │  │     records/recommendations/ (3 files)
│ [x] embedding = text-embedding-3-large (3072 dims)      │  │ [x] data/sources.csv manifest (hashes)
│     records and the user's draft, same text shape       │  │ LOCAL, DERIVED, REBUILDABLE
│ NOT AI (plain code, on purpose):                        │  │ [x] data/records/*.json (copy the app reads)
│ [x] cleaner  [x] segmenter  [x] verbatim verifier       │  │ [x] data/index/vectors.json (6.7 MB)
│ [~] AI Search: vector + keyword (hybrid), written       │  │ [x] raw PDFs data/raw (not committed)
│ [ ] Comparison LLM   [ ] Draft-parsing LLM              │  │ [~] AI Search index (schema written)
│ [ ] Semantic ranker (cut)  [ ] Doc Intelligence (cut)   │  │ [ ] Feedback store  [ ] other 6 reports
└─────────────────────────────────────────────────────────┘  └──────────────────────────────────────
                         │                                                │
                         ▼                                                ▼
┌─ PLATFORM ─ the cloud foundation everything sits on ───────────────────────────────────────────
│ [x] Personal Azure subscription (D31), resource group rg-advocacy-poc, EU region, tags, budget alert
│ [x] Infrastructure as code: Bicep (infra/), create and destroy reproducibly
│ [x] Storage account: shared keys OFF, Entra only, containers raw/ and records/
│ [x] Azure OpenAI account: API keys OFF; deployments named by role: chat (cap 10), embedding (cap 20)
│ [x] Access: RBAC roles for the developer identity (Blob Data Contributor, OpenAI User), no secrets
│ [x] CI: GitHub Actions runs pytest + ruff on every pull request (100 tests)
│ [~] AI Search Basic: Bicep module behind deploySearch=false, NOT deployed
│ [ ] Hosting (Container Apps)  [ ] Managed identity in the cloud  [ ] Monitoring (App Insights)
│ [ ] Private endpoints / network isolation (phase 8)   [ ] Entra sign-in for users
└────────────────────────────────────────────────────────────────────────────────────────────────
```

## 2. One request, step by step (what happens when you press "Check")

```
 BROWSER (Channels)            FASTAPI (Orchestration)              AZURE / FILES
 ─────────────────             ───────────────────────              ──────────────
 1 user selects a
   recommendation
   (+ optional actor)
        │  POST /api/check
        └────────────────────▶ 2 validate request (Pydantic)
                               3 retriever configured?
                                  no  -> serve mock fixture (banner on)
                                  yes ▼
                               4 build two draft texts:
                                 with actor (for ranking) and
                                 without actor (for the cutoff);
                                 no model labels added
                                            ──────────────────────▶ 5 embedding model (one call,
                                            ◀──────────────────────   two texts, 3072 numbers each)
                               6 cosine similarity against 105 stored
                                 vectors (local file), top 5 by the
                                 with-actor score
                               6b drop any of the 5 whose no-actor
                                 similarity is below 0.42 (D43)
                               7 look up the full records (verbatim
                                 quote, page, URL)                     <- local records JSON
                               8 build response:
                                 precedents (possibly none), hidden
                                 count, differences = [],
                                 comparison_performed = false
        ◀──────────────────────  (any error in 4-7 = HTTP 503 with
 9 cards show: Match 1..5,        the reason; never a silent mock)
   quote, source link,
   "Wording not compared yet"
```

## 3. How the data got there (batch, run before the demo)

```
 PDF (data/raw)  ─▶ text per page ─▶ CLEAN ─▶ SEGMENT ─▶ VERIFY ─▶ LABEL ─▶ RECORDS ─▶ BLOB
 pdfplumber          (page-marked)  delete/   find the     quote is   chat model  JSON per    system of
                                    join     section,     in cleaned  adds action document    record
                                    only     one unit     pages AND   + topic,
                                    (D26)    per bullet   reachable   one call
                                             (D38)        from raw    per unit
                                                          pages
                                                                          │
                                  records ─▶ embedding text ─▶ embedding model ─▶ vectors.json
                                             (actor + quote + labels, D41)        (derived)
```

## 4. Trust map: who is allowed to write what (the responsible-AI picture)

| Piece of what the user sees | Written by | Guarantee |
|---|---|---|
| The prior quote | **code** (copied from the cleaned report text) | verbatim, and checked against the raw pages (D26, D38) |
| Source, page, date, link, actor as written | **code** (manifest and the report's own headings) | traceable, not inferred |
| Requested action, topics | **model** (gpt-4o, one unit at a time) | none yet beyond a schema check; shown as model-generated; can contain an invented topic (seen once) |
| Which precedents appear, and their order | **embedding model + math** | an ordering, not a measure of correctness (D31); results below a 0.42 similarity are hidden (D43) |
| Differences between draft and precedent | **nobody yet** | deliberately not built (D37) |
| The institutional position | **humans** | the tool never states one |

## 5. What is real, what is only designed

| Capability | State |
|---|---|
| Find precedent for a draft, with exact quotes and links | real, over 105 recommendations from 3 reports |
| Extraction accuracy | checked by hand on one report: 33 of 33; other two by bullet count only |
| Retrieval quality | looked at, not scored (no labelled pairs); strong on repeats; clearly off-topic text returns nothing (threshold calibrated on 44 texts), weakly related text still returns weak neighbours |
| Comparison of wording | not built, by decision |
| AI Search (hybrid) | designed and written, not deployed; the cosine retriever is the working stand-in |
| Hosting, sign-in, monitoring, private network | designed for, not built; local demo (D32) |
| Scale (100k documents, 500 daily users) and confidential data (phase 8) | discussion only |

Where the running app reads from: **the local copy** of the records and vectors. Blob holds the system of record by design, but the app does not read Blob today. Do not claim otherwise.
