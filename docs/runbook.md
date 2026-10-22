# Runbook: how to run everything (state on 2026-10-22)

All commands are PowerShell from the repo root. Python is the project venv (`.venv\Scripts\python`).

## 0. Azure sign-in on the work laptop (read this first)

- `az login --use-device-code` does **not** work: the tenant's security defaults block the device-code flow (error AADSTS530035, decision D42). It fails for the personal account and for the demo user alike.
- Working route: `az login --tenant <tenant id>`. It opens a tab in the default (work) browser. Do not sign in there: copy the whole address from the address bar, close the tab, paste it into an **incognito** window, and sign in with the personal (gmx) account. The CLI receives the result on `localhost`, so this works from any browser on the same machine.
- Tokens expire after about a day. If a command prints `AADSTS`, `az logout` and log in again.
- Check: `az account show --query user.name -o tsv` prints the gmx address.
- Do not switch security defaults off and do not re-enable API keys (D35, D42).

## 1. Environment variables used below

```powershell
$env:AZURE_OPENAI_ENDPOINT     = "<openAiEndpoint>"
$env:AZURE_STORAGE_ACCOUNT_URL = "<storageBlobEndpoint>"
$env:ADVOCACY_RETRIEVAL        = "azure-cosine"      # only for the app and the checks below
$env:ADVOCACY_MIN_RELEVANCE    = "0.42"              # optional; default is 0.42 (D43)
```

The real values for this setup (tenant id, endpoints) are kept in `docs/local/environment.md`, which is gitignored. They can always be read again from the deployment outputs: `az deployment group show -g rg-advocacy-poc -n foundation --query properties.outputs`.

## 2. Pipeline, in order (each step is derived from the one before)

| Step | Command | Needs Azure | Output |
|---|---|---|---|
| Ingest (clean, segment, verify, label) | `.venv\Scripts\python -m advocacy_intel.ingestion.ingest` | yes (chat) | `data/records/<id>.json`, `data/records/coverage.md` |
| Same without the model | `... ingest --no-model` | no | unlabelled records (**overwrites** labelled files; do not run casually) |
| Upload records to Blob | `... ingest --upload-only` | yes (Blob) | `records/recommendations/<id>.json` (done for the trio on 2026-10-20) |
| Embed records | `.venv\Scripts\python -m advocacy_intel.indexing.vectors` | yes (embedding) | `data/index/vectors.json` (done 2026-10-21) |
| Gold check | `.venv\Scripts\python -m advocacy_intel.evaluation.gold_check 202409_lebanon_syrianrefugeepushbacks` | no | `data/records/gold_check_<id>.md` |
| Threshold calibration (is the cutoff still right?) | `.venv\Scripts\python -m advocacy_intel.evaluation.threshold_check 202409_lebanon_syrianrefugeepushbacks` | yes (embedding) | `data/records/threshold_check.md` |
| Held-out retrieval check | `.venv\Scripts\python -m advocacy_intel.evaluation.heldout 202409_lebanon_syrianrefugeepushbacks` | yes (embedding) | `data/records/heldout_<id>.md` |

Default documents are the refugee trio (201804, 202110, 202409). Raw PDFs are in `data/raw/`, never committed.

## 3. Run the app

Real retrieval (needs a valid Azure login, the `data/index/vectors.json` file and the two variables above):

```powershell
.venv\Scripts\python -m uvicorn advocacy_intel.api.main:app --reload     # http://127.0.0.1:8000
```

Without `ADVOCACY_RETRIEVAL` the app serves the mock fixture and shows the mock banner. If real retrieval is switched on but broken (expired login, missing or stale vector file), `/api/check` returns 503 with the reason; it never falls back to the mock silently.

## 4. Checks before committing (CI runs the same)

```powershell
.venv\Scripts\python -m ruff format --check src tests
.venv\Scripts\python -m ruff check src tests
.venv\Scripts\python -m pytest
git status          # data/ and eval/gold/*.yaml must NOT appear; only eval/gold/TEMPLATE.yaml is tracked
```

## 5. AI Search (designed, not deployed)

`infra/modules/search.bicep` is wired behind `deploySearch` (default false) in `infra/main.bicep`. Basic bills a fixed hourly amount while it exists. Raise the monthly budget first (docs/delivery-plan.md). Then:

```powershell
$me = az ad signed-in-user show --query id -o tsv      # object id of the signed-in user (gets the Search roles)
az deployment sub create --location swedencentral --template-file infra/main.bicep `
  --parameters principalId=$me chatModelName=gpt-4o chatModelVersion=2024-11-20 chatSkuName=Standard deploySearch=true
```

The chat settings repeat D36 (`gpt-4o` 2024-11-20, regional Standard, capacity 10 by default) and must match the existing deployment so the foundation is left unchanged; re-check them against the portal before running. `az ad signed-in-user show` may fail for a personal Microsoft account; if so, take the object id from Microsoft Entra, Users, your user. Run `az deployment sub what-if` first if unsure. After deploying: create the index with `indexing.service.create_index`, upload documents built with `indexing.schema.to_document`, and query with `indexing.service.hybrid_search`. **None of the `service.py` calls has been run against a live Search service.** Decision gate in the plan: if Search does not return results after about 2.5 hours, keep the cosine retriever and present Search as the designed component.

## 6. Teardown

`az group delete --name rg-advocacy-poc` removes everything (Storage, OpenAI, Search if created). Also delete the demo user created in the personal directory (Microsoft Entra, Users). Not yet exercised.

## 7. Known limits to state honestly

- Comparison (differences between draft and precedent) is not built (D37). The UI says "Wording not compared yet".
- Extraction was gold-checked on one report (202409, 33/33); the other two reports only by an independent bullet-glyph count. Small sample, not a general accuracy claim.
- 4 of 105 records have no model labels because Azure's content filter blocked them (D39); their quotes are still retrievable.
- A relevance threshold (0.42, D43) hides clearly unrelated text. It does not tell whether a true precedent exists, and it was calibrated on 44 texts; re-run `threshold_check` after any change of model, embedded text or corpus. No retrieval hit rate has been scored, because no precedent pairs are labelled.
- Retrieval runs as cosine over a local file; AI Search is designed and written but untested and not deployed.
- Tests that read real HRW text skip themselves when `data/` is absent (CI).
