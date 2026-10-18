"""M3 exit test: keyless chat call, embedding call and blob write against the deployed foundation.

Authenticates with DefaultAzureCredential (your `az login` identity locally). No keys anywhere.

Set these from the deployment outputs first (PowerShell):
    $env:AZURE_OPENAI_ENDPOINT      = "<openAiEndpoint>"
    $env:AZURE_STORAGE_ACCOUNT_URL  = "<storageBlobEndpoint>"
Run:
    .venv\\Scripts\\python scripts\\smoke_models.py

Role assignments can take a few minutes to take effect; a 401/403 right after deployment usually means wait.
"""

import os
import sys

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.storage.blob import BlobServiceClient
from openai import AzureOpenAI

CHAT_DEPLOYMENT = "chat"
EMBEDDING_DEPLOYMENT = "embedding"
API_VERSION = "2024-10-21"


def require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"Missing environment variable {name} (see the docstring).")
    return value


def main() -> None:
    endpoint = require("AZURE_OPENAI_ENDPOINT")
    account_url = require("AZURE_STORAGE_ACCOUNT_URL")

    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )
    client = AzureOpenAI(
        azure_endpoint=endpoint, azure_ad_token_provider=token_provider, api_version=API_VERSION
    )

    chat = client.chat.completions.create(
        model=CHAT_DEPLOYMENT,
        messages=[{"role": "user", "content": "Reply with the single word: ready"}],
        max_tokens=10,
    )
    print("chat      :", chat.choices[0].message.content)

    embedding = client.embeddings.create(model=EMBEDDING_DEPLOYMENT, input="smoke test")
    print("embedding : dimensions =", len(embedding.data[0].embedding))

    blobs = BlobServiceClient(account_url, credential=credential)
    blobs.get_container_client("records").upload_blob(
        "smoke/hello.txt", b"smoke test", overwrite=True
    )
    print("blob      : wrote records/smoke/hello.txt")
    print("OK: keyless chat, embedding and blob write all worked.")


if __name__ == "__main__":
    main()
