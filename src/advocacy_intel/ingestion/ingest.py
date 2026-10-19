"""M4 ingestion: PDF -> clean -> segment -> verify -> label -> records (+ coverage report).

Usage (repo root, after `az login`; PowerShell):
    $env:AZURE_OPENAI_ENDPOINT     = "<openAiEndpoint>"
    $env:AZURE_STORAGE_ACCOUNT_URL = "<storageBlobEndpoint>"   # only needed with --upload
    .venv\\Scripts\\python -m advocacy_intel.ingestion.ingest [--no-model] [--upload | --upload-only] [document_id ...]

Default documents are the refugee trio. `--no-model` skips labelling (no Azure needed).
Writes data/records/<id>.json and data/records/coverage.md (both gitignored: HRW text).
Exit code is 1 if any document has no section, a verification failure or a labelling failure.
"""

import csv
import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from advocacy_intel.models import Recommendation

from .clean import CLEANING_VERSION, CleanPage, clean_pages
from .extract import (
    PROMPT_VERSION,
    Labeller,
    LabelResult,
    Usage,
    azure_labeller,
    label_unit,
    load_prompt,
)
from .m1_probe import extract_pages
from .segment import SEGMENTER_VERSION, Segmentation, segment
from .text_checks import PageText, low_text_pages
from .verify import verify_units

RAW = Path("data/raw")
OUT = Path("data/records")
MANIFEST = Path("data/sources.csv")
TRIO = [
    "201804_lebanon_evictionssyrianrefugees",
    "202110_lebanon_syrianrefugeereturns",
    "202409_lebanon_syrianrefugeepushbacks",
]
API_VERSION = "2024-10-21"
CHAT_DEPLOYMENT = "chat"


@dataclass
class DocumentResult:
    doc_id: str
    pages: int
    segmentation: Segmentation
    records: list[Recommendation]
    no_text_pages: list[int]
    hash_ok: bool
    verification_failures: list[str] = field(default_factory=list)
    label_failures: list[str] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)

    @property
    def ok(self) -> bool:
        return (
            self.segmentation.found
            and bool(self.records)
            and self.hash_ok
            and not self.verification_failures
            and not self.label_failures
        )


def read_manifest() -> dict[str, dict[str, str]]:
    with MANIFEST.open(encoding="utf-8", newline="") as f:
        return {row["document_id"]: row for row in csv.DictReader(f)}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_record(unit, row: dict[str, str], labels: LabelResult | None, model: str):
    return Recommendation(
        recommendation_id=unit.unit_id,
        recommendation_text=unit.text,
        source_context=unit.actor_raw or "Recommendations",
        target_actor_raw=unit.actor_raw or "",
        action_requested=labels.labels.action_requested if labels and labels.labels else None,
        topic=list(labels.labels.topic) if labels and labels.labels else [],
        publication_date=row["date"],
        document_title=row["title"],
        document_type=row["document_type"],
        source_url=row["source_url"],
        source_page=unit.page,
        source_end_page=unit.end_page,
        cleaning_version=CLEANING_VERSION,
        segmenter_version=SEGMENTER_VERSION,
        extraction=f"{PROMPT_VERSION} / {model}" if labels else None,
    )


def process_document(
    doc_id: str,
    row: dict[str, str],
    raw: list[PageText],
    labeller: Labeller | None,
    model: str = CHAT_DEPLOYMENT,
    hash_ok: bool = True,
) -> DocumentResult:
    cleaned: list[CleanPage] = clean_pages(raw)
    seg = segment(doc_id, cleaned)
    verifications = verify_units(seg.units, cleaned, raw)

    system = load_prompt() if labeller else ""
    records, label_failures, usage = [], [], Usage()
    for unit in seg.units:
        result = label_unit(labeller, unit, system) if labeller else None
        if result:
            usage = Usage(
                usage.prompt_tokens + result.usage.prompt_tokens,
                usage.completion_tokens + result.usage.completion_tokens,
            )
            if result.labels is None:
                label_failures.append(f"{unit.unit_id}: {result.error}")
        records.append(build_record(unit, row, result, model))

    return DocumentResult(
        doc_id=doc_id,
        pages=len(raw),
        segmentation=seg,
        records=records,
        no_text_pages=low_text_pages(raw),
        hash_ok=hash_ok,
        verification_failures=[v.unit_id for v in verifications if not v.ok],
        label_failures=label_failures,
        usage=usage,
    )


