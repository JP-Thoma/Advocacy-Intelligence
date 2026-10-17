"""M1 experiment: plain PDF text extraction + problem heuristics.

Usage (from repo root):
    python -m advocacy_intel.ingestion.m1_probe [document_id ...]

Reads data/raw/<id>.pdf, writes data/extracted/<id>.txt (page-marked) and
data/extracted/m1_summary.md. Both stay gitignored: they contain HRW text.
"""

import sys
from pathlib import Path

import pdfplumber

from .text_checks import (
    PageText,
    glued_footnotes,
    hyphen_breaks,
    low_text_pages,
    recommendation_headings,
    repeated_edge_lines,
)

RAW = Path("data/raw")
OUT = Path("data/extracted")


def extract_pages(pdf_path: Path) -> list[PageText]:
    with pdfplumber.open(pdf_path) as pdf:
        return [PageText(i, page.extract_text() or "") for i, page in enumerate(pdf.pages, 1)]


def summarise(doc_id: str, pages: list[PageText]) -> dict:
    full = "\n".join(p.text for p in pages)
    heads = recommendation_headings(pages)
    return {
        "doc": doc_id,
        "pages": len(pages),
        "chars": len(full),
        "low_text_pages": low_text_pages(pages),
        "edge_repeats": repeated_edge_lines(pages)[:4],
        "glued_footnotes": glued_footnotes(full),
        "hyphen_breaks": hyphen_breaks(full),
        "rec_pages": heads["recommendations"],
        "actor_heading_pages": heads["actor_headings"],
    }


def write_text(doc_id: str, pages: list[PageText]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    body = "\n\n".join(f"=== page {p.number} ===\n{p.text}" for p in pages)
    (OUT / f"{doc_id}.txt").write_text(body, encoding="utf-8")


def write_summary(rows: list[dict]) -> None:
    lines = [
        "| document | pages | low-text pages | glued footnotes | hyphen breaks | rec. heading pages | 'To the…' pages |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['doc']} | {r['pages']} | {len(r['low_text_pages'])} | {len(r['glued_footnotes'])} "
            f"| {r['hyphen_breaks']} | {r['rec_pages'][:6]} | {r['actor_heading_pages'][:6]} |"
        )
    lines.append("\n## Repeated header/footer candidates\n")
    for r in rows:
        lines.append(f"- {r['doc']}: {r['edge_repeats']}")
    lines.append("\n## Glued-footnote samples (first 3 per document)\n")
    for r in rows:
        lines.append(f"- {r['doc']}: {r['glued_footnotes'][:3]}")
    (OUT / "m1_summary.md").write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str]) -> None:
    ids = argv or sorted(p.stem for p in RAW.glob("*.pdf"))
    rows = []
    for doc_id in ids:
        print(f"extracting {doc_id} ...", flush=True)
        pages = extract_pages(RAW / f"{doc_id}.pdf")
        write_text(doc_id, pages)
        rows.append(summarise(doc_id, pages))
    write_summary(rows)
    print(f"done: {len(rows)} documents -> {OUT}")


if __name__ == "__main__":
    main(sys.argv[1:])
