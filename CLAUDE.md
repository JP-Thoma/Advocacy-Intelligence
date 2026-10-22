# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository state

Working POC for the refugee trio (202409, 201804, 202110), state on 2026-10-22. Done and tested: ingestion (cleaner, segmenter, verifier, per-unit labeller, records in Blob; D38-D39), embeddings, and real "find precedent" retrieval wired into `/api/check` (cosine over a local vector file, with a relevance threshold that hides clearly unrelated text; D42, D43). The Azure foundation exists as code in `infra/` (Bicep: Storage + keyless Azure OpenAI in Sweden Central, deployments `chat` and `embedding`; AI Search written but behind `deploySearch=false` and **not deployed**). Without `ADVOCACY_RETRIEVAL=azure-cosine` the API still serves the mock fixture `src/advocacy_intel/fixtures/mock_check.json` (placeholder, clearly not HRW text); comparison/differences are not built (D37). **Resume here:** read `docs/runbook.md` (how to run everything, and the Azure sign-in workaround: device-code login is blocked), then `docs/delivery-plan.md` (status and what is left) and `docs/decision-log.md` (authoritative decisions, D1-D44). Planning docs live in `docs/` (`decision-log.md`, `build-plan.md`, `architecture.md`, `labelling-guide.md`); consult and update the decision log when a decision is made.

## Commands (Windows; Python 3.14 via `py`)

```
py -3.14 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"     # pip downloads can time out; add --default-timeout=120 --retries 8
.venv\Scripts\python -m pytest                      # all tests
.venv\Scripts\python -m pytest tests/test_api.py::test_health   # single test
.venv\Scripts\python -m ruff check src tests        # CI also runs: ruff format --check src tests
.venv\Scripts\python -m ruff format src tests       # fix formatting (CI fails on unformatted code)
.venv\Scripts\python -m uvicorn advocacy_intel.api.main:app --reload   # UI at http://127.0.0.1:8000
```

## Structure

`src/advocacy_intel/models/` holds the shared Pydantic contract (`Recommendation`, `Difference`, `Precedent`, `CheckResponse`); the API, the future ingestion/indexing/retrieval/comparison packages and the frontend all depend on it, so change the schema there first. The frontend (`web/`) is plain HTML/JS served by FastAPI and must insert external text with `textContent`, never `innerHTML`. Existing packages: `ingestion/` (slow batch: PDF → `clean.py` → `segment.py` → `verify.py` → `extract.py` labels → records via `ingest.py`; the model never writes a quote and never sees an ID, D38), `indexing/` (`schema.py` index definition as pure data, `embedding_text.py`, `vectors.py` local vector store, `service.py` Azure Search/embedding calls with lazy SDK imports and untested against a live service, `fallback.py` cosine), `retrieval/` (`precedents.py`), `evaluation/` (`gold_check.py`, `heldout.py`, `threshold_check.py`). Planned but not yet created: `comparison/`, `llm/`. Tests that read real HRW text skip themselves when `data/` is absent. `data/` is gitignored except `data/sources.csv` (manifest); `eval/gold/*` is gitignored except `TEMPLATE.yaml` (verbatim HRW text, D23); `prompts/` holds versioned prompts.

## What this is

A proof of concept: the **HRW Recommendation Consistency Assistant** on Azure, a reference implementation for an advocacy organisation such as Human Rights Watch.

A user drafting or reviewing a recommendation manually invokes "Check against previous HRW recommendations". The system retrieves relevant prior HRW recommendations (exact wording, source, date, target actor, geography, topic, context, relevance) and highlights differences in wording, scope, target actor, geography, framing, requested action, specificity, strength of language and safeguards.

Core principle: **AI retrieves precedent and highlights differences; humans determine the institutional position.**

Deliberately rejected directions (do not drift back into them):
- Implementation or impact tracking, including causal chains (recommendation → advocacy → policy change) and "implemented / partially implemented" labels.
- A generic "chat with HRW documents" assistant. A light chat surface is allowed, but the product is a recommendation-review tool.