def coverage_markdown(results: list[DocumentResult]) -> str:
    lines = [
        "| document | pages | section pages | units | verified | labelled | tokens in/out | ok |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        s = r.segmentation
        n = len(r.records)
        lines.append(
            f"| {r.doc_id} | {r.pages} | {s.section_start_page}-{s.section_end_page} | {n} "
            f"| {n - len(r.verification_failures)}/{n} | {sum(rec.action_requested is not None for rec in r.records)}/{n} "
            f"| {r.usage.prompt_tokens}/{r.usage.completion_tokens} | {'yes' if r.ok else 'NO'} |"
        )
    lines.append("\n## Details\n")
    for r in results:
        s = r.segmentation
        lines.append(f"### {r.doc_id}")
        lines.append(f"- section ended by: {s.ended_by!r}")
        lines.append(f"- segmentation warnings: {list(s.warnings) or 'none'}")
        lines.append(f"- source file hash matches manifest: {r.hash_ok}")
        lines.append(f"- pages with almost no extractable text (D27): {r.no_text_pages or 'none'}")
        lines.append(f"- verification failures: {r.verification_failures or 'none'}")
        lines.append(f"- labelling failures: {r.label_failures or 'none'}")
        lines.append("")
    return "\n".join(lines)


def write_outputs(results: list[DocumentResult]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for r in results:
        payload = {
            "document_id": r.doc_id,
            "records": [rec.model_dump(mode="json") for rec in r.records],
        }
        (OUT / f"{r.doc_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    (OUT / "coverage.md").write_text(coverage_markdown(results), encoding="utf-8")


def upload(doc_ids: list[str], credential) -> None:
    from azure.storage.blob import BlobServiceClient

    blobs = BlobServiceClient(os.environ["AZURE_STORAGE_ACCOUNT_URL"], credential=credential)
    container = blobs.get_container_client("records")
    for doc_id in doc_ids:
        data = (OUT / f"{doc_id}.json").read_bytes()
        container.upload_blob(f"recommendations/{doc_id}.json", data, overwrite=True)
        print(f"uploaded records/recommendations/{doc_id}.json")


def main(argv: list[str]) -> int:
    flags = {a for a in argv if a.startswith("--")}
    ids = [a for a in argv if not a.startswith("--")] or TRIO
    if "--upload-only" in flags:  # send the record files as they are; no re-run, no overwrite
        from azure.identity import DefaultAzureCredential

        upload(ids, DefaultAzureCredential())
        return 0
    manifest = read_manifest()

    credential = labeller = None
    if "--no-model" not in flags or "--upload" in flags:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider

        credential = DefaultAzureCredential()
    if "--no-model" not in flags:
        from openai import AzureOpenAI

        client = AzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            azure_ad_token_provider=get_bearer_token_provider(
                credential, "https://cognitiveservices.azure.com/.default"
            ),
            api_version=API_VERSION,
        )
        labeller = azure_labeller(client, CHAT_DEPLOYMENT)

    results = []
    for doc_id in ids:
        pdf = RAW / f"{doc_id}.pdf"
        print(f"{doc_id}: reading {pdf} ...", flush=True)
        row = manifest[doc_id]
        results.append(
            process_document(
                doc_id,
                row,
                extract_pages(pdf),
                labeller,
                hash_ok=_sha256(pdf) == row["sha256"],
            )
        )
        r = results[-1]
        print(f"  units={len(r.records)} ok={r.ok}", flush=True)

    write_outputs(results)
    print(f"wrote {OUT / 'coverage.md'}")
    if "--upload" in flags:
        upload([r.doc_id for r in results], credential)
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
