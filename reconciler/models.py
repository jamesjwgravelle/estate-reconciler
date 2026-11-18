"""Core data types. Every Finding carries Evidence that points at a document and a location."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from decimal import Decimal
from typing import Optional


@dataclass
class Evidence:
    doc: str        # file name relative to the matter folder
    locator: str    # e.g. "row D-04" or "line 7"
    quote: str      # the exact text relied on


@dataclass
class Finding:
    type: str       # machine-readable category; must have an entry in catalog.CATALOG
    key: str        # stable identifier within the type (used by the evals)
    severity: str   # "high" | "medium" | "low"
    title: str
    detail: str
    evidence: list[Evidence] = field(default_factory=list)
    # Dollars in question, if the finding has a figure. Always positive. Whether it is added
    # to the report's total is decided per type in catalog.CATALOG, not here.
    amount: Optional[Decimal] = None
    # Signed effect on (bank balance - stated balance on hand). Lets the report show that the
    # individual items add up to the overall gap. None if the finding does not move the balance.
    balance_effect: Optional[Decimal] = None
    # One or two sentences a client could read. Falls back to the title if empty.
    plain: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("amount", "balance_effect"):
            if d[k] is not None:
                d[k] = f"{d[k]:.2f}"
        return d


@dataclass
class Txn:
    """One money movement, from either the executor's accounts or the bank record."""
    id: str
    date: date
    direction: str  # "in" | "out"
    description: str
    amount: Decimal
    doc: str
    locator: str

    def cite(self) -> Evidence:
        return Evidence(self.doc, self.locator,
                        f"{self.date.isoformat()} | {self.description} | ${self.amount:,.2f}")


@dataclass
class TextDoc:
    """A letter, notice, will or other narrative document, kept line by line for citation."""
    name: str
    lines: list[str]
    doc_type: Optional[str] = None   # a key from extract.DOC_TYPES, if recognised
    date: Optional[date] = None
    reprinted: Optional[date] = None   # date a copy was reprinted, if the document says so


@dataclass
class Matter:
    root: str
    accounts: list[Txn] = field(default_factory=list)
    bank: list[Txn] = field(default_factory=list)
    bank_closing: Optional[Decimal] = None
    bank_doc: Optional[str] = None
    summary: dict[str, tuple[Decimal, Evidence]] = field(default_factory=dict)
    texts: list[TextDoc] = field(default_factory=list)
