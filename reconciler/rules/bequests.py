"""Gifts of money in the will against the payments in the accounts."""
from __future__ import annotations

import re
from decimal import Decimal

from ..checks import Config, check
from ..extract import statements, tokens
from ..models import Finding, Matter
from ._common import fmt

# "I give the sum of $10,000 to the Kingston Public Library Foundation."
GIFT = re.compile(r"\bI (?:give|bequeath|leave)\b[^$]*\$\s?([0-9][0-9,]*(?:\.[0-9]{2})?)\s+to\s+(?:the\s+)?(.+?)\s*(?:[.,;]|$)", re.I)


@check
def check_bequests(m: Matter, cfg: Config) -> list[Finding]:
    out: list[Finding] = []
    payments = [t for t in m.accounts if t.direction == "out"]
    for doc in m.texts:
        if doc.doc_type != "will":
            continue
        for s in statements(doc):
            hit = GIFT.search(s.text)
            if not hit:
                continue
            amount, name = Decimal(hit.group(1).replace(",", "")), hit.group(2)
            paid = any(t.amount == amount and (tokens(t.description) & tokens(name)
                                               or "bequest" in t.description.lower()
                                               or "legacy" in t.description.lower())
                       for t in payments)
            if not paid:
                out.append(Finding(
                    "unpaid_bequest", f"{amount:.2f}", "medium",
                    f"Will leaves {fmt(amount)} to {name}; the accounts show no payment",
                    "The Will makes this gift but no disbursement of that amount to that recipient "
                    "appears in the accounts. It may not yet be due; the accounts do not say.",
                    [s.cite()],
                    amount=amount,
                    plain=f"The will leaves {fmt(amount)} to {name}. The accounts show no payment "
                          "of this gift so far."))
    return out
