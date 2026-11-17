"""Read a lawyer's invoice (a text document) into time entries and stated totals.

Expected shape, one time entry per line, then the totals:

    2023-04-04 | JW | Review and file probate application | 1.50 | 450.00 | 675.00
    Fees: $13,000.00
    HST (13%): $1,690.00
    Total due: $14,690.00

Amounts on time entries are before tax. A negative entry is a credit.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from .models import Evidence, Matter, TextDoc

ENTRY = re.compile(r"^(\d{4}-\d{2}-\d{2})\s*\|\s*(\w+)\s*\|\s*(.+?)\s*\|\s*(-?[\d.]+)\s*\|\s*([\d.,]+)\s*\|\s*(-?[\d,]+\.\d{2})\s*$")
MONEY = re.compile(r"\$\s?([0-9][0-9,]*\.[0-9]{2})")
LABELS = {"fees:": "fees", "hst": "tax", "total due:": "total"}


@dataclass
class TimeEntry:
    date: date
    timekeeper: str
    description: str
    hours: Decimal
    rate: Decimal
    amount: Decimal
    evidence: Evidence


@dataclass
class Invoice:
    doc: TextDoc
    entries: list[TimeEntry] = field(default_factory=list)
    stated: dict[str, tuple[Decimal, Evidence]] = field(default_factory=dict)   # fees, tax, total

    def get(self, key: str) -> Optional[Decimal]:
        return self.stated[key][0] if key in self.stated else None


def _num(s: str) -> Decimal:
    return Decimal(s.replace(",", ""))


def parse_invoice(doc: TextDoc) -> Invoice:
    inv = Invoice(doc)
    for i, line in enumerate(doc.lines, start=1):
        ev = Evidence(doc.name, f"line {i}", line.strip())
        hit = ENTRY.match(line.strip())
        if hit:
            d, who, desc, hours, rate, amount = hit.groups()
            inv.entries.append(TimeEntry(date.fromisoformat(d), who, desc, _num(hours), _num(rate), _num(amount), ev))
            continue
        for label, key in LABELS.items():
            if line.strip().lower().startswith(label) and MONEY.search(line):
                inv.stated[key] = (_num(MONEY.search(line).group(1)), ev)
    return inv


def invoices(m: Matter) -> list[Invoice]:
    return [parse_invoice(d) for d in m.texts if d.doc_type == "legal_invoice"]
