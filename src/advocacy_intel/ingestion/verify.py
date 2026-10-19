"""Verbatim verifier (D26, D38): every unit's text must be traceable to the document.

Two independent checks, both pure code:
1. found in the cleaned pages the unit claims to come from (guards segmentation and joining);
2. reachable from the RAW pages by deleting characters only (guards the cleaner).
"""

import re
from dataclasses import dataclass

from .clean import CleanPage
from .segment import Unit
from .text_checks import PageText


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


def _words(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _is_subsequence(small: str, big: str) -> bool:
    it = iter(big)
    return all(ch in it for ch in small)


@dataclass(frozen=True)
class Verification:
    unit_id: str
    in_cleaned_pages: bool
    traceable_to_raw: bool

    @property
    def ok(self) -> bool:
        return self.in_cleaned_pages and self.traceable_to_raw


def verify_units(
    units: tuple[Unit, ...], cleaned: list[CleanPage], raw: list[PageText]
) -> list[Verification]:
    results = []
    for u in units:
        span = range(u.page, u.end_page + 1)
        cleaned_text = _words(" ".join(p.text for p in cleaned if p.number in span))
        raw_text = _squash("".join(p.text for p in raw if p.number in span))
        results.append(
            Verification(
                u.unit_id,
                _words(u.text) in cleaned_text,
                _is_subsequence(_squash(u.text), raw_text),
            )
        )
    return results
