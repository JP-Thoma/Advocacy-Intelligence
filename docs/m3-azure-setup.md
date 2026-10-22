# M3: Azure subscription and foundation

**Outcome: done.** The model decisions changed during execution; the log (D33 superseded, D36 confirmed) is authoritative, not the decision list below. What the run taught:
- Three gates decide whether a model is deployable: offered, not deprecated **for that deployment type** (`skus[].deprecationDate`), and quota above zero. `scripts/find_deployable_models.ps1` checks all three.
- A listed model with quota can still be deprecated; the model-level date can hide an already-deprecated deployment type.
- Fine-tune quota rows look like normal rows (same deployment-type names); exclude `usageName` containing `finetune`.
- The free trial had non-zero model quota here, contrary to community reports; verify, do not assume.
- `what-if` rejects a bad template before anything is created or billed.

Exit criterion: a local script calls the chat and embedding models and writes a blob, with no keys anywhere, and the whole environment can be created and destroyed from code.

Never paste subscription IDs, keys, tokens or card details into chat or commit them.

## Part A: you (about 45 minutes)

1. Create or reuse a personal Microsoft account with MFA. Do not use an employer email.
2. Sign up at the Azure free account page. Verify phone and card.
3. Portal: Cost Management + Billing, create a budget (small amount you accept losing) with email alerts at 50%, 80%, 100%. Alerts lag by hours; they warn, they do not stop spending.
4. Install the CLI and log in (PowerShell):
   ```
   winget install -e --id Microsoft.AzureCLI
   az login
   az account show --query "{name:name, state:state, offer:subscriptionPolicies.quotaId}" -o json
   az bicep install
   az provider register --namespace Microsoft.Storage
   az provider register --namespace Microsoft.CognitiveServices
   ```
   Open a new terminal after installing so `az` is on the PATH.
5. Check model availability and quota in your chosen EU region (replace REGION):
   ```
   az cognitiveservices usage list --location REGION -o table
   ```
   A free-trial subscription is expected to show zero for model quota (community reports, unverified). If so, upgrade to pay-as-you-go, then budget alert, low quota and short-lived resources are your only brakes.
6. Send the assistant: the `state` and `offer` values and the quota table, with no IDs.

## Part B: together (assistant writes, you explain each block back)

| Step | Resource (Bicep) | Why it exists |
|---|---|---|
| B1 | Resource group `rg-advocacy-poc` + tags | Lifecycle container; deleting it is the teardown button |
| B2 | Storage account + containers `raw`, `records` | System of record (D10) |
| B3 | Azure OpenAI account + chat deployment + embedding deployment, low capacity | Extraction, embeddings, comparison |
| B4 | RBAC role assignments to your user | Keyless access: Storage Blob Data Contributor, Cognitive Services OpenAI User |
| B5 | Budget as code (optional, after the portal one works) | Cost guardrail reproducible |
| B6 | `scripts/smoke_models.py` | Exit test: keyless chat call, embedding call, blob write |

## Decisions you must make before B2/B3 (answer with a reason)

1. **Shared keys and local auth.** Storage can disable shared-key access, and Azure OpenAI can disable key-based auth, forcing Entra tokens only. What does that buy, what does it cost you while developing, and would you turn it on from day one?
2. **Region and deployment type.** Which EU region, and a regional/EU data-zone deployment or a global one? Decide from the quota table and the data-residency statement you want to be able to make.
3. **Embedding model.** A smaller or larger embedding model? Think about vector dimensions, index size, cost per token, and what retrieval quality you can measure. Which would you start with, and what result would make you switch?
4. **Chat model for extraction.** Decision D29 says start small. Which size tier is available to you in the region, and what recall on the gold set would make you move up?
5. **Naming.** A convention such as `<type>-advocacy-poc-<env>`. Storage names must be globally unique and lowercase, so what suffix will you use?

## Technical facts the Bicep must respect (verify when writing)

- Azure OpenAI needs a custom subdomain on the account for Entra token authentication.
- Role assignments need the principal ID of your signed-in user (`az ad signed-in-user show`).
- Model names, versions and deployment SKUs available per region change; take them from the CLI/portal output, not from memory.