The recommendation, not the document, is the core data object. Draft schema (keep flexible until tested): recommendation_id, recommendation_text, target_actor, action_requested, topic[], geography[], publication_date, document_title, document_type, source_url, source_context, source_chunk_id.

## HRW assumptions

Use only public facts about HRW (Investigate → Expose → Change; researchers work with programme leadership; Legal & Policy, Program, Advocacy and Communications can be involved in review and publication). Do **not** assume where recommendations are drafted, whether a formal recommendation-review stage exists, which software HRW uses, who owns consistency, or whether a precedent tool already exists. Hence the neutral interaction model: manual invocation only. No invented triggers such as document submission or background review.

## How to work in this repo: teaching mode

Act as implementation partner **and** architecture sounding board:

- Before any major decision: ask the user what they would choose and why, challenge the reasoning, explain trade-offs, and only then recommend. Be explicit about mistakes and do not agree automatically.
- Do not pick Azure services automatically. Each component needs a stated architectural purpose. Call out over-engineering and designs that are too generic. No code before the architecture is agreed.
- Periodically ask the user to explain the architecture from memory and to explain it for different audiences (executive, product manager, engineer).
- Phases: 1 framing → 2 architecture → 3 ingestion → 4 structured extraction → 5 retrieval and comparison → 6 UI → 7 evaluation → 8 security redesign (confidential HRW data) → 9 scale (100k documents, 500 daily users) → 10 presentation artefacts (diagram, use-case, responsible-AI and roadmap slides, demo).
- Record agreed decisions and their rationale in a decision log in the repo.

## Scope and constraints

- Likely start: Lebanon, about 10–30 public HRW documents of mixed types (reports, World Report chapters, submissions, news releases, briefings) spanning enough time to contain repeated or evolving recommendations. The corpus is chosen only after the data model and comparison logic are clear.
- Azure only. Candidates, not pre-selected: Azure OpenAI, AI Search, Blob/Data Lake, AI Foundry, Functions or Container Apps, Key Vault, Entra ID/Managed Identity, App Insights/Monitor, optional structured store only if justified. No AKS without a strong reason. UI: Streamlit, Gradio or FastAPI plus a light frontend.
- Open decisions to settle with the user: extraction at ingestion vs query time; one index vs several; AI Search only vs also a database; what is embedded; actor and topic normalisation; semantic similarity plus metadata filters; ranking and near-duplicate handling; deterministic vs LLM-generated parts of the comparison.
- Prefer small → working → measurable → defensible.

## Responsible-AI rules (apply to code, prompts and UI wording)

- Never output verdicts such as "inconsistent with HRW policy". Use wording like "This draft appears broader than previous recommendations. The difference may be intentional and should be reviewed by the author."
- No automated approval or rejection, and no invented institutional position.
- Exact prior wording is always shown verbatim with a citation and a link to the original publication. Source text and model interpretation are visually and structurally separate.
- Reviewer feedback (relevant / not relevant / intentionally different / useful precedent) may be captured for later evaluation and ranking.

## Evaluation (manually reviewed test set, not "the demo looks good")

Measure separately: recommendation extraction, metadata extraction (target actor, topic, geography, action requested), retrieval relevance of precedents, comparison faithfulness (differences described, not invented), and citation fidelity (every claim traceable to source).

## Security scenario to revisit (Phase 8)

The MVP is public-only, but later a separate exercise redesigns it for confidential internal material and interview notes that may identify vulnerable sources: source protection, document-level access, Entra ID/RBAC, managed identities, private endpoints, encryption, retention, logging and audit, prompt injection, data exfiltration, model access.

## Output conventions (organisation policy)

Default to English. Lead client-facing or external documents with an executive summary. Remind the user to review and validate anything intended for external use. Do not give legal, financial or regulatory advice, and flag regulated-data questions (e.g. GDPR) to the Data Privacy Officer.
