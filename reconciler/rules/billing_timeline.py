"""A letter says a document has not arrived; the lawyers' own time records show they had it."""
from __future__ import annotations

import re

from ..checks import Config, check
from ..extract import DOC_TYPES, PENDING, statements
from ..invoices import invoices
from ..models import Finding, Matter

HANDLED = re.compile(r"\breview|\breceiv|\breceipt", re.I)


@check
def check_billing_timeline(m: Matter, cfg: Config) -> list[Finding]:
    out: list[Finding] = []
    entries = [e for inv in invoices(m) for e in inv.entries]
    seen: set[str] = set()
    for doc in m.texts:
        if doc.doc_type or not doc.date:
            continue
        for s in statements(doc):
            if not PENDING.search(s.text):
                continue
            for dt in s.doc_types():
                label, pattern = DOC_TYPES[dt]
                earlier = [e for e in entries if e.date < doc.date
                           and pattern.search(e.description) and HANDLED.search(e.description)]
                if earlier and dt not in seen:
                    seen.add(dt)
                    e = min(earlier, key=lambda x: x.date)
                    gap = (doc.date - e.date).days
                    out.append(Finding(
                        "billing_contradiction", dt, "high",
                        f"Letter of {doc.date} says the {label} is outstanding; time was billed for it on {e.date}",
                        f"The executor's lawyers recorded time on this document {gap} days before "
                        "their letter describing it as not yet received.",
                        [s.cite(), e.evidence],
                        plain=f"A letter dated {doc.date} said the {label} had not yet arrived. The same "
                              f"law firm's invoice records work on it on {e.date}, {gap} days earlier."))
    return out
