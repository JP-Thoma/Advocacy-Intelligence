# Build plan v3 (revised 2026-10-18)

Principle: small → working → measurable → defensible. Each milestone has an exit criterion; do not start the next until it is met.

Changes from v2: the demo is live from the user's own machine (D32), so app hosting is a stretch goal, not a milestone. Azure backing services (OpenAI, Search, Blob) are needed regardless and come first. Testing is a continuous track plus a later evaluation milestone.

## Logical architecture

```
INGEST (batch, local script)
HRW PDF -> text extraction -> deterministic cleaner -> LLM proposes quoted spans + metadata
  -> verbatim verifier (code) -> normalise actor/topic -> record JSON (Blob, system of record)
  -> embed (enriched + bare text) -> AI Search index (derived)

REVIEW (online, app runs locally)
draft text / uploaded file -> split -> parse draft (editable) -> hybrid retrieval
  -> top precedents with matched dimensions
  -> comparison (code for facts, LLM for language, every claim quote-verified)
  -> UI: verbatim prior wording, differences, source link
```

Local app authenticates to Azure with the developer identity (`az login`, `DefaultAzureCredential`) and RBAC roles. This is the same code path managed identity uses in the cloud. No keys in code or config.

## Block 1: backend wired to the frontend

Already real (deterministic, no Azure): `/api/split`, `/api/extract`, static frontend. Still mock: `/api/check`.

Rule: the contract in `src/advocacy_intel/models/` stays stable. Each step replaces one mock behind the same endpoint. The mock banner stays until nothing is mocked.

| Step | Replaces | Exit |
|---|---|---|
| Cleaner | new | Deterministic cleaning with the "delete/join only" invariant test (D26) |
| Extractor + verifier | new, offline | Records with source page and `cleaning_version`; per-document no-text page report (D27) |
| Index + retrieval | mock precedents | Hybrid query returns real records for a draft |
| Comparison | mock differences | Code facts + LLM language dimensions, quotes verified |
| `/api/check` | `_load_mock` | Mock banner removed only when nothing is mocked |

## Block 2: Azure backing services (hosting is a stretch goal)

| Step | Content | Exit |
|---|---|---|
| Subscription | New personal subscription (D31), budget alert, resource providers registered, Azure CLI | `az account show` works; budget alert exists |
| Foundation as code (Bicep) | Resource group `rg-advocacy-poc` with tags; Storage (Blob); Azure OpenAI (chat + embedding deployments, low quota); AI Search created only at the retrieval milestone | Create and destroy reproducibly |
| Identity | RBAC roles for the developer identity: OpenAI user, Search data contributor, Blob data contributor | App runs with no secrets |
| Stretch: hosting | Dockerfile, container registry, Container Apps, App Insights, sign-in | Only if time remains; otherwise documented in the architecture diagram |

Cost rules: budget alert first; low token quota on model deployments; create AI Search when M6 starts; delete the resource group after the demo.

## Block 3: testing

Continuous (starts now, runs on every PR):
- Unit tests for pure logic (cleaner, verifier, deterministic comparisons, splitting).
- API tests with fixtures (existing).
- CI gate on pull requests: `pytest` and `ruff`.

Evaluation (after the real pipeline exists, before any quality claim):
- Gold labels for the refugee trio (202409 held out, 201804, 202110) plus precedent links.
- Extraction recall/precision, retrieval hit rate@5, comparison faithfulness, citation fidelity, per D16.
- Anything real shown before this is labelled unevaluated.

Demo fallback (D32): a cached example produced by the real pipeline and marked as cached, plus a recorded run. Never hand-written.

## Milestones

| # | Milestone | Exit criterion |
|---|---|---|
| M0 | Corpus manifest, fixture-driven scaffold | Done |
| M1 | PDF text extraction probe | Done; decisions D25-D27 |
| M2 | CI gate (pytest + ruff on PRs) | CI green on a PR |
| M3 | Azure subscription + foundation as code (Storage, OpenAI) + RBAC + budget alert | **Done.** Keyless chat (`gpt-4o`, regional, Sweden Central), embedding (3072 dims) and blob write verified by `scripts/smoke_models.py`; destroy path is `az group delete` (not yet exercised) |
| M4 | Ingestion: cleaner, extractor (structured output), verifier, records in Blob | Records for the 3 trio reports; invariant test green; coverage report |
| M5 | Gold labelling + extraction evaluation | Recall/precision measured; prompt tuning only after this |
| M6 | AI Search index + hybrid retrieval, embedding variants compared | Hit rate@5 on leave-one-out drafts |
| M7 | Comparison with quote verification; replace `/api/check` mock | Faithfulness measured; mock banner removed; cached demo example saved |
| M8 | Security redesign (confidential HRW data), scale discussion, interview artefacts; stretch: hosting | Diagram, slides, demo |

M5 labelling can run in parallel with M2-M4; it must finish before the extractor prompt is tuned.
