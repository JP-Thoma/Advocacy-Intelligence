"""Extraction check: compare the hand-labelled gold file with the extracted records (M5).

Usage (repo root):
    .venv\\Scripts\\python -m advocacy_intel.evaluation.gold_check 202409_lebanon_syrianrefugeepushbacks

Reads eval/gold/<id>.yaml and data/records/<id>.json, writes data/records/gold_check_<id>.md.

Definitions (stated so the numbers cannot be gamed):
- A gold entry and a record MATCH when their text is the same after normalisation (case, spacing,
  punctuation and digits ignored), allowing a small difference for copy artefacts. Each side
  matches at most once.
- Recall    = matched gold entries / all gold entries      (did we miss any?)
- Precision = matched records / all records                (did we invent or over-split any?)
- For matched pairs the page and the actor heading are compared separately.
Small samples: report counts, not just percentages.
"""

import json
import re
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

import yaml

GOLD = Path("eval/gold")
RECORDS = Path("data/records")
VERBATIM = 0.98  # normalised similarity at or above this counts as the same text
NEAR = 0.85  # between NEAR and VERBATIM: listed for a human to decide, not counted as a match


def normalise(text: str) -> str:
    """Lowercase letters only: ignores spacing, punctuation, digits (footnote numbers) and case."""
    return re.sub(r"[^a-z]+", "", text.casefold())


def actor_key(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()


@dataclass(frozen=True)
class Item:
    key: str  # id
    text: str
    page: int | None
    actor: str


@dataclass(frozen=True)
class Pair:
    gold: Item
    record: Item
    similarity: float


@dataclass(frozen=True)
class CheckResult:
    matched: list[Pair]
    near: list[Pair]  # candidate pairs below VERBATIM, for human review
    missed_gold: list[Item]  # recall misses
    extra_records: list[Item]  # precision misses
    gold_total: int
    record_total: int

    @property
    def recall(self) -> float:
        return len(self.matched) / self.gold_total if self.gold_total else 0.0

    @property
    def precision(self) -> float:
        return len(self.matched) / self.record_total if self.record_total else 0.0

    @property
    def page_mismatches(self) -> list[Pair]:
        return [p for p in self.matched if p.gold.page != p.record.page]

    @property
    def actor_mismatches(self) -> list[Pair]:
        return [p for p in self.matched if actor_key(p.gold.actor) != actor_key(p.record.actor)]


def compare(gold: list[Item], records: list[Item]) -> CheckResult:
    """Greedy one-to-one matching by descending similarity."""
    g_norm = {g.key: normalise(g.text) for g in gold}
    r_norm = {r.key: normalise(r.text) for r in records}
    scored = sorted(
        (
            (SequenceMatcher(None, g_norm[g.key], r_norm[r.key], autojunk=False).ratio(), g, r)
            for g in gold
            for r in records
        ),
        key=lambda t: -t[0],
    )
    used_g: set[str] = set()
    used_r: set[str] = set()
    matched: list[Pair] = []
    near: list[Pair] = []
    for sim, g, r in scored:
        if g.key in used_g or r.key in used_r or sim < NEAR:
            continue
        used_g.add(g.key)
        used_r.add(r.key)
        (matched if sim >= VERBATIM else near).append(Pair(g, r, sim))
    return CheckResult(
        matched=sorted(matched, key=lambda p: p.gold.key),
        near=sorted(near, key=lambda p: p.gold.key),
        missed_gold=[g for g in gold if g.key not in used_g],
        extra_records=[r for r in records if r.key not in used_r],
        gold_total=len(gold),
        record_total=len(records),
    )


def load_gold(path: Path) -> tuple[dict, list[Item]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    items = [
        Item(
            str(r["id"]),
            " ".join(str(r["text"]).split()),
            r.get("page"),
            str(r.get("target_actor_as_written", "")),
        )
        for r in data["recommendations"]
    ]
    return data, items


def load_records(path: Path) -> list[Item]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        Item(
            r["recommendation_id"],
            r["recommendation_text"],
            r["source_page"],
            r["target_actor_raw"],
        )
        for r in payload["records"]
    ]


def _short(text: str, n: int = 90) -> str:
    return text if len(text) <= n else text[:n] + "..."


def report_markdown(doc_id: str, header: dict, res: CheckResult) -> str:
    out = [
        f"# Gold check: {doc_id}",
        f"Gold scope: {header.get('scope')!r}; labelled by {header.get('labelled_by')!r}.",
        "",
        "| measure | value |",
        "|---|---|",
        f"| gold entries / extracted records | {res.gold_total} / {res.record_total} |",
        f"| matched | {len(res.matched)} |",
        f"| recall (gold found) | {len(res.matched)}/{res.gold_total} = {res.recall:.0%} |",
        f"| precision (records real) | {len(res.matched)}/{res.record_total} = {res.precision:.0%} |",
        f"| matched with a different page | {len(res.page_mismatches)} |",
        f"| matched with a different actor heading | {len(res.actor_mismatches)} |",
        f"| near matches needing a human decision | {len(res.near)} |",
        "",
    ]

    def section(title, rows):
        out.append(f"## {title}")
        out.extend(rows or ["- none"])
        out.append("")

    section(
        "Gold entries with no matching record (missed)",
        [f"- {g.key} p{g.page}: {_short(g.text)}" for g in res.missed_gold],
    )
    section(
        "Records with no matching gold entry (extra)",
        [f"- {r.key} p{r.page}: {_short(r.text)}" for r in res.extra_records],
    )
    section(
        "Near matches (similarity below the verbatim bar; decide by eye)",
        [
            f"- {p.gold.key} vs {p.record.key} ({p.similarity:.2f})\n"
            f"  - gold:   {_short(p.gold.text, 200)}\n  - record: {_short(p.record.text, 200)}"
            for p in res.near
        ],
    )
    section(
        "Page differences",
        [
            f"- {p.gold.key}: gold p{p.gold.page}, record p{p.record.page}"
            for p in res.page_mismatches
        ],
    )
    section(
        "Actor heading differences",
        [
            f"- {p.gold.key}: gold {p.gold.actor!r}, record {p.record.actor!r}"
            for p in res.actor_mismatches
        ],
    )
    return "\n".join(out)


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    doc_id = argv[0]
    header, gold = load_gold(GOLD / f"{doc_id}.yaml")
    res = compare(gold, load_records(RECORDS / f"{doc_id}.json"))
    text = report_markdown(doc_id, header, res)
    (RECORDS / f"gold_check_{doc_id}.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
