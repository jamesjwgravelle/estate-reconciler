"""Turn narrative documents into checkable statements.

This layer is rule-based on purpose: it is fast, free, reproducible, and gives the evals a
fixed baseline. An LLM extractor can be dropped in behind the same `statements()` interface
and scored against the same ground truth (see README, "Roadmap").
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterator, Optional

from .models import Evidence, TextDoc

# Document types we know how to recognise, both as produced documents and as references in letters.
DOC_TYPES: dict[str, tuple[str, re.Pattern]] = {
    "will": ("the Will", re.compile(r"\blast will\b|\bcopy of the will\b", re.I)),
    "t3_return": ("T3 trust returns", re.compile(r"\bT3\b|\btrust (income tax )?returns?\b", re.I)),
    "notice_of_assessment": ("CRA Notice of Assessment", re.compile(r"\bnotices? of assessment\b", re.I)),
    "clearance_certificate": ("CRA Clearance Certificate", re.compile(r"\bclearance certificate\b", re.I)),
    "inventory": ("inventory of estate assets", re.compile(r"\binventory\b", re.I)),
    "appraisal": ("property appraisal", re.compile(r"\bappraisal\b", re.I)),
    "statement_of_accounts": ("statement of accounts", re.compile(r"\bstatement of accounts\b", re.I)),
    "legal_invoice": ("legal invoice", re.compile(r"\binvoice\b", re.I)),
    "bank_records": ("bank records", re.compile(r"\bbank (statements?|records)\b", re.I)),
}

# "We are giving / will give you this document."
PROMISE = re.compile(r"\benclos|\battach|\bwill provide\b|\bwill be provided\b|\bwill forward\b|\bto follow\b", re.I)
# "We do not have this document yet."
PENDING = re.compile(
    r"\bstill waiting\b|\bawaiting\b|\bnot yet (been )?received\b|"
    r"\b(has|have) not (yet )?(been )?received\b", re.I)

MONEY = re.compile(r"\$\s?([0-9][0-9,]*(?:\.[0-9]{2})?)")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
STOP = set("the and for from with that this was were has have had its into net per via".split())


def tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) >= 3 and t not in STOP}


def classify_doc(name: str, lines: list[str]) -> Optional[str]:
    """Classify a produced document from its file name and its title line only.
    (Letters mention many document types in their body; that must not count as producing them.)"""
    first = next((ln for ln in lines if ln.strip()), "")
    probe = name.replace("_", " ").replace("-", " ") + " " + first
    # A Notice of Assessment for a T3 return mentions both types; the one named first wins.
    hits = [(m.start(), key) for key, (_, p) in DOC_TYPES.items() if (m := p.search(probe))]
    return min(hits)[1] if hits else None


@dataclass
class Statement:
    doc: TextDoc
    line_no: int
    text: str

    def cite(self) -> Evidence:
        return Evidence(self.doc.name, f"line {self.line_no}", self.text)

    def doc_types(self) -> list[str]:
        return [k for k, (_, p) in DOC_TYPES.items() if p.search(self.text)]

    def amounts(self) -> list[Decimal]:
        return [Decimal(m.replace(",", "")) for m in MONEY.findall(self.text)]


def statements(doc: TextDoc) -> Iterator[Statement]:
    """Sentences of a narrative document, each tagged with its source line."""
    for i, line in enumerate(doc.lines, start=1):
        for sentence in SENTENCE_END.split(line.strip()):
            if sentence:
                yield Statement(doc, i, sentence)
